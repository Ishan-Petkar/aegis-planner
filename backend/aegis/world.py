"""World graph G = (V, E, w) with dynamic edge status, plus the scenario container."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field, asdict

DAMAGE_COST_MULT = 1.6   # damaged edges stay traversable but cost more...
DAMAGE_RISK_MULT = 1.5   # ...and are riskier

NODE_TYPES = ("hospital", "shelter", "hazard", "residential", "intersection")


@dataclass
class Node:
    id: str
    label: str
    type: str
    x: float
    y: float
    severity: float = 0.2
    hazard: bool = False

    @property
    def is_hazard(self) -> bool:
        return self.hazard or self.type == "hazard"


@dataclass
class Edge:
    a: str
    b: str
    cost: float
    time: float
    risk: float
    status: str = "open"          # open | blocked | damaged
    damage_rate: float = 0.0      # historical damage rate in [0, 1]

    @property
    def key(self) -> tuple[str, str]:
        return (self.a, self.b) if self.a <= self.b else (self.b, self.a)


@dataclass
class Team:
    id: str
    name: str
    base: str
    capacity: int
    capabilities: list[str]


@dataclass
class Group:
    id: str
    label: str
    location: str
    priority: int
    size: int
    needs: list[str]
    window: tuple[float, float]


def ekey(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


class WorldGraph:
    def __init__(self, nodes: list[Node], edges: list[Edge]):
        self.nodes: dict[str, Node] = {n.id: n for n in nodes}
        self.edges: dict[tuple[str, str], Edge] = {e.key: e for e in edges}
        self.adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for e in edges:
            self.adj[e.a].append(e.b)
            self.adj[e.b].append(e.a)

    # ---- access -------------------------------------------------------
    def edge(self, a: str, b: str) -> Edge | None:
        return self.edges.get(ekey(a, b))

    def dist(self, a: str, b: str) -> float:
        na, nb = self.nodes[a], self.nodes[b]
        return math.hypot(na.x - nb.x, na.y - nb.y)

    def hazards(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.is_hazard]

    def hospitals(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.type in ("hospital", "shelter")]

    # ---- effective weights (damage multipliers) -------------------------
    @staticmethod
    def eff_cost(e: Edge) -> float:
        return e.cost * (DAMAGE_COST_MULT if e.status == "damaged" else 1.0)

    @staticmethod
    def eff_time(e: Edge) -> float:
        return e.time * (DAMAGE_COST_MULT if e.status == "damaged" else 1.0)

    @staticmethod
    def eff_risk(e: Edge) -> float:
        return min(1.0, e.risk * (DAMAGE_RISK_MULT if e.status == "damaged" else 1.0))

    # ---- dynamics -----------------------------------------------------
    def apply_event(self, ev: dict) -> str:
        kind = ev["kind"]
        if kind in ("block", "damage"):
            a, b = ev["edge"]
            e = self.edge(a, b)
            if e is None:
                return f"unknown road {a}-{b}"
            e.status = "blocked" if kind == "block" else "damaged"
            if kind == "damage":
                e.damage_rate = max(e.damage_rate, 0.7)
            word = "blocked" if kind == "block" else "damaged"
            return f"Road {self.nodes[a].label} - {self.nodes[b].label} {word}"
        if kind == "hazard":
            n = self.nodes[ev["node"]]
            n.hazard = True
            n.severity = max(n.severity, 0.9)
            for other in self.adj[n.id]:
                e = self.edge(n.id, other)
                if e.status == "open":
                    e.status = "damaged"
                    e.damage_rate = max(e.damage_rate, 0.7)
            return f"New hazard at {n.label}"
        return f"unknown event {kind}"

    def copy(self) -> "WorldGraph":
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorldGraph":
        return cls([Node(**n) for n in d["nodes"]], [Edge(**e) for e in d["edges"]])


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    objective: str
    world: WorldGraph
    teams: list[Team]
    groups: list[Group]
    events: list[dict] = field(default_factory=list)

    def team(self, tid: str) -> Team | None:
        return next((t for t in self.teams if t.id == tid), None)

    def group(self, gid: str) -> Group | None:
        return next((g for g in self.groups if g.id == gid), None)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "objective": self.objective, **self.world.to_dict(),
            "teams": [asdict(t) for t in self.teams],
            "groups": [{**asdict(g), "window": list(g.window)} for g in self.groups],
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Scenario":
        return cls(
            id=d["id"], name=d["name"], description=d.get("description", ""),
            objective=d.get("objective", "Evacuate all groups to the nearest hospital or safe zone"),
            world=WorldGraph.from_dict(d),
            teams=[Team(**t) for t in d["teams"]],
            groups=[Group(**{**g, "window": tuple(g["window"])}) for g in d["groups"]],
            events=d.get("events", []),
        )
