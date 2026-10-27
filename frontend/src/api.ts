import type { Run } from './types'
async function j(r: Response) { if (!r.ok) throw new Error((await r.text()) || r.statusText); return r.json() }
export const api = {
  scenarios: () => fetch('/api/scenarios').then(j),
  scenario: (id: string) => fetch(`/api/scenarios/${id}`).then(j),
  plan: (body: any): Promise<Run> => fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j),
  event: (body: any): Promise<Run> => fetch('/api/event', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j),
  save: (s: any) => fetch('/api/scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(s) }).then(j),
  expRun: () => fetch('/api/experiments/run', { method: 'POST' }).then(j),
  expStatus: () => fetch('/api/experiments/status').then(j),
  expResults: () => fetch('/api/experiments/results').then(r => (r.ok ? r.json() : null)),
}
