/**
 * The dashboard's one recurring signature motif: a short dashed thread
 * with a gold node (the eliminated parent) and a moss node (the
 * newborn), used wherever we show "X evolved into Y". Reused verbatim
 * on the future Evolution Tree page (Phase 19) so lineage always reads
 * the same way across the app.
 */
export default function LineageThread({ parentName, childName }) {
  return (
    <div
      className="card"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.9rem',
        padding: '0.9rem 1.2rem',
      }}
    >
      <svg width="64" height="20" viewBox="0 0 64 20" aria-hidden="true">
        <circle cx="6" cy="10" r="5" fill="var(--gold)" />
        <line x1="11" y1="10" x2="53" y2="10" stroke="var(--void-line)" strokeWidth="2" strokeDasharray="4 4" />
        <circle cx="58" cy="10" r="5" fill="var(--moss)" />
      </svg>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
        <span style={{ color: 'var(--gold)' }}>{parentName}</span>
        <span style={{ color: 'var(--chalk-dim)' }}> evolved into </span>
        <span style={{ color: 'var(--moss)' }}>{childName}</span>
      </div>
    </div>
  )
}
