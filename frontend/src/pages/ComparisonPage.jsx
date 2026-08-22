import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import AnswerCard from '../components/AnswerCard.jsx'

const SORTS = {
  score: (a, b) => b.score - a.score,
  personality: (a, b) => a.personality_name.localeCompare(b.personality_name),
  model: (a, b) => a.model.localeCompare(b.model),
}

function buildRows(outcome) {
  const answerById = Object.fromEntries(outcome.round_result.answers.map((a) => [a.agent_id, a]))
  const letterByAgentId = Object.fromEntries(
    Object.entries(outcome.reveal_map).map(([letter, agentId]) => [agentId, letter])
  )

  return outcome.leaderboard.entries.map((entry) => {
    const letter = letterByAgentId[entry.agent_id]
    const critiques = outcome.judge_results
      .map((jr) => {
        const score = jr.scores.find((s) => s.answer_id === letter)
        return score ? { judge_name: jr.judge_name, critique: score.critique } : null
      })
      .filter(Boolean)

    return {
      agent_id: entry.agent_id,
      personality_name: entry.personality_name,
      score: entry.score,
      model: answerById[entry.agent_id]?.model ?? '—',
      answer: answerById[entry.agent_id]?.answer ?? '(no answer)',
      critiques,
    }
  })
}

export default function ComparisonPage() {
  const [rounds, setRounds] = useState([])
  const [roundNumber, setRoundNumber] = useState(null)
  const [outcome, setOutcome] = useState(null)
  const [sortKey, setSortKey] = useState('score')
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .rounds()
      .then((list) => {
        setRounds(list)
        if (list.length > 0) setRoundNumber(list[list.length - 1].round_number)
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (roundNumber == null) return
    api.round(roundNumber).then(setOutcome).catch((err) => setError(err.message))
  }, [roundNumber])

  const rows = useMemo(() => {
    if (!outcome) return []
    return [...buildRows(outcome)].sort(SORTS[sortKey])
  }, [outcome, sortKey])

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div className="card" style={{ padding: '1rem 1.2rem', display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: '0.3rem' }}>
            Round
          </div>
          <select
            value={roundNumber ?? ''}
            onChange={(e) => setRoundNumber(Number(e.target.value))}
            style={selectStyle}
          >
            {rounds.map((r) => (
              <option key={r.round_number} value={r.round_number}>
                Round {r.round_number}
              </option>
            ))}
          </select>
        </div>

        <div>
          <div className="eyebrow" style={{ marginBottom: '0.3rem' }}>
            Sort by
          </div>
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value)} style={selectStyle}>
            <option value="score">Score</option>
            <option value="personality">Personality</option>
            <option value="model">Model</option>
          </select>
        </div>

        {outcome && (
          <div style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--chalk-dim)', maxWidth: 420 }}>
            {outcome.round_result.question}
          </div>
        )}
      </div>

      {error && <div style={{ color: 'var(--ember)' }}>{error}</div>}
      {!outcome && !error && <div className="eyebrow">No rounds have been run yet.</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.85rem' }}>
        {rows.map((row) => (
          <AnswerCard key={row.agent_id} row={row} />
        ))}
      </div>
    </div>
  )
}

const selectStyle = {
  background: 'var(--void)',
  border: '1px solid var(--void-line)',
  borderRadius: 'var(--radius)',
  color: 'var(--chalk)',
  padding: '0.45rem 0.6rem',
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
}