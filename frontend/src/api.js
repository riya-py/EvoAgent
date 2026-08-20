const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const WS_BASE = API_BASE.replace(/^http/, 'ws')

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  askQuestion: (question) =>
    request('/api/arena/question', { method: 'POST', body: JSON.stringify({ question }) }),
  current: () => request('/api/arena/current'),
  agents: () => request('/api/agents'),
  agent: (agentId) => request(`/api/agents/${encodeURIComponent(agentId)}`),
  rounds: () => request('/api/rounds'),
  round: (roundNumber) => request(`/api/rounds/${roundNumber}`),
  leaderboard: () => request('/api/leaderboard'),
  evolution: () => request('/api/evolution'),
}

export function arenaSocketUrl() {
  return `${WS_BASE}/api/ws/arena`
}
