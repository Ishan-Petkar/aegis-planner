import { useEffect, useState } from 'react'
import { api } from '../api'
import WorldMap from '../components/WorldMap'
import type { Run } from '../types'

const STEPS: [string, string][] = [
  ['Decompose', 'The mission becomes typed route and assignment tasks.'],
  ['Solve', 'A* finds the roads, a constraint solver picks the teams.'],
  ['Verify', 'Every route, team and risk score is checked against the map.'],
  ['Repair', 'Violations are reported and the plan is rebuilt.'],
  ['Execute', 'New hazards on the road trigger a fresh plan.'],
]
const ROWS: [string, string, string][] = [
  ['baseline', 'Baseline planner', '#b9462f'],
  ['solvers', 'AEGIS + solvers', '#9a6b14'],
  ['full', 'Full AEGIS', '#0f766e'],
]

export default function Overview({ go }: { go: (t: string) => void }) {
  const [run, setRun] = useState<Run | null>(null)
  const [res, setRes] = useState<any>(null)
  useEffect(() => {
    api.plan({ scenario_id: 'S1', condition: 'full', seed: 1 }).then(setRun).catch(() => {})
    api.expResults().then(setRes).catch(() => {})
  }, [])
  const s = run?.steps[0]

  return (
    <div className="space-y-14 sm:space-y-20">
      <section className="grid items-center gap-8 lg:grid-cols-[1fr_1.05fr] lg:gap-14">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-stone-600">Disaster-response planning · Pune</p>
          <h1 className="mt-4 text-4xl leading-[1.08] text-stone-900 sm:text-5xl lg:text-[3.4rem]">
            Rescue plans, checked against the road network before anyone moves.
          </h1>
          <p className="mt-5 max-w-lg text-[15px] leading-relaxed text-stone-700">
            AEGIS plans routes and rescue teams for a city under flood, fire or collapse, then verifies each decision against blocked roads, team capability and risk. When a bridge fails mid-operation, it replans.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button className="btn btn-primary" onClick={() => go('mission')}>Open Mission Control</button>
            <button className="btn btn-ghost" onClick={() => go('experiments')}>Experiment results</button>
          </div>
        </div>

        <figure className="min-w-0">
          <div className="aspect-square max-h-[560px] w-full overflow-hidden rounded-xl border border-stone-900/15 bg-ink-900">
            {s && run ? (
              <WorldMap nodes={s.world.nodes} edges={s.world.edges} teams={run.scenario.teams} groups={run.scenario.groups} actions={s.plan.actions} violations={s.violations} />
            ) : <div className="grid h-full place-items-center text-sm text-stone-500">Loading plan…</div>}
          </div>
          <figcaption className="mt-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs text-stone-600">
            <span><span className="font-medium text-stone-800">S1 · Mutha River Flood.</span> Verified plan for 5 groups and 2 teams.</span>
            <span className="font-mono">solid = dispatch · dashed team colour = evacuation · red dashes = blocked road</span>
          </figcaption>
        </figure>
      </section>

      {res && (
        <section>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-stone-900/15 pt-4">
            <h2 className="text-2xl text-stone-900">Rule violations per plan</h2>
            <p className="font-mono text-xs text-stone-600">{res.scenarios.length} scenarios · {res.seeds.length} runs each</p>
          </div>
          <div className="mt-5 grid divide-y divide-stone-900/15 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {ROWS.map(([k, name, color]) => (
              <div key={k} className="py-4 sm:px-6 sm:first:pl-0 sm:last:pr-0">
                <p className="text-sm text-stone-700">{name}</p>
                <p className="mt-1 font-serif text-5xl font-semibold tabular-nums" style={{ color }}>{res.overall[k].violations.mean.toFixed(1)}</p>
                <p className="mt-1 text-xs text-stone-600">{res.overall[k].success.mean.toFixed(0)}% of plans fully valid</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="border-t border-stone-900/15 pt-4 text-2xl text-stone-900">How a plan is made</h2>
        <ol className="mt-5 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map(([t, d], i) => (
            <li key={t}>
              <p className="font-mono text-xs text-teal-800">{String(i + 1).padStart(2, '0')}</p>
              <p className="mt-1 font-medium text-stone-900">{t}</p>
              <p className="mt-1 text-sm leading-relaxed text-stone-600">{d}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
