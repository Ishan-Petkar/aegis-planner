"""Goal decomposition (AEGIS Decomposer) and the Baseline Planner."""
from __future__ import annotations

import heapq
import math
import random

from .world import Scenario, WorldGraph


class Decomposer:
    """Interface: turn a high-level objective into well-typed sub-tasks."""

    def decompose(self, scn: Scenario, world: WorldGraph, hints: dict | None, iteration: int) -> list[dict]:
        raise NotImplementedError


def _nearest_safe(world: WorldGraph, loc: str, exclude: set[str]) -> str:
    sites = [n for n in world.hospitals() if n.id not in exclude] or world.hospitals()
    return min(sites, key=lambda n: world.dist(loc, n.id)).id


class AegisDecomposer(Decomposer):
    """Emits typed sub-tasks (route / assign). Reads the failed-plan hints on repair."""

    def __init__(self, seed: int, noise: float = 0.16):
        self.seed, self.noise = seed, noise

    def decompose(self, scn, world, hints=None, iteration=0):
        hints = hints or {}
        rng = random.Random(self.seed * 1009 + iteration * 97 + 11)
        noise = self.noise * (0.15 ** iteration)          # repairs are far more careful
        avoid = [list(e) for e in sorted(hints.get("avoid", ()))]
        excluded = hints.get("exclude_dst", {})
        safe_ids = [n.id for n in world.hospitals()]
        tasks: list[dict] = []
        for g in sorted(scn.groups, key=lambda x: -x.priority):
            if rng.random() < noise * 0.45:                # forgets a group entirely
                continue
            ttype = "airlift" if rng.random() < noise * 0.3 else "assign"   # unsupported task type
            tasks.append({"id": f"T-{g.id}-assign", "type": ttype, "group": g.id, "requires": list(g.needs)})
            tasks.append({"id": f"T-{g.id}-dispatch", "type": "route", "leg": "dispatch", "group": g.id,
                          "src": "@team", "dst": g.location, "avoid": avoid})
            dst = _nearest_safe(world, g.location, set(excluded.get(g.id, ())))
            if rng.random() < noise * 0.7 and len(safe_ids) > 1:   # picks a different destination
                dst = rng.choice([s for s in safe_ids if s != dst])
            if rng.random() < noise * 0.3:                 # forgets the evacuation leg
                continue
            tasks.append({"id": f"T-{g.id}-evac", "type": "route", "leg": "evacuate", "group": g.id,
                          "src": g.location, "dst": dst, "avoid": avoid})
        return tasks


class BaselinePlanner:
    """Greedy single-pass planner: fast but state-blind. Used as Condition 1."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed * 7919 + 13)

    def _path(self, world, src, dst, believed_blocked):
        dist = {src: 0.0}
        prev = {}
        heap = [(0.0, src)]
        while heap:
            d, n = heapq.heappop(heap)
            if n == dst:
                break
            if d > dist.get(n, math.inf):
                continue
            for m in world.adj[n]:
                e = world.edge(n, m)
                if e.key in believed_blocked:
                    continue
                nd = d + world.dist(n, m)
                if nd < dist.get(m, math.inf):
                    dist[m], prev[m] = nd, n
                    heapq.heappush(heap, (nd, m))
        if dst not in dist:
            return [src, dst]
        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        path.reverse()
        # "shortcut" — jumps over an intermediate stop even when no road exists
        if len(path) > 3 and self.rng.random() < 0.22:
            i = self.rng.randrange(1, len(path) - 2)
            del path[i]
        return path

    def plan(self, scn: Scenario, world: WorldGraph) -> dict:
        rng = self.rng
        noticed = {e.key for e in world.edges.values() if e.status == "blocked" and rng.random() < 0.5}
        actions = []
        for g in sorted(scn.groups, key=lambda x: -x.priority):
            teams = sorted(scn.teams, key=lambda t: world.dist(t.base, g.location))
            if rng.random() < 0.45:                         # sometimes checks capabilities
                capable = [t for t in teams if all(c in t.capabilities for c in g.needs)]
                teams = capable or teams
            team = teams[0]
            d_path = self._path(world, team.base, g.location, noticed)
            h = _nearest_safe(world, g.location, set())
            e_path = self._path(world, g.location, h, noticed)
            d_time = sum(world.dist(a, b) * 0.5 for a, b in zip(d_path, d_path[1:]))
            e_time = sum(world.dist(a, b) * 0.5 for a, b in zip(e_path, e_path[1:]))
            actions += [
                {"id": f"R-{g.id}-d", "type": "route", "group": g.id, "leg": "dispatch", "team": team.id,
                 "src": team.base, "dst": g.location, "path": d_path, "start": 0.0, "end": round(d_time, 2)},
                {"id": f"A-{g.id}", "type": "assign", "group": g.id, "team": team.id, "site": g.location,
                 "start": g.window[0], "end": g.window[1]},
                {"id": f"R-{g.id}-e", "type": "route", "group": g.id, "leg": "evacuate", "team": team.id,
                 "src": g.location, "dst": h, "path": e_path, "start": g.window[1],
                 "end": round(g.window[1] + e_time, 2)},
            ]
        return {"actions": actions, "dispatch_issues": [], "notes": {}, "csp": None}
