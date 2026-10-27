"""Generate -> Verify -> Repair -> Execute control loop and the three experimental conditions."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

from .astar import Weights
from .decomposer import AegisDecomposer, BaselinePlanner
from .dispatcher import dispatch
from .explain import explain_plan
from .risk import RiskConfig, edge_search_risk
from .verifier import HARD_TYPES, verify
from .world import Scenario, WorldGraph

CONDITIONS = {
    "baseline": "Baseline Planner",
    "solvers": "AEGIS + Solvers",
    "full": "Full AEGIS",
}
EVAL_WEIGHTS = Weights(1.0, 0.5, 15.0)   # fixed weights used to score route cost in every condition


@dataclass
class RunConfig:
    condition: str = "full"
    seed: int = 1
    weights: Weights = field(default_factory=Weights)
    tau: float = 0.55
    risk: RiskConfig = field(default_factory=RiskConfig)
    max_repairs: int = 3
    noise: float = 0.16


def _hints_from(violations: list[dict], plan: dict, world: WorldGraph, hints: dict) -> dict:
    avoid = set(hints.get("avoid", ()))
    excl = {k: set(v) for k, v in hints.get("exclude_dst", {}).items()}
    by_id = {a["id"]: a for a in plan["actions"]}
    for x in violations:
        if x["type"] == "BLOCKED_ROUTE" and "-" in x["entity"]:
            a, b = x["entity"].split("-", 1)
            avoid.add(tuple(sorted((a, b))))
        elif x["type"] == "NO_ROUTE":
            excl.setdefault(x.get("group", ""), set()).add(x.get("dst"))
        elif x["type"] == "RISK_EXCEEDED":
            act = by_id.get(x["action"])
            if act and act["type"] == "route":
                edges = [world.edge(p, q) for p, q in zip(act["path"], act["path"][1:])]
                edges = [e for e in edges if e]
                if edges:
                    worst = max(edges, key=lambda e: edge_search_risk(world, e))
                    avoid.add(worst.key)
    return {"avoid": avoid, "exclude_dst": excl}


def _view(plan: dict) -> dict:
    return {"actions": plan["actions"], "dispatch_issues": plan["dispatch_issues"]}


def generate(scn: Scenario, world: WorldGraph, cfg: RunConfig, salt: int = 0) -> dict:
    """One planning episode for the configured condition."""
    t0 = time.perf_counter()
    trace: list[dict] = []
    if cfg.condition == "baseline":
        plan = BaselinePlanner(cfg.seed + salt).plan(scn, world)
        viol, risks = verify(plan, scn, world, cfg.tau, cfg.risk)
        trace.append({"iteration": 0, "stage": "generate", "tasks": [], "violations": []})
        ms = (time.perf_counter() - t0) * 1000
        return _finish(scn, world, cfg, plan, risks, trace, ms)

    dec = AegisDecomposer(cfg.seed + salt, cfg.noise)
    full = cfg.condition == "full"
    w = cfg.weights if full else Weights(cfg.weights.alpha, cfg.weights.beta, 0.0)
    hints: dict = {}
    plan = None
    for it in range(cfg.max_repairs + 1 if full else 1):
        tasks = dec.decompose(scn, world, hints, it)
        plan = dispatch(scn, world, tasks, w, risk_aware=full)
        if not full:
            trace.append({"iteration": it, "stage": "generate", "tasks": tasks, "violations": []})
            break
        viol, risks = verify(plan, scn, world, cfg.tau, cfg.risk)
        trace.append({"iteration": it, "stage": "generate" if it == 0 else "repair", "tasks": tasks,
                      "violations": viol, "plan_snapshot": copy.deepcopy(plan["actions"])})
        if not viol:
            break
        hints = _hints_from(viol, plan, world, hints)
    ms = (time.perf_counter() - t0) * 1000
    viol, risks = verify(plan, scn, world, cfg.tau, cfg.risk)
    return _finish(scn, world, cfg, plan, risks, trace, ms)


def _finish(scn, world, cfg, plan, risks, trace, ms) -> dict:
    viol, risks = verify(plan, scn, world, cfg.tau, cfg.risk)
    return {"plan": plan, "violations": viol, "risks": risks, "trace": trace, "ms": round(ms, 2),
            "explanations": explain_plan(scn, world, plan, risks, viol, cfg.condition)}


def run_scenario(scn: Scenario, cfg: RunConfig, extra_events: list[dict] | None = None) -> dict:
    world = scn.world.copy()
    events = sorted(scn.events + (extra_events or []), key=lambda e: e["at"])
    steps = []
    first = generate(scn, world, cfg)
    steps.append({"label": "Initial plan", "at": 0, "world": world.to_dict(), "event": None, "impact": [],
                  "replan_ms": None, **first})
    current = first
    for i, ev in enumerate(events, start=1):
        world = world.copy()
        desc = world.apply_event(ev)
        # which parts of the standing plan does this event invalidate?
        impact, _ = verify(copy.deepcopy(current["plan"]), scn, world, cfg.tau, cfg.risk, with_risk=False)
        impact = [x for x in impact if x["type"] in HARD_TYPES]
        if cfg.condition == "baseline":
            plan = copy.deepcopy(current["plan"])
            viol, risks = verify(plan, scn, world, cfg.tau, cfg.risk)
            current = {"plan": plan, "violations": viol, "risks": risks, "trace": [], "ms": 0.0,
                       "explanations": explain_plan(scn, world, plan, risks, viol, cfg.condition)}
            replan_ms = None
        else:
            current = generate(scn, world, cfg, salt=1000 * i)
            replan_ms = current["ms"]
        steps.append({"label": ev.get("label") or desc, "at": ev["at"], "world": world.to_dict(), "event": {**ev, "description": desc},
                      "impact": impact, "replan_ms": replan_ms, **current})
    return {"scenario_id": scn.id, "condition": cfg.condition, "condition_name": CONDITIONS[cfg.condition],
            "seed": cfg.seed, "steps": steps, "metrics": compute_metrics(scn, world, steps, cfg)}


def compute_metrics(scn: Scenario, world: WorldGraph, steps: list[dict], cfg: RunConfig) -> dict:
    last = steps[-1]
    plan, viol = last["plan"], last["violations"]
    hard = [x for x in viol if x["type"] != "RISK_EXCEEDED"]
    unsafe = [x for x in viol if x["type"] == "RISK_EXCEEDED"]
    route_cost = travel = 0.0
    for a in plan["actions"]:
        if a["type"] != "route":
            continue
        for p, q in zip(a["path"], a["path"][1:]):
            e = world.edge(p, q)
            c, t, r = (WorldGraph.eff_cost(e), WorldGraph.eff_time(e), WorldGraph.eff_risk(e)) if e else (world.dist(p, q) * 0.5,) * 2 + (0.3,)
            route_cost += EVAL_WEIGHTS.alpha * c + EVAL_WEIGHTS.beta * t + EVAL_WEIGHTS.gamma * r
            travel += EVAL_WEIGHTS.alpha * c + EVAL_WEIGHTS.beta * t
    per_team: dict[str, int] = {}
    for a in plan["actions"]:
        if a["type"] == "assign":
            per_team[a["team"]] = per_team.get(a["team"], 0) + 1
    cap = sum(t.capacity for t in scn.teams) or 1
    used = sum(min(n, scn.team(t).capacity) for t, n in per_team.items() if scn.team(t))
    replans = [s["replan_ms"] for s in steps[1:] if s["replan_ms"] is not None]
    return {
        "success": len(hard) == 0,
        "violations": len(hard),
        "unsafe": len(unsafe),
        "route_cost": round(route_cost, 2),
        "travel_cost": round(travel, 2),
        "planning_ms": steps[0]["ms"],
        "replanning_ms": round(sum(replans) / len(replans), 2) if replans else None,
        "utilization": round(100 * used / cap, 1),
        "repair_iterations": max(0, len(steps[0]["trace"]) - 1),
    }
