export default function AnalyticsTable({ rows }) {
  return (
    <div className="card" style={{ padding: '1rem 1.2rem', overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
        <thead>
          <tr style={{ color: 'var(--chalk-dim)', textAlign: 'left', fontSize: 11, textTransform: 'uppercase' }}>
            <th style={cellStyle}>#</th>
            <th style={cellStyle}>Personality</th>
            <th style={cellStyle}>Current</th>
            <th style={cellStyle}>Average</th>
            <th style={cellStyle}>Wins</th>
            <th style={cellStyle}>Losses</th>
            <th style={cellStyle}>Survival</th>
            <th style={cellStyle}>Gen</th>
            <th style={cellStyle}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.agent_id} style={{ borderTop: '1px solid var(--void-line)' }}>
              <td style={{ ...cellStyle, color: i === 0 ? 'var(--gold)' : 'inherit' }}>{i + 1}</td>
              <td style={{ ...cellStyle, fontFamily: 'var(--font-body)' }}>{row.personality_name}</td>
              <td style={cellStyle}>{row.latest_score ?? '—'}</td>
              <td style={cellStyle}>{row.average_score ?? '—'}</td>
              <td style={{ ...cellStyle, color: 'var(--gold)' }}>{row.wins}</td>
              <td style={{ ...cellStyle, color: 'var(--ember)' }}>{row.losses}</td>
              <td style={cellStyle}>{row.rounds_survived}</td>
              <td style={cellStyle}>{row.generation}</td>
              <td style={cellStyle}>
                <span className={`pill ${row.status === 'ACTIVE' ? 'pill--active' : 'pill--eliminated'}`}>
                  {row.status === 'ACTIVE' ? 'Active' : 'Eliminated'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const cellStyle = { padding: '0.45rem 0.6rem' }