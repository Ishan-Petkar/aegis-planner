import { useState } from 'react'
import { motion } from 'framer-motion'
import Overview from './pages/Overview'
import MissionControl from './pages/MissionControl'
import Builder from './pages/Builder'
import Experiments from './pages/Experiments'
import Method from './pages/Method'

const TABS = [['overview', 'Overview'], ['mission', 'Mission Control'], ['builder', 'Scenario Builder'], ['experiments', 'Experiments'], ['method', 'Method']] as const
type Tab = typeof TABS[number][0]

export default function App() {
  const fromHash = (): Tab => {
    const h = window.location.hash.replace('#', '').split('?')[0]
    return (TABS.find(t => t[0] === h)?.[0] ?? 'overview') as Tab
  }
  const [tab, setTabState] = useState<Tab>(fromHash)
  const setTab = (t: Tab) => { window.location.hash = t; setTabState(t) }
  const [custom, setCustom] = useState<string | null>(null)
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-stone-900/10 bg-ink-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center gap-4 px-4 py-3 sm:px-6">
          <button onClick={() => setTab('overview')} className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-teal-700 to-teal-900 text-amber-50">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 4 6v6c0 5 3.4 8 8 9 4.6-1 8-4 8-9V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></svg>
            </span>
            <span className="hidden text-lg font-semibold tracking-tight sm:inline">AEGIS</span>
          </button>
          <nav className="ml-1 flex min-w-0 gap-0.5 overflow-x-auto [scrollbar-width:none] sm:ml-2 sm:gap-1">
            {TABS.map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)} className={`relative shrink-0 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm transition sm:px-3 ${tab === id ? 'text-stone-900' : 'text-stone-600 hover:text-stone-900'}`}>
                {tab === id && <motion.span layoutId="nav" className="absolute inset-0 rounded-lg bg-stone-900/10" />}
                <span className="relative">{label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6">
        {tab === 'overview' && <Overview go={t => setTab(t as Tab)} />}
        {tab === 'mission' && <MissionControl initial={custom} />}
        {tab === 'builder' && <Builder onSaved={id => { setCustom(id); setTab('mission') }} />}
        {tab === 'experiments' && <Experiments />}
        {tab === 'method' && <Method />}
      </main>
    </div>
  )
}
