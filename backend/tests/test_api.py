from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_scenarios_listed():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    assert len(r.json()) >= 6


def test_plan_returns_valid_full_plan():
    r = client.post("/api/plan", json={"scenario_id": "S1", "condition": "full", "seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["metrics"]["violations"] == 0
    assert len(body["steps"]) == 3


def test_event_triggers_replan():
    plan = client.post("/api/plan", json={"scenario_id": "S2", "condition": "full"}).json()
    edge = plan["scenario"]["edges"][0]
    r = client.post("/api/event", json={"run_id": plan["run_id"], "kind": "block", "edge": [edge["a"], edge["b"]]})
    assert r.status_code == 200
    assert len(r.json()["steps"]) == len(plan["steps"]) + 1


def test_unknown_scenario_is_404():
    assert client.post("/api/plan", json={"scenario_id": "nope"}).status_code == 404
