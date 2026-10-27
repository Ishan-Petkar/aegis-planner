"""AEGIS HTTP API.  Run: uvicorn api:app --port 8000"""
import json, pathlib, threading, uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aegis.astar import Weights
from aegis.pipeline import CONDITIONS, RunConfig, run_scenario
from aegis.risk import RiskConfig
from aegis.world import Scenario
from experiments import run_ablation

ROOT = pathlib.Path(__file__).resolve().parent
CUSTOM: dict[str, dict] = {}
RUNS: dict[str, dict] = {}
EXP = {"status": "idle", "progress": 0, "total": 0}

app = FastAPI(title="AEGIS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _all() -> dict[str, dict]:
    d = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "scenarios").glob("S*.json"))}
    d.update(CUSTOM)
    return d


class PlanReq(BaseModel):
    scenario_id: str | None = None
    scenario: dict | None = None
    condition: str = "full"
    seed: int = 1
    alpha: float = 1.0
    beta: float = 0.5
    gamma: float = 15.0
    tau: float = 0.55
    wh: float = 0.45
    wd: float = 0.25
    ws: float = 0.30


class EventReq(BaseModel):
    run_id: str
    kind: str
    edge: list[str] | None = None
    node: str | None = None


def _cfg(r: PlanReq) -> RunConfig:
    if r.condition not in CONDITIONS:
        raise HTTPException(400, "unknown condition")
    return RunConfig(condition=r.condition, seed=r.seed, weights=Weights(r.alpha, r.beta, r.gamma),
                     tau=r.tau, risk=RiskConfig(r.wh, r.wd, r.ws))


@app.get("/api/scenarios")
def scenarios():
    return [{"id": k, "name": v["name"], "description": v.get("description", ""), "nodes": len(v["nodes"]),
             "teams": len(v["teams"]), "groups": len(v["groups"]), "events": len(v.get("events", []))}
            for k, v in _all().items()]


@app.get("/api/scenarios/{sid}")
def scenario(sid: str):
    s = _all().get(sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    return s


@app.post("/api/scenarios")
def save_scenario(body: dict):
    try:
        Scenario.from_dict(body)
    except Exception as e:  # malformed builder payload
        raise HTTPException(422, f"invalid scenario: {e}")
    CUSTOM[body["id"]] = body
    return {"id": body["id"]}


@app.post("/api/plan")
def plan(req: PlanReq):
    data = req.scenario or _all().get(req.scenario_id or "")
    if not data:
        raise HTTPException(404, "scenario not found")
    scn = Scenario.from_dict(data)
    cfg = _cfg(req)
    result = run_scenario(scn, cfg)
    rid = uuid.uuid4().hex[:10]
    RUNS[rid] = {"scenario": data, "req": req, "extra": []}
    return {"run_id": rid, "scenario": data, **result}


@app.post("/api/event")
def event(ev: EventReq):
    run = RUNS.get(ev.run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if ev.kind not in ("block", "damage", "hazard"):
        raise HTTPException(400, "bad event kind")
    last_at = max([e["at"] for e in run["scenario"].get("events", []) + run["extra"]] or [0])
    labels = {"block": "Road blocked", "damage": "Road damaged", "hazard": "New hazard"}
    run["extra"].append({"at": last_at + 30, "kind": ev.kind, "edge": ev.edge, "node": ev.node,
                         "label": labels[ev.kind] + " (operator)"})
    scn = Scenario.from_dict(run["scenario"])
    result = run_scenario(scn, _cfg(run["req"]), extra_events=run["extra"])
    return {"run_id": ev.run_id, "scenario": run["scenario"], **result}


def _run_exp():
    scns = run_ablation.load_scenarios()
    EXP.update(status="running", progress=0, total=len(scns) * len(CONDITIONS))
    def tick(*_):
        EXP["progress"] += 1
    res = run_ablation.run_all(progress=tick)
    (ROOT / "experiments" / "results.json").write_text(json.dumps(res, indent=1))
    EXP["status"] = "done"


@app.post("/api/experiments/run")
def exp_run():
    if EXP["status"] != "running":
        threading.Thread(target=_run_exp, daemon=True).start()
    return EXP


@app.get("/api/experiments/status")
def exp_status():
    return EXP


@app.get("/api/experiments/results")
def exp_results():
    p = ROOT / "experiments" / "results.json"
    if not p.exists():
        raise HTTPException(404, "no results yet")
    return json.loads(p.read_text())
