import { useEffect, useState } from 'react'
import { api } from '../api'
import AnalyticsTable from '../components/AnalyticsTable.jsx'
import ScoreHistoryChart from '../components/ScoreHistoryChart.jsx'

export default function AnalyticsPage() {
  const [agents, setAgents] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    api.agents().then(setAgents).catch((err) => setError(err.message))
  }, [])

  const rows = [...agents].sort((a, b) => (b.latest_score ?? -1) - (a.latest_score ?? -1))

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div>
        <h2 style={{ fontSize: 22 }}>Leaderboard &amp; Analytics</h2>
        <div className="eyebrow" style={{ marginTop: '0.3rem' }}>
          Every personality this arena has ever fielded, active or eliminated.
        </div>
      </div>

      {error && <div style={{ color: 'var(--ember)' }}>{error}</div>}

      <AnalyticsTable rows={rows} />
      <ScoreHistoryChart agents={agents} />
    </div>
  )
}