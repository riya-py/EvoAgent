import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const LINE_COLORS = ['#d4a73a', '#6e8b5d', '#c4432e', '#7590c4', '#b378c4', '#4a5568', '#8fa3ad', '#c48f4a']

// Reshape per-agent score_history arrays into one row per round_number
// with a column per personality, which is what recharts wants.
function buildChartData(agents) {
  const roundNumbers = new Set()
  agents.forEach((a) => a.score_history.forEach((p) => roundNumbers.add(p.round_number)))
  const sorted = [...roundNumbers].sort((a, b) => a - b)

  return sorted.map((round) => {
    const row = { round }
    agents.forEach((a) => {
      const point = a.score_history.find((p) => p.round_number === round)
      if (point) row[a.personality_name] = point.score
    })
    return row
  })
}

export default function ScoreHistoryChart({ agents }) {
  const withHistory = agents.filter((a) => a.score_history.length > 0)
  if (withHistory.length === 0) {
    return <div className="eyebrow">No score history yet — run a round to see trends.</div>
  }

  const data = buildChartData(withHistory)

  return (
    <div className="card" style={{ padding: '1rem 1.2rem', height: 320 }}>
      <div className="eyebrow" style={{ marginBottom: '0.6rem' }}>
        Score by round
      </div>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 0, left: -10 }}>
          <CartesianGrid stroke="var(--void-line)" strokeDasharray="3 3" />
          <XAxis
            dataKey="round"
            tick={{ fill: 'var(--chalk-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
            label={{ value: 'Round', position: 'insideBottom', offset: -2, fill: 'var(--chalk-dim)', fontSize: 11 }}
          />
          <YAxis domain={[0, 10]} tick={{ fill: 'var(--chalk-dim)', fontSize: 11, fontFamily: 'var(--font-mono)' }} />
          <Tooltip
            contentStyle={{ background: 'var(--void-raised)', border: '1px solid var(--void-line)', fontSize: 12 }}
            labelStyle={{ color: 'var(--chalk)' }}
          />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} />
          {withHistory.map((agent, i) => (
            <Line
              key={agent.agent_id}
              type="monotone"
              dataKey={agent.personality_name}
              stroke={LINE_COLORS[i % LINE_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}