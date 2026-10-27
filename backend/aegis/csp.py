"""CSP resource assignment: X_k = team for target group k.

Unary pruning (capability, reachability, arrival before window) -> AC-3 over the
non-overlap constraints -> backtracking with MRV, capacity forward-checking.
If unsatisfiable, a minimal conflict set is returned (deletion filter).
"""
from __future__ import annotations

from collections import deque

from .astar import Weights, astar
from .world import Scenario


def _overlap(a, b) -> bool:
    return a.window[0] < b.window[1] and b.window[0] < a.window[1]


def solve_assignment(scn: Scenario, world, group_ids: list[str], w: Weights, *,
                     risk_aware: bool = False, avoid_edges: set | None = None) -> dict:
    groups = [scn.group(g) for g in group_ids if scn.group(g)]
    teams = scn.teams
    cost: dict[tuple[str, str], dict | None] = {}
    domains: dict[str, list[str]] = {}
    eliminated: dict[str, dict[str, str]] = {}

    # ---- unary constraints ----
    for g in groups:
        domains[g.id], eliminated[g.id] = [], {}
        for t in teams:
            missing = [c for c in g.needs if c not in t.capabilities]
            if t.capacity <= 0:
                eliminated[g.id][t.id] = "no capacity"
                continue
            if missing:
                eliminated[g.id][t.id] = f"lacks capability: {', '.join(missing)}"
                continue
            r = astar(world, t.base, g.location, w, risk_aware=risk_aware, avoid_edges=avoid_edges)
            cost[(t.id, g.id)] = r
            if r is None:
                eliminated[g.id][t.id] = "no open route to site"
            elif r["time"] > g.window[0]:
                eliminated[g.id][t.id] = f"cannot arrive before window ({r['time']:.0f} > {g.window[0]:.0f} min)"
            else:
                domains[g.id].append(t.id)

    neighbors = {g.id: [h.id for h in groups if h.id != g.id and _overlap(g, h)] for g in groups}

    # ---- AC-3 on X_i != X_j for overlapping windows ----
    def ac3(doms: dict[str, list[str]]) -> bool:
        queue = deque((i, j) for i in neighbors for j in neighbors[i])
        while queue:
            i, j = queue.popleft()
            if len(doms[j]) == 1 and doms[j][0] in doms[i]:
                doms[i] = [v for v in doms[i] if v != doms[j][0]]
                if not doms[i]:
                    return False
                for k in neighbors[i]:
                    if k != j:
                        queue.append((k, i))
        return True

    def search(gids: list[str]) -> dict | None:
        doms = {g: list(domains[g]) for g in gids}
        sub_nb = {g: [n for n in neighbors[g] if n in doms] for g in gids}
        # AC-3 restricted to subset
        queue = deque((i, j) for i in sub_nb for j in sub_nb[i])
        while queue:
            i, j = queue.popleft()
            if len(doms[j]) == 1 and doms[j][0] in doms[i]:
                doms[i] = [v for v in doms[i] if v != doms[j][0]]
                if not doms[i]:
                    return None
                queue.extend((k, i) for k in sub_nb[i] if k != j)
        load = {t.id: 0 for t in teams}
        cap = {t.id: t.capacity for t in teams}
        assign: dict[str, str] = {}
        prio = {g.id: g.priority for g in groups}

        def bt() -> bool:
            if len(assign) == len(gids):
                return True
            unassigned = [g for g in gids if g not in assign]
            def live(g):
                return [v for v in doms[g] if load[v] < cap[v]
                        and all(assign.get(n) != v for n in sub_nb[g])]
            g = min(unassigned, key=lambda x: (len(live(x)), -prio[x]))
            for v in sorted(live(g), key=lambda t: cost[(t, g)]["composite"] + 8 * load[t]):
                assign[g] = v
                load[v] += 1
                if bt():
                    return True
                del assign[g]
                load[v] -= 1
            return False

        return dict(assign) if bt() else None

    gids = [g.id for g in groups]
    solution = search(gids)
    conflict: list[str] = []
    dropped: list[str] = []
    if solution is None:
        # deletion filter -> minimal conflict set
        core = list(gids)
        for g in list(core):
            trial = [x for x in core if x != g]
            if trial and search(trial) is None:
                core = trial
            elif not trial:
                break
        conflict = core
        keep = list(gids)
        # relax lowest-priority groups until satisfiable
        for g in sorted(conflict, key=lambda x: scn.group(x).priority):
            if search(keep) is not None:
                break
            keep.remove(g)
            dropped.append(g)
        solution = search(keep) or {}

    choice = {}
    for g in gids:
        t = solution.get(g)
        choice[g] = {
            "team": t,
            "candidates": [{"team": v, "route_cost": cost[(v, g)]["composite"], "eta": cost[(v, g)]["time"]}
                           for v in domains[g]],
            "eliminated": eliminated[g],
            "overlaps_with": neighbors[g],
        }
    return {"assignment": solution, "conflict_set": conflict, "dropped": dropped, "detail": choice,
            "routes": {k: v for k, v in cost.items() if v is not None}}
