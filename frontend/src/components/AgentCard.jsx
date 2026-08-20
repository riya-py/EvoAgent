const STATE_BORDER = {
  idle: 'var(--void-line)',
  started: 'var(--gold)',
  completed: 'var(--moss)',
}

/**
 * `liveState` (optional): 'idle' | 'started' | 'completed' — driven by
 * AGENT_STARTED / AGENT_COMPLETED events while a round is in flight.
 * `justEliminated` / `justBorn` add the KO stamp / NEW ribbon signature.
 */
export default function AgentCard({ agent, liveState = 'idle', justEliminated = false, justBorn = false }) {
  const isEliminated = agent.status === 'ELIMINATED'

  return (
    <div
      className="card"
      style={{
        position: 'relative',
        padding: '1rem 1.1rem',
        opacity: isEliminated && !justEliminated ? 0.45 : 1,
        borderColor: STATE_BORDER[liveState],
        boxShadow: liveState === 'started' ? '0 0 0 1px var(--gold)' : 'none',
        transition: 'border-color 200ms var(--ease), opacity 200ms var(--ease)',
        overflow: 'hidden',
      }}
    >
      {justEliminated && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            right: -28,
            transform: 'rotate(28deg)',
            background: 'var(--ember)',
            color: 'var(--void)',
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.1em',
            padding: '2px 34px',
          }}
        >
          ELIMINATED
        </div>
      )}
      {justBorn && (
        <div
          style={{
            position: 'absolute',
            top: 10,
            right: -28,
            transform: 'rotate(28deg)',
            background: 'var(--moss)',
            color: 'var(--void)',
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.1em',
            padding: '2px 42px',
          }}
        >
          NEW
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <h3 style={{ fontSize: 17 }}>{agent.personality_name}</h3>
        <span className={`pill ${isEliminated ? 'pill--eliminated' : 'pill--active'}`}>
          {isEliminated ? 'Eliminated' : 'Active'}
        </span>
      </div>

      <dl
        className="mono"
        style={{
          margin: '0.75rem 0 0',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '0.4rem 0.6rem',
          fontSize: 12,
        }}
      >
        <Field label="Model" value={agent.model} />
        <Field label="Generation" value={agent.generation} />
        <Field label="Score" value={agent.latest_score ?? '—'} accent="gold" />
        <Field label="Avg" value={agent.average_score ?? '—'} />
        <Field label="Rounds survived" value={agent.rounds_survived} />
        <Field label="Calls" value={agent.statistics.total_calls} />
      </dl>
    </div>
  )
}

function Field({ label, value, accent }) {
  return (
    <div>
      <dt style={{ color: 'var(--chalk-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </dt>
      <dd style={{ margin: 0, color: accent ? `var(--${accent})` : 'var(--chalk)', fontSize: 14 }}>{value}</dd>
    </div>
  )
}
