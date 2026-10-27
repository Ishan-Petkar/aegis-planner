"""Explanations built directly from solver data structures (no free-form text generation)."""
from __future__ import annotations

from .world import Scenario, WorldGraph


def explain_plan(scn: Scenario, world: WorldGraph, plan: dict, risks: dict, violations: list[dict],
                 condition: str) -> dict:
    label = lambda n: world.nodes[n].label if n in world.nodes else n
    bad = {}
    for x in violations:
        if x.get("action"):
            bad.setdefault(x["action"], []).append(x)
    out: dict[str, dict] = {}
    for a in plan["actions"]:
        note = plan.get("notes", {}).get(a["id"], {})
        r = risks.get(a["id"], {})
        e: dict = {"action": a["id"], "type": a["type"], "violations": bad.get(a["id"], []), "risk": r}
        if a["type"] == "route":
            names = [label(n) for n in a["path"]]
            e["title"] = f"{'Dispatch' if a.get('leg') == 'dispatch' else 'Evacuation'} route: {names[0]} to {names[-1]}"
            e["path"] = names
            if note.get("best"):
                b = note["best"]
                e["facts"] = [
                    ("Path cost", b["cost"]), ("Est. time (min)", b["time"]),
                    ("Composite g(n)", b["composite"]), ("Risk score R", r.get("R")),
                ]
                e["alternatives"] = [
                    {"path": [label(n) for n in alt["path"]], "composite": alt["composite"],
                     "delta": round(alt["composite"] - b["composite"], 2)} for alt in note.get("alternatives", [])
                ]
            else:
                e["facts"] = [("Source", "direct plan, no solver trace"), ("Risk score R", r.get("R"))]
                e["alternatives"] = []
        else:
            g = scn.group(a["group"])
            t = scn.team(a["team"])
            e["title"] = f"Assignment: {t.name if t else a['team']} to {g.label}"
            csp = note.get("csp")
            if csp:
                e["facts"] = [("Candidate teams", len(csp["candidates"])),
                              ("Overlapping groups", len(csp["overlaps_with"])), ("Risk score R", r.get("R"))]
                e["candidates"] = [{"team": scn.team(c["team"]).name, "eta": c["eta"], "route_cost": c["route_cost"],
                                    "chosen": c["team"] == a["team"]} for c in csp["candidates"]]
                e["eliminated"] = [{"team": scn.team(k).name, "reason": why} for k, why in csp["eliminated"].items()]
            else:
                e["facts"] = [("Source", "direct plan, no constraint trace"), ("Risk score R", r.get("R"))]
                e["candidates"], e["eliminated"] = [], []
        out[a["id"]] = e
    return out
