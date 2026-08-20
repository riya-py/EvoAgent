export default function Leaderboard({ leaderboard }) {
  if (!leaderboard || leaderboard.entries.length === 0) return null

  return (
    <div className="card" style={{ padding: '1rem 1.2rem' }}>
      <div className="eyebrow" style={{ marginBottom: '0.6rem' }}>
        Leaderboard · round {leaderboard.round_number}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
        <thead>
          <tr style={{ color: 'var(--chalk-dim)', textAlign: 'left', fontSize: 11, textTransform: 'uppercase' }}>
            <th style={{ padding: '0.3rem 0.5rem' }}>#</th>
            <th style={{ padding: '0.3rem 0.5rem' }}>Agent</th>
            <th style={{ padding: '0.3rem 0.5rem' }}>Score</th>
            <th style={{ padding: '0.3rem 0.5rem' }}>Accuracy</th>
            <th style={{ padding: '0.3rem 0.5rem' }}>Reasoning</th>
            <th style={{ padding: '0.3rem 0.5rem' }}>Utility</th>
          </tr>
        </thead>
        <tbody>
          {leaderboard.entries.map((entry, i) => (
            <tr
              key={entry.agent_id}
              style={{
                borderTop: '1px solid var(--void-line)',
                color: i === leaderboard.entries.length - 1 ? 'var(--ember)' : 'var(--chalk)',
              }}
            >
              <td style={{ padding: '0.4rem 0.5rem', color: entry.rank === 1 ? 'var(--gold)' : 'inherit' }}>
                {entry.rank}
              </td>
              <td style={{ padding: '0.4rem 0.5rem', fontFamily: 'var(--font-body)' }}>{entry.personality_name}</td>
              <td style={{ padding: '0.4rem 0.5rem' }}>{entry.score.toFixed(1)}</td>
              <td style={{ padding: '0.4rem 0.5rem' }}>{entry.avg_accuracy.toFixed(1)}</td>
              <td style={{ padding: '0.4rem 0.5rem' }}>{entry.avg_reasoning.toFixed(1)}</td>
              <td style={{ padding: '0.4rem 0.5rem' }}>{entry.avg_utility.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
