import { useMemo } from 'react'
import type { Action, Group, NodeT, EdgeT, Team, Violation } from '../types'
import { TEAM_COLORS } from '../types'

type Props = {
  nodes: NodeT[]; edges: EdgeT[]; teams: Team[]; groups: Group[]
  actions?: Action[]; violations?: Violation[]; selected?: string | null
  live?: boolean; tool?: 'none' | 'block' | 'hazard' | 'pick'
  onSelect?: (id: string | null) => void; onEdge?: (e: EdgeT) => void; onNode?: (n: NodeT) => void
  onBackground?: (x: number, y: number) => void
}

const glyph: Record<string, string> = { hospital: '+', shelter: '⌂', hazard: '!', residential: '', intersection: '' }

export default function WorldMap(p: Props) {
  const byId = useMemo(() => Object.fromEntries(p.nodes.map(n => [n.id, n])), [p.nodes])
  const teamIdx = useMemo(() => Object.fromEntries(p.teams.map((t, i) => [t.id, i])), [p.teams])
  const badEdges = useMemo(() => {
    const s = new Set<string>()
    p.violations?.forEach(v => { if (v.type === 'BLOCKED_ROUTE') s.add(v.entity.split('-').sort().join('|')) })
    return s
  }, [p.violations])
  const badActions = useMemo(() => new Set((p.violations ?? []).map(v => v.action).filter(Boolean) as string[]), [p.violations])
  const groupAt = useMemo(() => {
    const m: Record<string, Group[]> = {}
    p.groups.forEach(g => (m[g.location] ??= []).push(g))
    return m
  }, [p.groups])
  const pts = (path: string[]) => path.map(id => byId[id]).filter(Boolean).map(n => `${n.x},${n.y}`)
  const routes = (p.actions ?? []).filter(a => a.type === 'route' && a.path)

  return (
    <svg viewBox="-4 -4 108 108" className="h-full w-full select-none" onClick={e => {
      if (!p.onBackground) return
      const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
      p.onBackground(((e.clientX - r.left) / r.width) * 108 - 4, ((e.clientY - r.top) / r.height) * 108 - 4)
    }}>
      <defs>
        <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M10 0H0V10" fill="none" stroke="rgba(90,60,20,.08)" strokeWidth=".3" /></pattern>
        <radialGradient id="haz"><stop offset="0" stopColor="#d97706" stopOpacity=".35" /><stop offset="1" stopColor="#d97706" stopOpacity="0" /></radialGradient>
      </defs>
      <rect x="-4" y="-4" width="108" height="108" fill="url(#grid)" />
      {p.nodes.filter(n => n.type === 'hazard' || n.hazard).map(n => (
        <g key={'h' + n.id}><circle cx={n.x} cy={n.y} r="17" fill="url(#haz)" /><circle cx={n.x} cy={n.y} r="5" fill="none" stroke="#f59e0b" strokeWidth=".4" style={{ transformOrigin: `${n.x}px ${n.y}px`, animation: 'pulse-ring 2.2s ease-out infinite' }} /></g>
      ))}
      {/* roads */}
      {p.edges.map(e => {
        const a = byId[e.a], b = byId[e.b]
        const key = [e.a, e.b].sort().join('|')
        const color = e.status === 'blocked' ? '#b91c1c' : e.status === 'damaged' ? '#d97706' : 'rgba(120,95,60,.45)'
        return (
          <g key={key} className={p.tool === 'block' ? 'cursor-crosshair' : ''} onClick={ev => { if (p.tool === 'block') { ev.stopPropagation(); p.onEdge?.(e) } }}>
            {badEdges.has(key) && <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#b91c1c" strokeWidth="3.2" strokeOpacity=".25" />}
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth={e.status === 'open' ? 0.7 : 1.1} strokeDasharray={e.status === 'blocked' ? '2 1.6' : e.status === 'damaged' ? '3 1' : undefined} />
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth="4" />
            {e.status === 'blocked' && <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 + 1.2} fontSize="3.4" textAnchor="middle" fill="#b91c1c" fontWeight="700">×</text>}
          </g>
        )
      })}
      {/* planned routes */}
      {routes.map(a => {
        const ci = teamIdx[a.team] ?? 0
        const col = TEAM_COLORS[ci % TEAM_COLORS.length]
        const bad = badActions.has(a.id)
        const dim = p.selected && p.selected !== a.id
        const pl = pts(a.path!)
        const dash = a.leg === 'evacuate'
        return (
          <g key={a.id} opacity={dim ? 0.18 : 1} className="cursor-pointer" onClick={ev => { ev.stopPropagation(); p.onSelect?.(a.id === p.selected ? null : a.id) }}>
            <polyline points={pl.join(' ')} fill="none" stroke={bad ? '#b91c1c' : col} strokeWidth={p.selected === a.id ? 1.8 : 1.2} strokeLinecap="round" strokeLinejoin="round" strokeOpacity={bad ? 0.95 : 0.85} className={dash ? 'flow' : ''} strokeDasharray={dash ? '1.6 1.6' : undefined} />
            <polyline points={pl.join(' ')} fill="none" stroke="transparent" strokeWidth="3.5" />
            {p.live && a.path!.length > 1 && !dim && (
              <circle r="1.4" fill={bad ? '#b91c1c' : col}>
                <animateMotion dur={`${3 + a.path!.length * 0.8}s`} repeatCount="indefinite" path={'M' + pl.join(' L')} />
              </circle>
            )}
          </g>
        )
      })}
      {/* nodes */}
      {p.nodes.map(n => {
        const isH = n.type === 'hospital', isS = n.type === 'shelter', isZ = n.type === 'hazard' || n.hazard
        const base = p.teams.filter(t => t.base === n.id)
        const fill = isZ ? '#d97706' : isH ? '#0f766e' : isS ? '#0369a1' : n.type === 'residential' ? '#d9c9a4' : '#a99f8c'
        const r = isH || isS || isZ ? 3.1 : n.type === 'residential' ? 2.4 : 1.5
        return (
          <g key={n.id} className={p.tool === 'hazard' || p.tool === 'pick' ? 'cursor-pointer' : ''} onClick={ev => { if (p.tool === 'hazard' || p.tool === 'pick') { ev.stopPropagation(); p.onNode?.(n) } }}>
            <circle cx={n.x} cy={n.y} r={r} fill={fill} stroke="#fbf4e4" strokeWidth=".6" />
            {glyph[isZ ? 'hazard' : n.type] && <text x={n.x} y={n.y + 1.35} fontSize="3.6" textAnchor="middle" fill="#fffaf0" fontWeight="800">{glyph[isZ ? 'hazard' : n.type]}</text>}
            {(isH || isS || isZ || n.type === 'residential') && <text x={n.x} y={n.y + r + 3.6} fontSize="2.8" textAnchor="middle" fill="#44403c" paintOrder="stroke" stroke="#fbf4e4" strokeWidth=".5">{n.label}</text>}
            {groupAt[n.id] && (
              <g><circle cx={n.x + 3} cy={n.y - 3} r="1.9" fill="#be123c" stroke="#fbf4e4" strokeWidth=".4" /><text x={n.x + 3} y={n.y - 2.1} fontSize="2.4" textAnchor="middle" fill="#fffaf0" fontWeight="800">{groupAt[n.id].length}</text></g>
            )}
            {base.map((t, i) => (
              <rect key={t.id} x={n.x - 4.2 + i * 3.2} y={n.y + r + 4.6} width="2.6" height="2.6" rx=".6" fill={TEAM_COLORS[teamIdx[t.id] % TEAM_COLORS.length]} />
            ))}
          </g>
        )
      })}
    </svg>
  )
}
