export default function AnswerCard({ row }) {
  return (
    <div className="card" style={{ padding: '1rem 1.15rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <h3 style={{ fontSize: 15 }}>{row.personality_name}</h3>
        <span className="mono" style={{ fontSize: 18, color: 'var(--gold)' }}>
          {row.score.toFixed(1)}
        </span>
      </div>
      <div className="eyebrow">{row.model}</div>

      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--chalk)' }}>{row.answer}</p>

      {row.critiques.length > 0 && (
        <div style={{ borderTop: '1px solid var(--void-line)', paddingTop: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {row.critiques.map((c, i) => (
            <div key={i} style={{ fontSize: 12 }}>
              <span className="mono" style={{ color: 'var(--steel)' }}>
                {c.judge_name}:{' '}
              </span>
              <span style={{ color: 'var(--chalk-dim)' }}>{c.critique}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
