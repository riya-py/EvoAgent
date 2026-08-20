import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

const NODE_W = 176
const NODE_H = 60
const COL_GAP = 90
const ROW_GAP = 18

// Lays every personality out in columns by generation, rows within a
// generation in the order they arrived — then hands back both the
// positioned nodes and the parent->child edges needed to draw the
// lineage threads between them.
function layoutTree(personalities) {
  const byGeneration = new Map()
  personalities.forEach((p) => {
    if (!byGeneration.has(p.generation)) byGeneration.set(p.generation, [])
    byGeneration.get(p.generation).push(p)
  })

  const positions = {}
  const generations = [...byGeneration.keys()].sort((a, b) => a - b)
  generations.forEach((gen, colIndex) => {
    byGeneration.get(gen).forEach((p, rowIndex) => {
      positions[p.id] = {
        x: colIndex * (NODE_W + COL_GAP),
        y: rowIndex * (NODE_H + ROW_GAP),
        personality: p,
      }
    })
  })

  const edges = personalities
    .filter((p) => p.parent_agent && positions[p.parent_agent])
    .map((p) => ({ from: positions[p.parent_agent], to: positions[p.id] }))

  const width = (generations.length || 1) * (NODE_W + COL_GAP)
  const maxRows = Math.max(1, ...[...byGeneration.values()].map((g) => g.length))
  const height = maxRows * (NODE_H + ROW_GAP)

  return { positions, edges, width, height }
}

export default function EvolutionTreePage() {
  const [lineage, setLineage] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [parentDetail, setParentDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.evolution().then(setLineage).catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setDetail(null)
    setParentDetail(null)
    api
      .agent(selectedId)
      .then((agent) => {
        setDetail(agent)
        if (agent.parent_agent) {
          api.agent(agent.parent_agent).then(setParentDetail).catch(() => {})
        }
      })
      .catch((err) => setError(err.message))
  }, [selectedId])

  const { positions, edges, width, height } = useMemo(() => layoutTree(lineage), [lineage])

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
      <div>
        <h2 style={{ fontSize: 22 }}>Evolution Tree</h2>
        <div className="eyebrow" style={{ marginTop: '0.3rem' }}>
          Click any personality to see its lineage and performance.
        </div>
      </div>

      {error && <div style={{ color: 'var(--ember)' }}>{error}</div>}

      <div style={{ display: 'flex', gap: '1.1rem', alignItems: 'flex-start' }}>
        <div className="card" style={{ padding: '1.2rem', overflowX: 'auto', flex: 1 }}>
          <svg width={Math.max(width, 200)} height={Math.max(height, 100)}>
            {edges.map((edge, i) => (
              <g key={i}>
                <line
                  x1={edge.from.x + NODE_W}
                  y1={edge.from.y + NODE_H / 2}
                  x2={edge.to.x}
                  y2={edge.to.y + NODE_H / 2}
                  stroke="var(--void-line)"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                />
                <circle cx={edge.from.x + NODE_W} cy={edge.from.y + NODE_H / 2} r="4" fill="var(--gold)" />
                <circle cx={edge.to.x} cy={edge.to.y + NODE_H / 2} r="4" fill="var(--moss)" />
              </g>
            ))}
            {Object.values(positions).map(({ x, y, personality }) => (
              <g
                key={personality.id}
                transform={`translate(${x}, ${y})`}
                onClick={() => setSelectedId(personality.id)}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx="6"
                  fill="var(--void-raised)"
                  stroke={selectedId === personality.id ? 'var(--gold)' : 'var(--void-line)'}
                  strokeWidth={selectedId === personality.id ? 2 : 1}
                />
                <text x="12" y="24" fill="var(--chalk)" fontSize="13" fontFamily="var(--font-body)">
                  {personality.name}
                </text>
                <text x="12" y="42" fill="var(--chalk-dim)" fontSize="11" fontFamily="var(--font-mono)">
                  gen {personality.generation}
                </text>
              </g>
            ))}
          </svg>
        </div>

        <DetailPanel detail={detail} parentDetail={parentDetail} />
      </div>
    </div>
  )
}

function DetailPanel({ detail, parentDetail }) {
  if (!detail) {
    return (
      <div className="card" style={{ padding: '1.1rem', width: 300, flexShrink: 0 }}>
        <div className="eyebrow">Select a personality to inspect it.</div>
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: '1.1rem', width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
      <h3 style={{ fontSize: 16 }}>{detail.personality_name}</h3>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--chalk-dim)' }}>{detail.description}</p>

      <DetailRow label="Parent" value={parentDetail?.personality_name ?? '— (original generation)'} />
      <DetailRow label="Generation" value={detail.generation} />
      {parentDetail && (
        <DetailRow label="Why the parent died" value={parentDetail.elimination_reason ?? 'Still active'} />
      )}

      <DetailList label="Strengths" items={detail.specialties} color="moss" />
      <DetailList label="Weaknesses" items={detail.weaknesses} color="ember" />

      <div>
        <div className="eyebrow" style={{ marginBottom: '0.3rem' }}>
          Evolution prompt
        </div>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--chalk-dim)', lineHeight: 1.5 }}>
          {detail.description}
          <br />
          <span style={{ fontStyle: 'italic' }}>
            (The raw generation prompt itself isn't persisted — this is the personality's own system
            prompt, which is what it was actually designed to be.)
          </span>
        </p>
      </div>

      <div>
        <div className="eyebrow" style={{ marginBottom: '0.3rem' }}>
          Performance history
        </div>
        {detail.score_history.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--chalk-dim)' }}>No rounds yet.</div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {detail.score_history.map((p) => (
              <span key={p.round_number} className="pill" style={{ borderColor: 'var(--void-line)' }}>
                R{p.round_number}: {p.score.toFixed(1)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function DetailRow({ label, value }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div style={{ fontSize: 13 }}>{value}</div>
    </div>
  )
}

function DetailList({ label, items, color }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: '0.25rem' }}>
        {label}
      </div>
      <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: 12, color: `var(--${color})` }}>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}