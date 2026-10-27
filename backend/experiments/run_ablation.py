"""Ablation: 6 scenarios x 3 conditions x 5 seeds -> results.json (+ markdown tables)."""
import json, pathlib, statistics as st, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aegis.world import Scenario
from aegis.pipeline import RunConfig, run_scenario, CONDITIONS

SEEDS = [1, 2, 3, 4, 5]
METRICS = ["success", "violations", "route_cost", "travel_cost", "planning_ms", "replanning_ms", "unsafe", "utilization"]


def load_scenarios():
    return [Scenario.from_dict(json.loads(p.read_text())) for p in sorted((ROOT / "scenarios").glob("S*.json"))]


def agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"mean": round(st.mean(vals), 2), "std": round(st.pstdev(vals), 2)}


def run_all(seeds=SEEDS, progress=None):
    scns = load_scenarios()
    per = {c: {s.id: {m: [] for m in METRICS} for s in scns} for c in CONDITIONS}
    for s in scns:
        for c in CONDITIONS:
            for seed in seeds:
                m = run_scenario(s, RunConfig(condition=c, seed=seed))["metrics"]
                for k in METRICS:
                    per[c][s.id][k].append(float(m[k]) if m[k] is not None else None)
            if progress: progress(s.id, c)
    overall, by_scn = {}, {}
    for c in CONDITIONS:
        overall[c] = {}
        for k in METRICS:
            runs = [v for s in scns for v in per[c][s.id][k] if v is not None]
            a = agg(runs)
            if a and k == "success": a = {"mean": round(100 * a["mean"], 1), "std": round(100 * a["std"], 1)}
            overall[c][k] = a
        by_scn[c] = {s.id: {k: agg(per[c][s.id][k]) for k in METRICS} for s in scns}
    return {"seeds": seeds, "scenarios": [{"id": s.id, "name": s.name} for s in scns],
            "conditions": CONDITIONS, "overall": overall, "by_scenario": by_scn}


def tables(res):
    f = lambda a: "–" if a is None else f"{a['mean']} ± {a['std']}"
    rows = [("Planning success rate (%)", "success"), ("Constraint violations / plan", "violations"),
            ("Route cost (composite)", "route_cost"), ("Planning time (ms)", "planning_ms"),
            ("Replanning time (ms)", "replanning_ms"), ("Unsafe decisions / plan", "unsafe"),
            ("Resource utilization (%)", "utilization")]
    out = ["| Metric | " + " | ".join(res["conditions"].values()) + " |", "|---|---|---|---|"]
    for name, k in rows:
        out.append(f"| {name} | " + " | ".join(f(res["overall"][c][k]) for c in res["conditions"]) + " |")
    out += ["", "| Scenario | " + " | ".join(res["conditions"].values()) + " |", "|---|---|---|---|"]
    for s in res["scenarios"]:
        out.append(f"| {s['id']} | " + " | ".join(str(res["by_scenario"][c][s["id"]]["violations"]["mean"]) for c in res["conditions"]) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    res = run_all()
    (ROOT / "experiments" / "results.json").write_text(json.dumps(res, indent=1))
    t = tables(res)
    (ROOT / "experiments" / "tables.md").write_text(t)
    print(t)
