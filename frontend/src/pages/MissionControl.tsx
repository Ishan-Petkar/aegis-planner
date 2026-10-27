import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { api } from '../api'
import WorldMap from '../components/WorldMap'
import { CONDITIONS, TEAM_COLORS, type EdgeT, type NodeT, type Run, type Violation } from '../types'

type Tool = 'none' | 'block' | 'hazard'
const VCOL: Record<string, string> = { RISK_EXCEEDED: 'bg-amber-600/15 text-amber-700', default: 'bg-rose-700/15 text-rose-700' }
const chip = (t: string) => VCOL[t] ?? VCOL.default

function Metric({ label, value, tone }: { label: string; value: any; tone?: string }) {
  return <div className="card min-w-0 px-3 py-2 sm:px-3.5 sm:py-2.5"><p className="label truncate">{label}</p><p className={`mt-0.5 truncate text-base font-semibold sm:text-xl ${tone ?? ''}`}>{value}</p></div>
}

function MapPanel({ run, step, title, selected, setSelected, live, tool, onEdge, onNode }: any) {
  const s = run.steps[step]
  const sc = run.scenario
  const hard = s.violations.filter((v: Violation) => v.type !== 'RISK_EXCEEDED').length
  return (
    <div className="card relative overflow-hidden">
      <div className="flex items-center justify-between border-b border-stone-900/10 px-4 py-2.5">
        <p className="text-sm font-medium">{title}</p>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${hard === 0 ? 'bg-teal-700/15 text-teal-700' : 'bg-rose-700/15 text-rose-700'}`}>{hard === 0 ? 'Plan verified' : `${hard} violation${hard > 1 ? 's' : ''}`}</span>
      </div>
      <div className="aspect-square max-h-[640px] w-full bg-ink-950/40">
        <WorldMap nodes={s.world.nodes} edges={s.world.edges} teams={sc.teams} groups={sc.groups} actions={s.plan.actions}
          violations={s.violations} selected={selected} onSelect={setSelected} live={live} tool={tool} onEdge={onEdge} onNode={onNode} />
      </div>
    </div>
  )
}

export default function MissionControl({ initial }: { initial: string | null }) {
  const hashArg = (k: string) => new URLSearchParams(window.location.hash.split('?')[1] ?? '').get(k)
  const selKey = useRef('')
  const [list, setList] = useState<any[]>([])
  const [sid, setSid] = useState(initial ?? hashArg('scenario') ?? 'S1')
  const [cond, setCond] = useState('full')
  const [seed, setSeed] = useState(1)
  const [p, setP] = useState({ alpha: 1, beta: 0.5, gamma: 15, tau: 0.55 })
  const [compare, setCompare] = useState(() => hashArg('compare') === '1')
  const [run, setRun] = useState<Run | null>(null)
  const [other, setOther] = useState<Run | null>(null)
  const [step, setStep] = useState(0)
  const [sel, setSel] = useState<string | null>(() => hashArg('select'))
  const [tab, setTab] = useState<'plan' | 'cycle' | 'explain'>('plan')
  const [tool, setTool] = useState<Tool>('none')
  const [live, setLive] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [adv, setAdv] = useState(false)

  useEffect(() => { api.scenarios().then(setList).catch(e => setErr(String(e))) }, [])

  const go = useCallback(async () => {
    setBusy(true); setErr('')
    try {
      const body = { scenario_id: sid, seed, ...p }
      const [a, b] = await Promise.all([api.plan({ ...body, condition: cond }), compare ? api.plan({ ...body, condition: 'baseline' }) : Promise.resolve(null)])
      setRun(a); setOther(b); setStep(0); 
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }, [sid, cond, seed, p, compare])
  useEffect(() => { go() }, [sid, cond, compare]) // eslint-disable-line
  useEffect(() => {
    const k = `${sid}|${cond}`
    if (selKey.current && selKey.current !== k) setSel(null)
    selKey.current = k
  }, [sid, cond])

  const inject = async (body: any) => {
    if (!run) return
    setBusy(true)
    try {
      const [a, b] = await Promise.all([api.event({ run_id: run.run_id, ...body }), other ? api.event({ run_id: other.run_id, ...body }) : Promise.resolve(null)])
      setRun(a); setOther(b); setStep(a.steps.length - 1); setTool('none')
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  const s = run?.steps[Math.min(step, (run?.steps.length ?? 1) - 1)]
  const sc = run?.scenario
  const groups = useMemo(() => {
    if (!s || !sc) return []
    return sc.groups.map(g => ({ g, acts: s.plan.actions.filter(a => a.group === g.id) }))
  }, [s, sc])
  const selExp = s && sel ? s.explanations[sel] : null
  useEffect(() => { if (sel) setTab('explain') }, [sel])
  const teamName = (id: string) => sc?.teams.find(t => t.id === id)?.name ?? id
  const hard = s ? s.violations.filter(v => v.type !== 'RISK_EXCEEDED') : []
  const unsafe = s ? s.violations.length - hard.length : 0

  return (
    <div className="grid gap-4 sm:gap-5 xl:grid-cols-[272px_minmax(0,1fr)_360px]">
      {/* controls */}
      <aside className="order-2 space-y-4 xl:order-1">
        <div className="card space-y-4 p-4">
          <div><p className="label mb-1.5">Scenario</p>
            <select value={sid} onChange={e => setSid(e.target.value)} className="w-full rounded-lg border border-stone-900/10 bg-ink-800 px-3 py-2 text-sm">
              {list.map(s => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}
            </select>
            {list.find(x => x.id === sid) && <p className="mt-1.5 text-xs text-stone-500">{list.find(x => x.id === sid).description}</p>}
          </div>
          <div><p className="label mb-1.5">Planner</p>
            <div className="grid gap-1.5">{Object.entries(CONDITIONS).map(([k, v]) => (
              <button key={k} onClick={() => setCond(k)} className={`rounded-lg border px-3 py-2 text-left text-sm transition ${cond === k ? 'border-teal-700/60 bg-teal-700/10 text-stone-900' : 'border-stone-900/10 text-stone-600 hover:bg-stone-900/5'}`}>{v}</button>))}</div>
          </div>
          <label className="flex items-center justify-between text-sm"><span>Side-by-side vs Baseline</span>
            <input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} className="h-4 w-4 accent-teal-700" /></label>
          <div className="flex items-center justify-between text-sm"><span>Run seed</span>
            <input type="number" value={seed} min={1} max={99} onChange={e => setSeed(+e.target.value)} className="w-16 rounded-lg border border-stone-900/10 bg-ink-800 px-2 py-1 text-right" /></div>
          <button className="text-left text-xs text-stone-600 hover:text-stone-900" onClick={() => setAdv(!adv)}>{adv ? '▾' : '▸'} Cost &amp; risk settings</button>
          {adv && (['alpha', 'beta', 'gamma', 'tau'] as const).map(k => (
            <div key={k}><div className="flex justify-between text-xs"><span className="text-stone-600">{{ alpha: 'α cost', beta: 'β time', gamma: 'γ risk', tau: 'τ risk ceiling' }[k]}</span><span className="font-mono">{p[k]}</span></div>
              <input type="range" min={0} max={k === 'gamma' ? 40 : k === 'tau' ? 1 : 3} step={k === 'tau' ? 0.05 : 0.5} value={p[k]} onChange={e => setP({ ...p, [k]: +e.target.value })} className="w-full accent-teal-700" /></div>))}
          <button className="btn btn-primary w-full" disabled={busy} onClick={go}>{busy ? 'Planning…' : 'Run planner'}</button>
          {err && <p className="text-xs text-rose-700">{err}</p>}
        </div>
        <div className="card space-y-2 p-4">
          <p className="label">Inject live event</p>
          <p className="text-xs text-stone-500">Pick a tool, then click the map. The plan is re-evaluated against the new world.</p>
          <div className="grid grid-cols-2 gap-2">
            <button className={`btn ${tool === 'block' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTool(tool === 'block' ? 'none' : 'block')}>Block road</button>
            <button className={`btn ${tool === 'hazard' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTool(tool === 'hazard' ? 'none' : 'hazard')}>New hazard</button>
          </div>
          <label className="flex items-center justify-between pt-1 text-sm"><span>Live run playback</span>
            <input type="checkbox" checked={live} onChange={e => setLive(e.target.checked)} className="h-4 w-4 accent-teal-700" /></label>
        </div>
        {sc && <div className="card p-4"><p className="label mb-2">Teams</p>
          <div className="space-y-1.5">{sc.teams.map((t, i) => <div key={t.id} className="flex items-center gap-2 text-sm"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: TEAM_COLORS[i % 4] }} /><span>{t.name}</span><span className="ml-auto text-xs text-stone-500">cap {t.capacity} · {t.capabilities.join(', ')}</span></div>)}</div></div>}
      </aside>

      {/* center */}
      <section className="order-1 min-w-0 space-y-4 xl:order-2">
        <div className="flex gap-2 xl:hidden">
          <select value={sid} onChange={e => setSid(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-stone-900/10 bg-ink-800 px-3 py-2 text-sm">
            {list.map(s => <option key={s.id} value={s.id}>{s.id} · {s.name}</option>)}
          </select>
          <select value={cond} onChange={e => setCond(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-stone-900/10 bg-ink-800 px-3 py-2 text-sm">
            {Object.entries(CONDITIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {run && s && sc ? <>
          <div className="grid grid-cols-3 gap-2 md:grid-cols-5 md:gap-3">
            <Metric label="Status" value={hard.length === 0 ? 'Valid' : 'Invalid'} tone={hard.length === 0 ? 'text-teal-700' : 'text-rose-700'} />
            <Metric label="Violations" value={hard.length} tone={hard.length ? 'text-rose-700' : ''} />
            <Metric label="Unsafe" value={unsafe} tone={unsafe ? 'text-amber-700' : ''} />
            <Metric label={step === 0 ? 'Plan time' : 'Replan'} value={`${(step === 0 ? s.ms : s.replan_ms ?? 0).toFixed(1)} ms`} />
            <Metric label="Repairs" value={Math.max(0, s.trace.length - 1)} />
          </div>
          <div className="-mx-1 flex items-center gap-2 overflow-x-auto px-1 pb-1">
            {run.steps.map((st, i) => (
              <button key={i} onClick={() => setStep(i)} className={`shrink-0 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs transition ${i === step ? 'border-teal-700/60 bg-teal-700/10 text-stone-900' : 'border-stone-900/10 text-stone-600 hover:bg-stone-900/5'}`}>
                {i === 0 ? 'Initial plan' : `t=${st.at} · ${st.label}`}
              </button>))}
          </div>
          <AnimatePresence mode="wait">
            {step > 0 && s.impact.length > 0 && (
              <motion.div key={step} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-xl border border-rose-700/30 bg-rose-700/10 px-4 py-2.5 text-sm text-rose-800">
                {s.event?.description}: the standing plan had {s.impact.length} violation{s.impact.length > 1 ? 's' : ''}.{' '}
                {run.condition === 'baseline' ? 'This planner does not replan.' : `AEGIS replanned in ${s.replan_ms?.toFixed(1)} ms.`}
              </motion.div>)}
          </AnimatePresence>
          <div className={`grid gap-4 ${other ? 'lg:grid-cols-2' : ''}`}>
            {other && other.steps[step] && <MapPanel run={other} step={step} title="Baseline Planner" selected={null} setSelected={() => {}} live={live} tool="none" />}
            <MapPanel run={run} step={step} title={run.condition_name} selected={sel} setSelected={setSel} live={live} tool={tool}
              onEdge={(e: EdgeT) => inject({ kind: 'block', edge: [e.a, e.b] })} onNode={(n: NodeT) => inject({ kind: 'hazard', node: n.id })} />
          </div>
        </> : <div className="card grid h-96 place-items-center text-stone-500">{busy ? 'Planning…' : 'No plan yet'}</div>}
      </section>

      {/* right */}
      <aside className="card order-3 flex min-h-[320px] flex-col overflow-hidden xl:sticky xl:top-20 xl:max-h-[calc(100vh-110px)]">
        <div className="flex border-b border-stone-900/10 text-sm">
          {([['plan', 'Plan'], ['cycle', 'Control loop'], ['explain', 'Explain']] as const).map(([id, l]) => (
            <button key={id} onClick={() => setTab(id)} className={`flex-1 px-3 py-3 transition ${tab === id ? 'border-b-2 border-teal-700 text-stone-900' : 'text-stone-600 hover:text-stone-900'}`}>{l}</button>))}
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
          {s && tab === 'plan' && <>
            {groups.map(({ g, acts }) => (
              <div key={g.id} className="rounded-xl border border-stone-900/10 p-3">
                <div className="flex items-center justify-between"><p className="font-medium">{g.label}</p><span className="text-xs text-stone-500">P{g.priority} · {g.size} people</span></div>
                <p className="mt-0.5 text-xs text-stone-500">needs {g.needs.join(', ')} · window {g.window[0]}–{g.window[1]} min</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {acts.length === 0 && <span className="text-xs text-rose-700">not planned</span>}
                  {acts.map(a => {
                    const bad = s.violations.some(v => v.action === a.id)
                    return <button key={a.id} onClick={() => setSel(a.id)} className={`rounded-md border px-2 py-1 text-xs ${bad ? 'border-rose-700/50 bg-rose-700/10 text-rose-800' : 'border-stone-900/10 bg-stone-900/5 text-stone-700 hover:bg-stone-900/10'} ${sel === a.id ? 'ring-1 ring-teal-700' : ''}`}>
                      {a.type === 'assign' ? teamName(a.team) : a.leg === 'dispatch' ? 'dispatch route' : 'evacuation route'}</button>
                  })}
                </div>
              </div>))}
            {s.violations.length > 0 && <div><p className="label mb-1.5">Violation report</p><div className="space-y-1.5">
              {s.violations.map((v, i) => <div key={i} className="rounded-lg bg-stone-900/5 p-2"><span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${chip(v.type)}`}>{v.type}</span><p className="mt-1 text-xs text-stone-700">{v.detail}</p></div>)}</div></div>}
          </>}
          {s && tab === 'cycle' && <>
            {run?.condition === 'baseline' ? <p className="text-stone-600">The Baseline Planner builds the full plan in one pass. There is no verification or repair stage.</p> : s.trace.map(t => (
              <div key={t.iteration} className="rounded-xl border border-stone-900/10 p-3">
                <div className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-full bg-teal-700/15 font-mono text-xs text-teal-700">{t.iteration}</span>
                  <p className="font-medium">{t.stage === 'repair' ? 'Repair → re-verify' : 'Generate → verify'}</p></div>
                <p className="mt-1.5 text-xs text-stone-600">{t.tasks.length} typed sub-tasks · {t.violations.length === 0 ? 'no violations' : `${t.violations.length} violations`}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">{Array.from(new Set(t.violations.map(v => v.type))).map(x => <span key={x} className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${chip(x)}`}>{x}</span>)}</div>
                <details className="mt-2"><summary className="cursor-pointer text-xs text-stone-500">sub-task JSON</summary>
                  <pre className="mt-1.5 max-h-48 overflow-auto rounded-lg bg-ink-950 p-2 font-mono text-[10px] leading-relaxed text-stone-600">{JSON.stringify(t.tasks.slice(0, 8), null, 1)}{t.tasks.length > 8 ? '\n…' : ''}</pre></details>
              </div>))}
            {run?.condition !== 'baseline' && <div className="rounded-xl border border-teal-700/30 bg-teal-700/5 p-3 text-xs text-teal-800">Execute → plan {hard.length === 0 ? 'released to execution.' : 'failed verification after the maximum repair iterations.'}</div>}
          </>}
          {s && tab === 'explain' && (selExp ? <>
            <p className="font-medium">{selExp.title}</p>
            {selExp.path && <p className="text-xs text-stone-600">{selExp.path.join(' → ')}</p>}
            <div className="grid grid-cols-2 gap-2">{selExp.facts.map(([k, v]) => <div key={k} className="rounded-lg bg-stone-900/5 p-2"><p className="label">{k}</p><p className="font-mono text-sm">{String(v)}</p></div>)}</div>
            {selExp.risk?.R !== undefined && <div><p className="label mb-1">Risk factors</p>
              {(['H', 'D', 'S'] as const).map(k => <div key={k} className="mb-1 flex items-center gap-2 text-xs"><span className="w-24 text-stone-600">{{ H: 'Hazard proximity', D: 'Damage rate', S: 'Severity' }[k]}</span>
                <div className="h-1.5 flex-1 rounded bg-stone-900/10"><div className="h-full rounded bg-amber-600" style={{ width: `${(selExp.risk[k] ?? 0) * 100}%` }} /></div><span className="w-8 text-right font-mono">{selExp.risk[k]}</span></div>)}</div>}
            {selExp.alternatives && selExp.alternatives.length > 0 && <div><p className="label mb-1">Alternatives considered</p>{selExp.alternatives.map((a, i) => <div key={i} className="mb-1 rounded-lg bg-stone-900/5 p-2 text-xs"><p className="text-stone-700">{a.path.join(' → ')}</p><p className="font-mono text-stone-500">composite {a.composite} (+{a.delta})</p></div>)}</div>}
            {selExp.candidates && selExp.candidates.length > 0 && <div><p className="label mb-1">Candidate teams</p>{selExp.candidates.map((c, i) => <div key={i} className={`mb-1 flex justify-between rounded-lg p-2 text-xs ${c.chosen ? 'bg-teal-700/10 text-teal-800' : 'bg-stone-900/5 text-stone-600'}`}><span>{c.team}{c.chosen ? ' ✓' : ''}</span><span className="font-mono">ETA {c.eta} min · cost {c.route_cost}</span></div>)}</div>}
            {selExp.eliminated && selExp.eliminated.length > 0 && <div><p className="label mb-1">Eliminated</p>{selExp.eliminated.map((c, i) => <div key={i} className="mb-1 rounded-lg bg-rose-700/5 p-2 text-xs text-stone-700"><span className="text-rose-700">{c.team}</span> — {c.reason}</div>)}</div>}
            {selExp.violations.length > 0 && <div><p className="label mb-1">Violations</p>{selExp.violations.map((v, i) => <div key={i} className="mb-1 rounded-lg bg-stone-900/5 p-2 text-xs"><span className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${chip(v.type)}`}>{v.type}</span><p className="mt-1 text-stone-700">{v.detail}</p></div>)}</div>}
          </> : <p className="text-stone-600">Click a route on the map, or an item in the plan, to see why AEGIS made that decision.</p>)}
        </div>
      </aside>
    </div>
  )
}
