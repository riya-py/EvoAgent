import { useState } from 'react'

export default function QuestionBar({ onSubmit, isRunning }) {
  const [question, setQuestion] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isRunning) return
    onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ padding: '1.25rem 1.4rem' }}>
      <div className="eyebrow" style={{ marginBottom: '0.5rem' }}>
        Tonight's question
      </div>
      <div style={{ display: 'flex', gap: '0.75rem' }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask the arena something…"
          disabled={isRunning}
          style={{
            flex: 1,
            background: 'var(--void)',
            border: '1px solid var(--void-line)',
            borderRadius: 'var(--radius)',
            color: 'var(--chalk)',
            padding: '0.7rem 0.9rem',
            fontSize: 15,
            fontFamily: 'var(--font-body)',
          }}
        />
        <button
          type="submit"
          disabled={isRunning || !question.trim()}
          style={{
            background: isRunning ? 'var(--steel)' : 'var(--gold)',
            color: 'var(--void)',
            border: 'none',
            borderRadius: 'var(--radius)',
            padding: '0 1.4rem',
            fontFamily: 'var(--font-display)',
            fontSize: 13,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            fontWeight: 600,
          }}
        >
          {isRunning ? 'Round in progress…' : 'Run round'}
        </button>
      </div>
    </form>
  )
}
