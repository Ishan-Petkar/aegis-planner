import json, pathlib
from aegis.world import WorldGraph, Node, Edge, Scenario, Team, Group
from aegis.astar import astar, Weights
from aegis.csp import solve_assignment
from aegis.verifier import verify
from aegis.risk import RiskConfig
from aegis.pipeline import RunConfig, run_scenario

SC = pathlib.Path(__file__).resolve().parents[1] / "scenarios"


def fig4():
    pos = {"v1": (10, 50), "v2": (30, 20), "v3": (30, 80), "v4": (55, 20), "v5": (55, 80), "v6": (80, 50), "v7": (50, 5)}
    types = {"v1": "residential", "v2": "intersection", "v3": "intersection", "v4": "intersection",
             "v5": "hazard", "v6": "hospital", "v7": "shelter"}
    nodes = [Node(k, k, types[k], *pos[k]) for k in pos]
    pairs = [("v1", "v2", 3), ("v1", "v3", 4), ("v2", "v3", 2), ("v2", "v4", 2), ("v3", "v5", 5), ("v4", "v6", 3),
             ("v5", "v6", 1), ("v4", "v7", 2), ("v2", "v7", 2)]
    return WorldGraph(nodes, [Edge(a, b, c, c, 0.1) for a, b, c in pairs])


def test_astar_optimal_and_avoids_blocked():
    w = fig4()
    best = astar(w, "v1", "v6", Weights(1, 0, 0))
    assert best["path"][0] == "v1" and best["path"][-1] == "v6"
    w.edge("v2", "v4").status = "blocked"
    detour = astar(w, "v1", "v6", Weights(1, 0, 0))
    assert ("v2", "v4") not in list(zip(detour["path"], detour["path"][1:]))
    assert detour["cost"] >= best["cost"]


def test_astar_no_route():
    w = fig4()
    for e in w.edges.values():
        if "v6" in (e.a, e.b):
            e.status = "blocked"
    assert astar(w, "v1", "v6", Weights()) is None


def _scn():
    w = fig4()
    teams = [Team("T1", "Alpha", "v7", 1, ["medical"]), Team("T2", "Bravo", "v6", 2, ["fire", "medical"])]
    groups = [Group("G1", "G1", "v1", 3, 10, ["medical"], (100, 140)), Group("G2", "G2", "v1", 2, 10, ["fire"], (110, 150))]
    return Scenario("t", "t", "", "", w, teams, groups)


def test_csp_respects_capability_and_overlap():
    s = _scn()
    r = solve_assignment(s, s.world, ["G1", "G2"], Weights(1, .5, 0))
    assert r["assignment"]["G2"] == "T2"          # only T2 has fire
    assert r["assignment"]["G1"] == "T1"          # overlap forbids T2 for both


def test_csp_conflict_set_when_unsat():
    s = _scn()
    s.groups[0].needs = ["fire"]                   # both groups now need T2 but overlap
    r = solve_assignment(s, s.world, ["G1", "G2"], Weights(1, .5, 0))
    assert set(r["conflict_set"]) == {"G1", "G2"} and r["dropped"]


def test_verifier_flags_bad_plan():
    s = _scn()
    s.world.edge("v2", "v4").status = "blocked"
    plan = {"dispatch_issues": [], "actions": [
        {"id": "R-G1-d", "type": "route", "group": "G1", "src": "v7", "dst": "v1", "path": ["v7", "v4", "v2", "v1"], "start": 0, "end": 5},
        {"id": "A-G1", "type": "assign", "group": "G1", "team": "T2", "site": "v1", "start": 100, "end": 140},
        {"id": "A-G2", "type": "assign", "group": "G2", "team": "T2", "site": "v1", "start": 110, "end": 150},
        {"id": "A-G3", "type": "assign", "group": "G1", "team": "T1", "site": "v1", "start": 100, "end": 140}]}
    types = {x["type"] for x in verify(plan, s, s.world, 0.55, RiskConfig())[0]}
    assert {"BLOCKED_ROUTE", "RESOURCE_CONFLICT", "INCOMPLETE_PLAN"} <= types


def test_full_aegis_has_no_hard_violations_on_all_scenarios():
    for p in sorted(SC.glob("S*.json")):
        s = Scenario.from_dict(json.loads(p.read_text()))
        for seed in (1, 2, 3):
            m = run_scenario(s, RunConfig(condition="full", seed=seed))["metrics"]
            assert m["violations"] == 0, (s.id, seed)


def test_baseline_worse_than_full():
    s = Scenario.from_dict(json.loads((SC / "S3.json").read_text()))
    b = run_scenario(s, RunConfig(condition="baseline", seed=1))["metrics"]
    f = run_scenario(s, RunConfig(condition="full", seed=1))["metrics"]
    assert b["violations"] > f["violations"]
