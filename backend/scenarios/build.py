"""Deterministic scenario generator. Run: python scenarios/build.py  (writes S1..S6 .json)."""
import json, math, random, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from aegis.world import WorldGraph, Node, Edge, Scenario, Team, Group, ekey
from aegis.astar import astar, Weights

CAPS = ["medical", "fire", "rescue", "logistics"]
NAMES = ["Kothrud", "Hadapsar", "Shivajinagar", "Viman Nagar", "Kharadi", "Baner", "Wakad", "Hinjewadi",
         "Swargate", "Deccan", "Katraj", "Aundh", "Pimpri", "Kondhwa", "Yerwada", "Camp",
         "Magarpatta", "Warje", "Bibwewadi", "Sinhagad Road"]

SPECS = [  # id, name, nodes, teams, groups, hospitals, events, seed
    ("S1", "Mutha River Flood", 11, 2, 5, 1, 2, 11),
    ("S2", "Pimpri Chemical Spill", 13, 3, 7, 2, 2, 22),
    ("S3", "Katraj Earthquake", 15, 3, 9, 2, 2, 33),
    ("S4", "Sinhagad Hill Wildfire", 17, 3, 11, 2, 2, 44),
    ("S5", "Khadakwasla Dam Breach", 19, 4, 13, 2, 2, 55),
    ("S6", "Pune Metro Multi-Hazard", 20, 4, 15, 2, 2, 66),
]


