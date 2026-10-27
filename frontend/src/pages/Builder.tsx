import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import WorldMap from '../components/WorldMap'
import type { EdgeT, Group, NodeT, ScenarioData, Team } from '../types'

const CAPS = ['medical', 'fire', 'rescue', 'logistics']
const NTYPES = ['intersection', 'residential', 'hospital', 'shelter', 'hazard']

export default function Builder({ onSaved }: { onSaved: (id: string) => void }) {
  const [nodes, setNodes] = useState<NodeT[]>([])
  const [edges, setEdges] = useState<EdgeT[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [events, setEvents] = useState<any[]>([])
  const [name, setName] = useState('My scenario')
  const [ntype, setNtype] = useState('intersection')
  const [from, setFrom] = useState<string | null>(null)
  const [mode, setMode] = useState<'node' | 'edge'>('node')
  const [err, setErr] = useState('')

  const load = async () => { const s: ScenarioData = await api.scenario('S1'); setNodes(s.nodes); setEdges(s.edges); setTeams(s.teams); setGroups(s.groups); setEvents(s.events); setName('Edited ' + s.name) }
  const mk = (a: NodeT, b: NodeT): EdgeT => { const d = Math.hypot(a.x - b.x, a.y - b.y); return { a: a.id, b: b.id, cost: +(d * 0.5).toFixed(1), time: +(d * 0.32 + 2).toFixed(1), risk: 0.1, status: 'open', damage_rate: 0.05 } }
  const nextId = () => 'v' + (Math.max(0, ...nodes.map(n => +n.id.slice(1))) + 1)

  const addNode = (x: number, y: number) => {
    if (mode !== 'node' || x < 0 || y < 0 || x > 100 || y > 100) return
    const id = nextId()
    const label = { hospital: 'Hospital', shelter: 'Shelter', hazard: 'Hazard Zone', residential: 'District', intersection: 'Junction' }[ntype]! + ' ' + id.slice(1)
    setNodes([...nodes, { id, label, type: ntype, x: +x.toFixed(1), y: +y.toFixed(1), severity: ntype === 'hazard' ? 0.9 : 0.2, hazard: false }])
  }
  const pick = (n: NodeT) => {
    if (mode !== 'edge') return
    if (!from) return setFrom(n.id)
    if (from !== n.id && !edges.some(e => (e.a === from && e.b === n.id) || (e.b === from && e.a === n.id))) setEdges([...edges, mk(nodes.find(x => x.id === from)!, n)])
    setFrom(null)
  }
  const sites = nodes.filter(n => n.type === 'residential' || n.type === 'intersection')
  const addTeam = () => nodes[0] && setTeams([...teams, { id: 'T' + (teams.length + 1), name: ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot'][teams.length % 6] + ' Team', base: nodes[0].id, capacity: 2, capabilities: ['rescue', 'medical'] }])
  const addGroup = () => sites[0] && setGroups([...groups, { id: 'G' + (groups.length + 1), label: 'Group ' + (groups.length + 1), location: sites[0].id, priority: 3, size: 20, needs: ['rescue'], window: [120 + groups.length * 20, 160 + groups.length * 20] }])
  const upd = <T,>(arr: T[], i: number, patch: Partial<T>, set: (a: T[]) => void) => set(arr.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  const tog = (list: string[], c: string) => (list.includes(c) ? list.filter(x => x !== c) : [...list, c])

  const problems = useMemo(() => {
    const p: string[] = []
    if (!nodes.some(n => n.type === 'hospital' || n.type === 'shelter')) p.push('Add a hospital or shelter')
    if (!teams.length) p.push('Add at least one team')
    if (!groups.length) p.push('Add at least one group')
    if (nodes.length && edges.length < nodes.length - 1) p.push('Connect the roads (need at least ' + (nodes.length - 1) + ')')
    return p
  }, [nodes, edges, teams, groups])
  useEffect(() => { setErr('') }, [nodes, edges, teams, groups])

  const save = async () => {
    const id = 'C' + Date.now().toString().slice(-5)
    const s = { id, name, description: `Custom scenario · ${nodes.length} locations`, objective: 'Evacuate all groups to the nearest hospital or safe zone', nodes, edges, teams, groups, events }
    try { await api.save(s); onSaved(id) } catch (e: any) { setErr(e.message) }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={name} onChange={e => setName(e.target.value)} className="rounded-lg border border-stone-900/10 bg-ink-800 px-3 py-2 text-sm" />
          <div className="flex rounded-lg border border-stone-900/10 p-0.5">{(['node', 'edge'] as const).map(m => <button key={m} onClick={() => { setMode(m); setFrom(null) }} className={`rounded-md px-3 py-1.5 text-sm ${mode === m ? 'bg-stone-900/10 text-stone-900' : 'text-stone-600'}`}>{m === 'node' ? 'Place location' : 'Connect roads'}</button>)}</div>
          {mode === 'node' && <select value={ntype} onChange={e => setNtype(e.target.value)} className="rounded-lg border border-stone-900/10 bg-ink-800 px-3 py-2 text-sm">{NTYPES.map(t => <option key={t}>{t}</option>)}</select>}
          <button className="btn btn-ghost" onClick={load}>Start from S1</button>
          <button className="btn btn-ghost" onClick={() => { setNodes([]); setEdges([]); setTeams([]); setGroups([]); setEvents([]) }}>Clear</button>
        </div>
        <div className="card aspect-square max-h-[680px] overflow-hidden bg-ink-950/40">
          <WorldMap nodes={nodes} edges={edges} teams={teams} groups={groups} onBackground={addNode} tool={mode === 'edge' ? 'pick' : 'none'} onNode={pick} />
        </div>
        <p className="text-xs text-stone-500">{mode === 'node' ? 'Click the map to place a location.' : from ? 'Now click the second location.' : 'Click two locations to build a road between them.'}</p>
      </div>
      <div className="space-y-4">
        <div className="card space-y-3 p-4">
          <div className="flex items-center justify-between"><p className="label">Rescue teams</p><button className="btn btn-ghost !py-1" onClick={addTeam}>+ Team</button></div>
          {teams.map((t, i) => <div key={t.id} className="space-y-1.5 rounded-xl border border-stone-900/10 p-2.5 text-sm">
            <div className="flex gap-2"><select value={t.base} onChange={e => upd(teams, i, { base: e.target.value }, setTeams)} className="flex-1 rounded-md border border-stone-900/10 bg-ink-800 px-2 py-1 text-xs">{nodes.map(n => <option key={n.id} value={n.id}>{t.name} @ {n.label}</option>)}</select>
              <input type="number" min={1} max={9} value={t.capacity} onChange={e => upd(teams, i, { capacity: +e.target.value }, setTeams)} className="w-12 rounded-md border border-stone-900/10 bg-ink-800 px-1 py-1 text-center text-xs" /></div>
            <div className="flex flex-wrap gap-1">{CAPS.map(c => <button key={c} onClick={() => upd(teams, i, { capabilities: tog(t.capabilities, c) }, setTeams)} className={`rounded px-2 py-0.5 text-[11px] ${t.capabilities.includes(c) ? 'bg-teal-700/20 text-teal-800' : 'bg-stone-900/5 text-stone-500'}`}>{c}</button>)}</div></div>)}
        </div>
        <div className="card space-y-3 p-4">
          <div className="flex items-center justify-between"><p className="label">Target groups</p><button className="btn btn-ghost !py-1" onClick={addGroup}>+ Group</button></div>
          {groups.map((g, i) => <div key={g.id} className="space-y-1.5 rounded-xl border border-stone-900/10 p-2.5 text-xs">
            <div className="flex gap-2"><select value={g.location} onChange={e => upd(groups, i, { location: e.target.value }, setGroups)} className="flex-1 rounded-md border border-stone-900/10 bg-ink-800 px-2 py-1">{sites.map(n => <option key={n.id} value={n.id}>{g.label} @ {n.label}</option>)}</select>
              <input type="number" value={g.window[0]} onChange={e => upd(groups, i, { window: [+e.target.value, g.window[1]] }, setGroups)} className="w-14 rounded-md border border-stone-900/10 bg-ink-800 px-1 py-1 text-center" />
              <input type="number" value={g.window[1]} onChange={e => upd(groups, i, { window: [g.window[0], +e.target.value] }, setGroups)} className="w-14 rounded-md border border-stone-900/10 bg-ink-800 px-1 py-1 text-center" /></div>
            <div className="flex flex-wrap gap-1">{CAPS.map(c => <button key={c} onClick={() => upd(groups, i, { needs: tog(g.needs, c) }, setGroups)} className={`rounded px-2 py-0.5 text-[11px] ${g.needs.includes(c) ? 'bg-rose-700/20 text-rose-800' : 'bg-stone-900/5 text-stone-500'}`}>{c}</button>)}</div></div>)}
        </div>
        {problems.length > 0 && <ul className="space-y-1 text-xs text-amber-700">{problems.map(p => <li key={p}>• {p}</li>)}</ul>}
        {err && <p className="text-xs text-rose-700">{err}</p>}
        <button className="btn btn-primary w-full" disabled={problems.length > 0} onClick={save}>Save &amp; plan in Mission Control →</button>
      </div>
    </div>
  )
}

