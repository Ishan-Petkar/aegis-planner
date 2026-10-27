"""A* router over the dynamic world graph with composite cost g = sum(alpha*c + beta*t + gamma*r)."""
from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass

from .risk import edge_search_risk
from .world import WorldGraph


@dataclass
class Weights:
    alpha: float = 1.0
    beta: float = 0.5
    gamma: float = 15.0


def _min_unit(world: WorldGraph, w: Weights) -> float:
    best = math.inf
    for e in world.edges.values():
        if e.status == "blocked":
            continue
        length = world.dist(e.a, e.b)
        if length > 1e-9:
            best = min(best, (w.alpha * e.cost + w.beta * e.time) / length)
    return 0.0 if best is math.inf else best


def astar(world: WorldGraph, src: str, dst: str, w: Weights, *, risk_aware: bool = False,
          avoid_edges: set | None = None, avoid_nodes: set | None = None) -> dict | None:
    avoid_edges = avoid_edges or set()
    avoid_nodes = avoid_nodes or set()
    if src == dst:
        return _summary(world, [src], w, risk_aware)
    unit = _min_unit(world, w)
    tie = itertools.count()
    open_heap = [(0.0, next(tie), src)]
    g = {src: 0.0}
    came: dict[str, str] = {}
    closed: set[str] = set()
    while open_heap:
        _, _, n = heapq.heappop(open_heap)
        if n in closed:
            continue
        if n == dst:
            path = [n]
            while path[-1] in came:
                path.append(came[path[-1]])
            path.reverse()
            return _summary(world, path, w, risk_aware)
        closed.add(n)
        for m in world.adj[n]:
            e = world.edge(n, m)
            if e.status == "blocked" or e.key in avoid_edges:
                continue
            if m in avoid_nodes and m != dst:
                continue
            step = w.alpha * WorldGraph.eff_cost(e) + w.beta * WorldGraph.eff_time(e)
            if w.gamma:
                r = edge_search_risk(world, e) if risk_aware else WorldGraph.eff_risk(e)
                step += w.gamma * r
            ng = g[n] + step
            if ng < g.get(m, math.inf):
                g[m] = ng
                came[m] = n
                f = ng + unit * world.dist(m, dst)
                heapq.heappush(open_heap, (f, next(tie), m))
    return None


def _summary(world: WorldGraph, path: list[str], w: Weights, risk_aware: bool) -> dict:
    cost = time = risk = 0.0
    for a, b in zip(path, path[1:]):
        e = world.edge(a, b)
        cost += WorldGraph.eff_cost(e)
        time += WorldGraph.eff_time(e)
        risk += edge_search_risk(world, e) if risk_aware else WorldGraph.eff_risk(e)
    composite = w.alpha * cost + w.beta * time + w.gamma * risk
    return {"path": path, "cost": round(cost, 2), "time": round(time, 2),
            "risk_sum": round(risk, 3), "composite": round(composite, 2)}


def alternatives(world: WorldGraph, best: dict, src: str, dst: str, w: Weights, *,
                 risk_aware: bool = False, extra_avoid: set | None = None, limit: int = 3) -> list[dict]:
    """Single-edge-deviation alternatives, used for explanations."""
    seen = {tuple(best["path"])}
    alts = []
    path = best["path"]
    for a, b in zip(path, path[1:]):
        avoid = set(extra_avoid or ()) | {world.edge(a, b).key}
        alt = astar(world, src, dst, w, risk_aware=risk_aware, avoid_edges=avoid)
        if alt and tuple(alt["path"]) not in seen:
            seen.add(tuple(alt["path"]))
            alts.append(alt)
    alts.sort(key=lambda r: r["composite"])
    return alts[:limit]
