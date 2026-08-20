import { useEffect, useState } from 'react'
import { api } from '../api'
import { useArenaSocket } from '../hooks/useArenaSocket'
import QuestionBar from '../components/QuestionBar.jsx'
import AgentCard from '../components/AgentCard.jsx'
import Leaderboard from '../components/Leaderboard.jsx'
import LineageThread from '../components/LineageThread.jsx'

const PHASE_LABEL = {
  ROUND_STARTED: 'Agents are answering…',
  AGENT_STARTED: 'Agents are answering…',
  AGENT_COMPLETED: 'Agents are answering…',
  JUDGING_STARTED: 'Judges are scoring…',
  JUDGE_COMPLETED: 'Judges are scoring…',
  SCORES_UPDATED: 'Ranking the roster…',
  AGENT_ELIMINATED: 'Lowest scorer eliminated…',
  EVOLUTION_STARTED: 'Evolving a replacement…',
  NEW_AGENT_CREATED: 'A new personality was born…',
  ROUND_COMPLETED: null,
}

export default function ArenaPage() {
  const [agents, setAgents] = useState([])
  const [leaderboard, setLeaderboard] = useState(null)
  const [outcome, setOutcome] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)
  const [liveStates, setLiveStates] = useState({}) // agent_id -> 'started' | 'completed'
  const { lastEvent, connected } = useArenaSocket()

  async function refreshAgents() {
    const list = await api.agents()
    setAgents(list)
  }

  useEffect(() => {
    refreshAgents().catch(() => {})
    api.leaderboard().then(setLeaderboard).catch(() => {})
  }, [])

  useEffect(() => {
    if (!lastEvent) return
    if (lastEvent.type === 'AGENT_STARTED') {
      setLiveStates((prev) => ({ ...prev, [lastEvent.data.agent_id]: 'started' }))
    }
    if (lastEvent.type === 'AGENT_COMPLETED') {
      setLiveStates((prev) => ({ ...prev, [lastEvent.data.agent_id]: 'completed' }))
    }
    if (lastEvent.type === 'ROUND_COMPLETED') {
      refreshAgents().catch(() => {})
      setTimeout(() => setLiveStates({}), 2500)
    }
  }, [lastEvent])

  async function runRound(question) {
    setIsRunning(true)
    setError(null)
    setLiveStates({})
    try {
      const result = await api.askQuestion(question)
      setOutcome(result)
      setLeaderboard(result.leaderboard)
      await refreshAgents()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsRunning(false)
    }
  }

  const phaseLabel = isRunning ? PHASE_LABEL[lastEvent?.type] ?? 'Running round…' : null

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <QuestionBar onSubmit={runRound} isRunning={isRunning} />

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', minHeight: 20 }}>
        <span
          className="mono"
          style={{ fontSize: 11, color: connected ? 'var(--moss)' : 'var(--ember)' }}
        >
          ● {connected ? 'live' : 'reconnecting…'}
        </span>
        {phaseLabel && <span className="eyebrow">{phaseLabel}</span>}
        {error && <span style={{ color: 'var(--ember)', fontSize: 13 }}>{error}</span>}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: '0.85rem',
        }}
      >
        {agents.map((agent) => (
          <AgentCard
            key={agent.agent_id}
            agent={agent}
            liveState={liveStates[agent.agent_id] ?? 'idle'}
            justEliminated={outcome?.eliminated?.agent_id === agent.agent_id}
            justBorn={outcome?.newborn?.id === agent.agent_id}
          />
        ))}
      </div>

      {outcome?.eliminated && outcome?.newborn && (
        <LineageThread parentName={outcome.eliminated.personality_name} childName={outcome.newborn.name} />
      )}

      <Leaderboard leaderboard={leaderboard} />
    </div>
  )
}
