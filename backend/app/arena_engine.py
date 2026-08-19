"""
ArenaEngine — Phase 8 (orchestration) + Phase 9 (elimination).

Combines everything built so far into the flow from the spec:

    ROUND START
        v
    Question Input
        v
    Generate 8 Answers        (Phase 4 — run_round)
        v
    Anonymous Judges          (Phase 5 — anonymize_answers + judges)
        v
    Peer Voting               (Phase 7 — optional, off by default)
        v
    Score Answers             (Phase 6 — ScoringEngine)
        v
    Rank Agents
        v
    Lowest Eliminated         (Phase 9)
        v
    Round Complete

Usage:
    engine = ArenaEngine(agents=await build_agents())
    outcome = await engine.run_round("Explain TCP congestion control.")

Multi-round competitions (Phase 12) and evolution (Phase 10/11) build
on top of this by calling run_round() repeatedly and, eventually,
replacing the eliminated slot with a newborn personality instead of
just shrinking the roster like this phase does on its own.
"""
from __future__ import annotations

import asyncio
import logging

from app.agent import Agent
from app.anonymizer import anonymize_answers
from app.arena_round import run_round as run_agent_round
from app.judges import build_judges
from app.models.arena import RoundOutcome
from app.models.elimination import EliminationRecord
from app.ollama_manager import OllamaManager, ollama_manager
from app.peer_voting import conduct_peer_voting
from app.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class ArenaEngine:
    def __init__(
        self,
        agents: list[Agent],
        manager: OllamaManager | None = None,
        scoring_engine: ScoringEngine | None = None,
        judge_model: str | None = None,
        peer_voting_enabled: bool = False,
    ):
        if not agents:
            raise ValueError("ArenaEngine needs at least one agent to start")

        self.active_agents: list[Agent] = list(agents)
        self.manager = manager or ollama_manager
        self.peer_voting_enabled = peer_voting_enabled
        self.scoring_engine = scoring_engine or ScoringEngine(
            peer_vote_weight=0.3 if peer_voting_enabled else 0.0
        )
        self._judge_model = judge_model  # resolved lazily if not given

        self.round_number = 0
        self.history: list[RoundOutcome] = []
        self.eliminated: list[EliminationRecord] = []
        self._eliminated_agents: dict[str, Agent] = {}  # agent_id -> Agent, never discarded

    async def run_round(self, question: str) -> RoundOutcome:
        self.round_number += 1

        # Step 1 — every active agent answers concurrently (Phase 4).
        round_result = await run_agent_round(self.active_agents, question, round_number=self.round_number)

        # Step 2 — anonymize before judging (Phase 5).
        anonymized, reveal_map = anonymize_answers(round_result)

        # Step 3 — independent judges score every answer, concurrently.
        judge_model = await self._get_judge_model()
        judges = build_judges(model=judge_model, manager=self.manager)
        judge_results = list(
            await asyncio.gather(*(judge.evaluate(question, anonymized) for judge in judges))
        )

        # Step 4 — peer voting, only if explicitly enabled (Phase 7).
        peer_voting = None
        if self.peer_voting_enabled:
            peer_voting = await conduct_peer_voting(self.active_agents, question, anonymized, reveal_map)

        # Step 5 — score & rank (Phase 6).
        leaderboard = self.scoring_engine.compute(
            judge_results, reveal_map, round_result, peer_voting=peer_voting
        )

        # Step 6 — eliminate the lowest-ranked agent (Phase 9), unless
        # only one agent remains — the arena needs at least one survivor.
        eliminated_record = None
        if len(self.active_agents) > 1 and leaderboard.entries:
            eliminated_record = self._eliminate_lowest(leaderboard)

        outcome = RoundOutcome(
            round_number=self.round_number,
            round_result=round_result,
            judge_results=judge_results,
            leaderboard=leaderboard,
            peer_voting=peer_voting,
            eliminated=eliminated_record,
            reveal_map=reveal_map,
        )
        self.history.append(outcome)
        return outcome

    def get_agent(self, agent_id: str) -> Agent | None:
        """Look up an agent whether it's still active or was eliminated —
        eliminated agents are kept, never deleted, so their `.history`
        (answers) and personality data stay reachable."""
        for agent in self.active_agents:
            if agent.agent_id == agent_id:
                return agent
        return self._eliminated_agents.get(agent_id)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    async def _get_judge_model(self) -> str:
        if self._judge_model:
            return self._judge_model

        models = await self.manager.list_models()
        if models:
            self._judge_model = models[0].name
        elif self.active_agents:
            # No models installed at all (e.g. sandbox/demo) — reuse an
            # agent's resolved model rather than crash the round.
            self._judge_model = self.active_agents[0].model
        else:
            raise ValueError("Cannot resolve a judge model: no Ollama models installed and no active agents")

        return self._judge_model

    def _eliminate_lowest(self, leaderboard) -> EliminationRecord:
        lowest_entry = leaderboard.entries[-1]  # entries are sorted descending by score
        agent = next(a for a in self.active_agents if a.agent_id == lowest_entry.agent_id)

        record = EliminationRecord(
            agent_id=agent.agent_id,
            personality_name=agent.personality.name,
            round_number=self.round_number,
            final_score=lowest_entry.score,
            reason=f"Lowest score ({lowest_entry.score}) in round {self.round_number}",
        )

        self.active_agents = [a for a in self.active_agents if a.agent_id != agent.agent_id]
        self._eliminated_agents[agent.agent_id] = agent
        self.eliminated.append(record)

        logger.info("Round %d: eliminated %s (score %.2f)", self.round_number, agent.agent_id, lowest_entry.score)
        return record