def build(spec):
    sid, name, n_nodes, n_teams, n_groups, n_hosp, n_events, seed = spec
    for attempt in range(200):
        rng = random.Random(seed * 1000 + attempt)
        pts = []
        while len(pts) < n_nodes:
            p = (rng.uniform(6, 94), rng.uniform(8, 92))
            if all(math.hypot(p[0] - q[0], p[1] - q[1]) > 15 for q in pts):
                pts.append(p)
        types = ["intersection"] * n_nodes
        order = list(range(n_nodes)); rng.shuffle(order)
        hosp = order[:n_hosp]; haz = order[n_hosp:n_hosp + 1]
        n_res = min(n_groups, n_nodes - n_hosp - 1 - 3)
        res_nodes = order[n_hosp + 1:n_hosp + 1 + n_res]
        res = [res_nodes[k % len(res_nodes)] for k in range(n_groups)]
        for i in hosp: types[i] = "hospital" if i == hosp[0] else "shelter"
        for i in haz: types[i] = "hazard"
        for i in res_nodes: types[i] = "residential"
        nodes = []
        names = NAMES[:]; rng.shuffle(names)
        for i, (x, y) in enumerate(pts):
            label = {"hospital": f"{names[i]} Hospital", "shelter": f"{names[i]} Shelter",
                     "hazard": f"{names[i]} Hazard Zone"}.get(types[i], names[i])
            sev = {"hazard": 0.9, "residential": rng.uniform(0.25, 0.45)}.get(types[i], rng.uniform(0.05, 0.2))
            nodes.append(Node(f"v{i+1}", label, types[i], round(x, 1), round(y, 1), round(sev, 2)))
        # edges: 3 nearest neighbours + MST for connectivity
        pairs = {}
        for i in range(n_nodes):
            near = sorted(range(n_nodes), key=lambda j: math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1]))[1:4]
            for j in near: pairs[ekey(f"v{i+1}", f"v{j+1}")] = 1
        parent = list(range(n_nodes))
        def find(a):
            while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
            return a
        allp = sorted(((math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1]), i, j) for i in range(n_nodes) for j in range(i+1, n_nodes)))
        for d, i, j in allp:
            if find(i) != find(j): parent[find(i)] = find(j); pairs[ekey(f"v{i+1}", f"v{j+1}")] = 1
        edges = []
        for (a, b) in pairs:
            na = next(n for n in nodes if n.id == a); nb = next(n for n in nodes if n.id == b)
            d = math.hypot(na.x-nb.x, na.y-nb.y)
            edges.append(Edge(a, b, round(d*0.5, 1), round(d*0.32 + rng.uniform(1, 3), 1),
                              round(rng.uniform(0.04, 0.22), 2), "open", round(rng.uniform(0, 0.25), 2)))
        world = WorldGraph(nodes, edges)
        hosp_ids = [f"v{i+1}" for i in hosp]
        # teams
        bases = [n.id for n in nodes if n.type in ("intersection", "hospital", "shelter")]
        rng.shuffle(bases)
        teams = []
        for k in range(n_teams):
            caps = rng.sample(CAPS, rng.choice([2, 2, 3]))
            teams.append(Team(f"T{k+1}", ["Alpha", "Bravo", "Charlie", "Delta"][k] + " Team",
                              bases[k % len(bases)], 0, caps))
        # groups with a planted feasible schedule
        res_ids = [f"v{i+1}" for i in res]
        groups, load, busy = [], {t.id: 0 for t in teams}, {t.id: [] for t in teams}
        for k, loc in enumerate(res_ids):
            for _ in range(60):
                t = rng.choice(teams)
                need = [rng.choice(t.capabilities)]
                s = rng.uniform(120, 260); e = s + rng.uniform(25, 45)
                if all(e <= b0 or s >= b1 for b0, b1 in busy[t.id]):
                    busy[t.id].append((s, e)); load[t.id] += 1
                    groups.append(Group(f"G{k+1}", f"Group {k+1} ({nodes[int(loc[1:])-1].label})", loc,
                                        rng.randint(1, 5), rng.randint(8, 60), need, (round(s), round(e))))
                    break
        if len(groups) != len(res_ids): continue
        for t in teams: t.capacity = load[t.id] + rng.choice([0, 1])
        for t in teams:
            if t.capacity == 0: t.capacity = 1
        # traps: damaged / blocked roads on the straight-line shortest paths of several groups
        w0 = Weights(1, 0.5, 0)
        trap_edges = []
        for g in groups:
            h = min(hosp_ids, key=lambda h: world.dist(g.location, h))
            p = astar(world, g.location, h, w0)
            if p and len(p["path"]) > 2 and rng.random() < 0.75:
                i = rng.randrange(len(p["path"]) - 1)
                trap_edges.append(ekey(p["path"][i], p["path"][i + 1]))
        trap_edges = list(dict.fromkeys(trap_edges))[: max(2, n_nodes // 5)]
        for i, k in enumerate(trap_edges):
            world.edges[k].status = "blocked" if i % 2 == 0 else "damaged"
            if i % 2: world.edges[k].damage_rate = 0.65
        # events: block an edge on a group's optimal dispatch route; add a hazard on an intersection
        events = []
        g = rng.choice(groups); t = rng.choice([t for t in teams if all(c in t.capabilities for c in g.needs)] or teams)
        p = astar(world, t.base, g.location, Weights(1, .5, 15), risk_aware=True)
        if p and len(p["path"]) > 2:
            i = rng.randrange(len(p["path"]) - 1)
            events.append({"at": 60, "kind": "block", "edge": list(ekey(p["path"][i], p["path"][i + 1])),
                           "label": "Bridge collapse"})
        if n_events > 1:
            cands = [n.id for n in nodes if n.type == "intersection"]
            cands = [c for c in cands if all(world.dist(c, g.location) > 12 for g in groups)]
            if cands: events.append({"at": 120, "kind": "hazard", "node": rng.choice(cands), "label": "Gas leak ignites"})
        scn = Scenario(sid, name, f"{n_nodes} locations, {n_teams} rescue teams, {n_groups} groups, {len(events)} mid-run events.",
                       "Evacuate all civilian groups to the nearest hospital or safe zone",
                       world, teams, groups, events)
        # validate: after all events every team can reach every group it could serve, every group reaches a hospital
        w = scn.world.copy()
        for ev in events: w.apply_event(ev)
        ok = all(astar(w, g.location, h, w0) for g in groups for h in hosp_ids[:1])
        ok = ok and all(any(astar(w, t.base, g.location, w0) for t in teams if all(c in t.capabilities for c in g.needs))
                        for g in groups)
        if ok and len(events) == n_events:
            return scn
    raise RuntimeError("could not build " + sid)


if __name__ == "__main__":
    out = pathlib.Path(__file__).parent
    for spec in SPECS:
        s = build(spec)
        (out / f"{s.id}.json").write_text(json.dumps(s.to_dict(), indent=1))
        print(s.id, s.name, len(s.world.nodes), "nodes", len(s.groups), "groups", s.events)
