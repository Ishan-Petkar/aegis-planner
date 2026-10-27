"""Task dispatcher: route -> A*, assign -> CSP. Everything also passes through the risk layer."""
from __future__ import annotations

from .astar import Weights, alternatives, astar
from .csp import solve_assignment
from .verifier import v
from .world import Scenario, WorldGraph


def dispatch(scn: Scenario, world: WorldGraph, tasks: list[dict], w: Weights, *, risk_aware: bool) -> dict:
    issues: list[dict] = []
    assign_groups: list[str] = []
    route_tasks: list[dict] = []
    for t in tasks:
        if t.get("type") == "assign":
            assign_groups.append(t["group"])
        elif t.get("type") == "route":
            route_tasks.append(t)
        else:
            issues.append(v("UNKNOWN_TASK", t.get("id"), t.get("group", "?"),
                            f"unrecognized task type '{t.get('type')}'"))

    csp = solve_assignment(scn, world, assign_groups, w, risk_aware=risk_aware)
    assignment: dict[str, str] = csp["assignment"]
    if csp["conflict_set"]:
        issues.append(v("RESOURCE_CONFLICT", None, ",".join(csp["conflict_set"]),
                        f"no feasible assignment for {', '.join(csp['conflict_set'])}; "
                        f"deferred {', '.join(csp['dropped']) or 'none'}"))

    actions: list[dict] = []
    notes: dict[str, dict] = {}
    for gid, tid in assignment.items():
        g = scn.group(gid)
        aid = f"A-{gid}"
        actions.append({"id": aid, "type": "assign", "group": gid, "team": tid, "site": g.location,
                        "start": g.window[0], "end": g.window[1]})
        notes[aid] = {"csp": csp["detail"][gid]}

    for t in route_tasks:
        gid = t["group"]
        g = scn.group(gid)
        if g is None:
            continue
        src = t["src"]
        if src == "@team":
            tid = assignment.get(gid)
            if tid is None:
                continue
            src = scn.team(tid).base
        tid = assignment.get(gid)
        avoid = {tuple(sorted(e)) for e in t.get("avoid", [])}
        best = astar(world, src, t["dst"], w, risk_aware=risk_aware, avoid_edges=avoid)
        if best is None and avoid:
            best = astar(world, src, t["dst"], w, risk_aware=risk_aware)
            avoid = set()
        if best is None:
            issues.append(v("NO_ROUTE", t["id"], t["dst"],
                            f"no open route from {world.nodes[src].label} to {world.nodes[t['dst']].label}",
                            group=gid, dst=t["dst"]))
            continue
        alts = alternatives(world, best, src, t["dst"], w, risk_aware=risk_aware, extra_avoid=avoid)
        leg = t["leg"]
        aid = f"R-{gid}-{'d' if leg == 'dispatch' else 'e'}"
        if leg == "dispatch":
            start = 0.0
        else:
            start = g.window[1]
        actions.append({"id": aid, "type": "route", "group": gid, "leg": leg, "team": tid, "src": src,
                        "dst": t["dst"], "path": best["path"], "start": start,
                        "end": round(start + best["time"], 2)})
        notes[aid] = {"best": best, "alternatives": alts}
    return {"actions": actions, "dispatch_issues": issues, "notes": notes, "csp": csp["detail"]}
