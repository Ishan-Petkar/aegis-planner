"""Transparent heuristic risk scorer: R(a) = wh*H + wd*D + ws*S  (weights sum to 1)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .world import WorldGraph

HAZARD_SCALE = 18.0  # map units; H(d) = exp(-d / scale)


@dataclass
class RiskConfig:
    wh: float = 0.45
    wd: float = 0.25
    ws: float = 0.30

    def normalized(self) -> "RiskConfig":
        s = (self.wh + self.wd + self.ws) or 1.0
        return RiskConfig(self.wh / s, self.wd / s, self.ws / s)


def hazard_proximity(world: WorldGraph, x: float, y: float) -> float:
    hs = world.hazards()
    if not hs:
        return 0.0
    d = min(math.hypot(h.x - x, h.y - y) for h in hs)
    return math.exp(-d / HAZARD_SCALE)


def edge_damage(e) -> float:
    return max(e.damage_rate, 0.6 if e.status == "damaged" else 0.0)


def edge_hazard(world: WorldGraph, e) -> float:
    a, b = world.nodes[e.a], world.nodes[e.b]
    return max(hazard_proximity(world, a.x, a.y), hazard_proximity(world, b.x, b.y),
               hazard_proximity(world, (a.x + b.x) / 2, (a.y + b.y) / 2))


def edge_search_risk(world: WorldGraph, e) -> float:
    """Per-edge risk used by the risk-aware A* (base risk + hazard proximity + damage)."""
    r = WorldGraph.eff_risk(e) + 0.6 * edge_hazard(world, e) + 0.3 * edge_damage(e)
    return min(1.0, r)


def factors_for_path(world: WorldGraph, path: list[str]) -> tuple[float, float, float]:
    H = D = 0.0
    for a, b in zip(path, path[1:]):
        e = world.edge(a, b)
        if e is None:
            continue
        H = max(H, edge_hazard(world, e))
        D = max(D, edge_damage(e))
    if path:
        n = world.nodes[path[-1]]
        H = max(H, hazard_proximity(world, n.x, n.y))
        S = max(world.nodes[p].severity for p in path[-1:])
    else:
        S = 0.0
    return min(H, 1.0), min(D, 1.0), min(S, 1.0)


def factors_for_site(world: WorldGraph, loc: str) -> tuple[float, float, float]:
    n = world.nodes[loc]
    H = hazard_proximity(world, n.x, n.y)
    D = max((edge_damage(world.edge(loc, o)) for o in world.adj[loc]), default=0.0)
    return H, D, n.severity


def score(H: float, D: float, S: float, cfg: RiskConfig) -> float:
    c = cfg.normalized()
    return round(c.wh * H + c.wd * D + c.ws * S, 4)


def action_risk(world: WorldGraph, action: dict, cfg: RiskConfig) -> dict:
    if action["type"] == "route":
        H, D, S = factors_for_path(world, action.get("path", []))
    else:
        H, D, S = factors_for_site(world, action["site"])
    return {"H": round(H, 3), "D": round(D, 3), "S": round(S, 3), "R": score(H, D, S, cfg)}
