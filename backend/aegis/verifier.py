"""Verification engine (Algorithm 1) -> structured violation report."""
from __future__ import annotations

from .risk import RiskConfig, action_risk
from .world import Scenario, WorldGraph

HARD_TYPES = {"BLOCKED_ROUTE", "RESOURCE_CONFLICT", "CAPABILITY_MISMATCH", "PRECONDITION_FAIL",
              "INCOMPLETE_PLAN", "UNKNOWN_TASK", "NO_ROUTE", "INVALID_ROUTE"}


def v(vtype: str, action: str | None, entity: str, detail: str, **extra) -> dict:
    return {"type": vtype, "action": action, "entity": entity, "detail": detail, **extra}


def route_duration(world: WorldGraph, path: list[str]) -> float:
    total = 0.0
    for a, b in zip(path, path[1:]):
        e = world.edge(a, b)
        total += WorldGraph.eff_time(e) if e else world.dist(a, b) * 0.5
    return total


def verify(plan: dict, scn: Scenario, world: WorldGraph, tau: float, rcfg: RiskConfig,
           *, with_risk: bool = True) -> tuple[list[dict], dict]:
    """Returns (violations, risk_by_action)."""
    V: list[dict] = []
    risks: dict[str, dict] = {}
    actions = plan["actions"]
    by_id = {a["id"]: a for a in actions}
    label = lambda n: world.nodes[n].label if n in world.nodes else n

    V.extend(plan.get("dispatch_issues", []))

    for a in actions:
        if a["type"] == "route":
            path = a["path"]
            if not path or path[0] != a["src"] or path[-1] != a["dst"]:
                V.append(v("INVALID_ROUTE", a["id"], f"{a['src']}->{a['dst']}", "path does not connect its endpoints"))
            for x, y in zip(path, path[1:]):
                e = world.edge(x, y)
                if e is None:
                    V.append(v("BLOCKED_ROUTE", a["id"], f"{x}-{y}", f"no road between {label(x)} and {label(y)}"))
                elif e.status == "blocked":
                    V.append(v("BLOCKED_ROUTE", a["id"], f"{x}-{y}", f"road {label(x)} - {label(y)} is blocked"))
            a["end"] = round(a["start"] + route_duration(world, path), 2)

    # assignment checks
    load: dict[str, list[dict]] = {}
    for a in actions:
        if a["type"] != "assign":
            continue
        t = scn.team(a["team"])
        g = scn.group(a["group"])
        if t is None:
            V.append(v("RESOURCE_CONFLICT", a["id"], a["team"], "assigned team does not exist"))
            continue
        missing = [c for c in (g.needs if g else []) if c not in t.capabilities]
        if missing:
            V.append(v("CAPABILITY_MISMATCH", a["id"], t.id, f"{t.name} lacks {', '.join(missing)} required by {g.label}"))
        for other in load.get(t.id, []):
            if a["start"] < other["end"] and other["start"] < a["end"]:
                V.append(v("RESOURCE_CONFLICT", a["id"], t.id, f"{t.name} double-booked with {other['group']} (overlapping windows)"))
        load.setdefault(t.id, []).append(a)
    for tid, acts in load.items():
        t = scn.team(tid)
        if len(acts) > t.capacity:
            V.append(v("RESOURCE_CONFLICT", acts[-1]["id"], tid, f"{t.name} over capacity ({len(acts)} > {t.capacity})"))

    # preconditions (arrive before work starts, finish work before transport)
    for g in scn.groups:
        r_d, a_, r_e = by_id.get(f"R-{g.id}-d"), by_id.get(f"A-{g.id}"), by_id.get(f"R-{g.id}-e")
        if r_d and a_ and r_d["end"] > a_["start"] + 1e-6:
            V.append(v("PRECONDITION_FAIL", a_["id"], r_d["id"], f"team arrives at {r_d['end']:.0f} min, after operation starts at {a_['start']:.0f}"))
        if a_ and r_e and a_["end"] > r_e["start"] + 1e-6:
            V.append(v("PRECONDITION_FAIL", r_e["id"], a_["id"], "evacuation starts before the rescue operation ends"))
        if not (r_d and a_ and r_e):
            V.append(v("INCOMPLETE_PLAN", None, g.id, f"{g.label} has no complete dispatch / rescue / evacuation chain"))

    # risk
    for a in actions:
        r = action_risk(world, a, rcfg)
        risks[a["id"]] = r
        if with_risk and r["R"] > tau:
            V.append(v("RISK_EXCEEDED", a["id"], a["id"], f"risk {r['R']:.2f} exceeds ceiling {tau:.2f}", risk=r))
    return V, risks
