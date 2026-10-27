const rows = [
  ['World graph', 'G = (V, E, w) with w(e) = (cost, time, risk) and a dynamic status σ(e) ∈ {open, blocked, damaged}. Damaged roads stay passable at a cost and risk multiplier; blocked roads leave the search space.'],
  ['Goal decomposition', 'The objective becomes typed sub-tasks: route (A → B) and assign (team → group). Unrecognized task types are flagged for repair.'],
  ['A* router', 'f(n) = g(n) + h(n), g = Σ α·c + β·τ + γ·r. The heuristic is Euclidean distance scaled by the cheapest per-unit edge cost, so it is admissible.'],
  ['CSP assigner', 'One variable per target group, domain = available teams. Capacity, capability, non-overlap and geographic feasibility are enforced with AC-3 + backtracking. Unsatisfiable problems return a minimal conflict set.'],
  ['Risk scorer', 'R(a) = wh·H + wd·D + ws·S where H is hazard proximity, D historical damage, S target severity.'],
  ['Verification engine', 'Checks route validity, resource consistency, capability, preconditions, completeness and the risk ceiling τ, producing a typed violation report.'],
  ['Repair loop', 'A violation report triggers a new decomposition with hints (avoid roads, exclude destinations); up to 3 iterations before the system reports a planning failure.'],
]
export default function Method() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl font-semibold tracking-tight">Method</h1>
      <p className="text-stone-600">Experimental design: three conditions over a shared scenario set, five seeded runs each, scripted mid-run events at fixed times. Violations are always counted by the same verification engine, applied after the run, so conditions are comparable.</p>
      {rows.map(([t, d]) => <div key={t} className="card p-5"><h3 className="font-semibold text-teal-700">{t}</h3><p className="mt-1.5 text-sm text-stone-700">{d}</p></div>)}
    </div>
  )
}
