/**
 * Shows the EliminationRecord for a round (agent, final score, reason).
 * Renders nothing when nobody's been eliminated yet (e.g. round 1 in
 * progress, or no rounds run at all).
 */
export default function EliminationCard({ eliminated }) {
  if (!eliminated) return null

  return (
    <div
      className="card"
      style={{ padding: '0.9rem 1.2rem', borderColor: 'var(--ember)' }}
    >
      <div className="eyebrow" style={{ marginBottom: '0.35rem', color: 'var(--ember)' }}>
        Eliminated · round {eliminated.round_number}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.7rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 15, fontFamily: 'var(--font-display)' }}>{eliminated.personality_name}</span>
        <span className="mono" style={{ fontSize: 13, color: 'var(--chalk-dim)' }}>
          final score {eliminated.final_score.toFixed(1)}
        </span>
      </div>
      {eliminated.reason && (
        <p style={{ margin: '0.4rem 0 0', fontSize: 13, color: 'var(--chalk-dim)', lineHeight: 1.5 }}>
          {eliminated.reason}
        </p>
      )}
    </div>
  )
}