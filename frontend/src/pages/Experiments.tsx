import { useEffect, useState } from 'react'
import { Bar, BarChart, Cell, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, ErrorBar } from 'recharts'
import { api } from '../api'

const COL: Record<string, string> = { baseline: '#b9462f', solvers: '#c08a2e', full: '#0f766e' }
const ROWS: [string, string][] = [['Planning success rate (%)', 'success'], ['Constraint violations / plan', 'violations'], ['Route cost (composite)', 'route_cost'], ['Planning time (ms)', 'planning_ms'], ['Replanning time (ms)', 'replanning_ms'], ['Unsafe decisions / plan', 'unsafe'], ['Resource utilization (%)', 'utilization']]
const fmt = (a: any) => (a ? `${a.mean} ± ${a.std}` : '–')

function Chart({ title, k, res }: { title: string; k: string; res: any }) {
  const data = Object.keys(res.conditions).map(c => ({ name: res.conditions[c], c, v: res.overall[c][k]?.mean ?? 0, e: res.overall[c][k]?.std ?? 0 }))
  return (
    <div className="card p-4"><p className="mb-2 text-sm font-medium">{title}</p>
      <div className="h-52"><ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="rgba(90,60,20,.10)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#78716c', fontSize: 11 }} tickFormatter={(v: string) => v.split(' ')[0] === 'Baseline' ? 'Baseline' : v} />
          <YAxis domain={[0, 'auto']} allowDataOverflow tickFormatter={(v: number) => String(Math.round(v * 10) / 10)} tick={{ fill: '#78716c', fontSize: 11 }} />
          <Tooltip contentStyle={{ background: '#fffaf0', border: '1px solid rgba(90,60,20,.15)', borderRadius: 8 }} cursor={{ fill: 'rgba(90,60,20,.05)' }} />
          <Bar dataKey="v" radius={[6, 6, 0, 0]} fill="#0f766e" isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={COL[d.c]} />)}
            <ErrorBar dataKey="e" stroke="#57534e" width={4} />
          </Bar>
        </BarChart></ResponsiveContainer></div></div>
  )
}

export default function Experiments() {
  const [res, setRes] = useState<any>(null)
  const [st, setSt] = useState<any>({ status: 'idle', progress: 0, total: 1 })
  useEffect(() => { api.expResults().then(setRes) }, [])
  useEffect(() => {
    if (st.status !== 'running') return
    const t = setInterval(async () => {
      const s = await api.expStatus(); setSt(s)
      if (s.status === 'done') { setRes(await api.expResults()); clearInterval(t) }
    }, 500)
    return () => clearInterval(t)
  }, [st.status])
  const start = async () => setSt(await api.expRun())
  const maxV = res ? Math.max(...Object.keys(res.conditions).flatMap((c: string) => res.scenarios.map((s: any) => res.by_scenario[c][s.id].violations.mean))) || 1 : 1
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ablation study</h1>
          <p className="mt-1 max-w-2xl text-sm text-stone-600">6 scenarios × 3 planners × 5 seeded runs, each with scripted mid-run events. Violations are counted by the same verification engine for every planner, after the run.</p></div>
        <div className="flex items-center gap-3">
          {st.status === 'running' && <div className="h-1.5 w-40 overflow-hidden rounded bg-stone-900/10"><div className="h-full bg-teal-700 transition-all" style={{ width: `${(100 * st.progress) / Math.max(1, st.total)}%` }} /></div>}
          <button className="btn btn-primary" disabled={st.status === 'running'} onClick={start}>{st.status === 'running' ? 'Running…' : res ? 'Re-run experiments' : 'Run experiments'}</button>
        </div>
      </div>
      {!res ? <div className="card grid h-60 place-items-center text-stone-500">Run the experiments to populate the tables.</div> : <>
        <div className="card overflow-x-auto"><p className="px-4 pt-4 text-sm font-medium">Table I — mean ± std. dev. over all runs</p>
          <table className="mt-2 w-full min-w-[640px] text-sm"><thead><tr className="text-left text-stone-600"><th className="px-4 py-2 font-normal">Metric</th>{Object.values(res.conditions).map((n: any) => <th key={n} className="px-4 py-2 font-normal">{n}</th>)}</tr></thead>
            <tbody>{ROWS.map(([n, k]) => <tr key={k} className="border-t border-stone-900/5"><td className="px-4 py-2.5 text-stone-700">{n}</td>{Object.keys(res.conditions).map(c => <td key={c} className={`px-4 py-2.5 font-mono ${c === 'full' ? 'text-teal-700' : ''}`}>{fmt(res.overall[c][k])}</td>)}</tr>)}</tbody></table>
          <p className="px-4 py-3 text-xs text-stone-500">Route cost is scored on the final plan. Invalid routes (missing or blocked roads) are counted at base cost, so a lower cost does not imply a better plan.</p></div>
        <div className="grid gap-3 sm:grid-cols-2 md:gap-4 xl:grid-cols-4">
          <Chart title="Planning success (%)" k="success" res={res} /><Chart title="Constraint violations / plan" k="violations" res={res} />
          <Chart title="Unsafe decisions / plan" k="unsafe" res={res} /><Chart title="Planning time (ms)" k="planning_ms" res={res} />
        </div>
        <div className="card overflow-x-auto p-4"><p className="mb-3 text-sm font-medium">Table II — constraint violations per scenario (mean of 5 runs)</p>
          <table className="w-full min-w-[520px] text-sm"><thead><tr className="text-left text-stone-600"><th className="py-2 font-normal">Scenario</th>{Object.values(res.conditions).map((n: any) => <th key={n} className="py-2 font-normal">{n}</th>)}</tr></thead>
            <tbody>{res.scenarios.map((s: any) => <tr key={s.id} className="border-t border-stone-900/5"><td className="py-2 text-stone-700">{s.id} <span className="text-stone-500">{s.name}</span></td>
              {Object.keys(res.conditions).map(c => { const v = res.by_scenario[c][s.id].violations.mean; return <td key={c} className="py-1.5 pr-3"><div className="rounded-md px-2.5 py-1.5 font-mono" style={{ background: `rgba(${c === 'full' ? '15,118,110' : '185,70,47'},${0.08 + 0.5 * (v / maxV)})` }}>{v}</div></td> })}</tr>)}</tbody></table></div>
        <div className="grid gap-4 md:grid-cols-3">
          {[['Solvers change the picture', 'Replacing direct route and team choices with A* and CSP removes most violations — paths avoid blocked roads and teams always have the needed capability.'], ['Verification closes the gap', 'What remains after the solvers comes from decomposition mistakes. The verification engine catches each one and repair resolves it, bringing hard violations to zero.'], ['Safety costs a little time', 'Full AEGIS spends extra milliseconds on verification and repair — negligible against planning horizons measured in minutes.']].map(([t, d]) =>
            <div key={t} className="card p-4"><p className="font-medium">{t}</p><p className="mt-1.5 text-sm text-stone-600">{d}</p></div>)}</div>
      </>}
    </div>
  )
}
