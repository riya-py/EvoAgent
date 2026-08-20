"""
ArenaEngine — Phase 8 (orchestration), Phase 9 (elimination), and
Phase 12 (multi-round evolution).

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
    New Personality Born      (Phase 10/11 — optional, off by default)
        v
    Round Complete

Usage — elimination only, roster shrinks (Phase 9 behavior):
    engine = ArenaEngine(agents=await build_agents())
    outcome = await engine.run_round("Explain TCP congestion control.")

Usage — full evolutionary loop, roster stays constant (Phase 12):
    engine = ArenaEngine(agents=await build_agents(), evolve_on_elimination=True)
    outcomes = await engine.run_tournament(["Q1", "Q2", ..., "Q8"])
"""
from __future__ import annotations

import asyncio
import logging

from app.agent import Agent
from app.anonymizer import anonymize_answers
from app.arena_round import run_round as run_agent_round
from app.diversity import DiversityChecker, evolve_with_diversity_check
from app.evolution import EvolutionEngine
from app.evolution_input import build_evolution_input
from app.events import ArenaEvent, EventBus, EventType
from app.judges import build_judges
from app.models.arena import RoundOutcome
from app.models.elimination import EliminationRecord
from app.models.personality import Personality
from app.ollama_manager import OllamaManager, ollama_manager
from app.peer_voting import conduct_peer_voting
from app.persistence import ArenaRepository
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
        evolve_on_elimination: bool = False,
        evolution_engine: EvolutionEngine | None = None,
        diversity_checker: DiversityChecker | None = None,
        repository: ArenaRepository | None = None,
        event_bus: EventBus | None = None,
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

        # Phase 12 — off by default so Phase 9's plain elimination
        # behavior (roster shrinks, nothing replaces it) is unchanged
        # unless explicitly opted into.
        self.evolve_on_elimination = evolve_on_elimination
        self.evolution_engine = evolution_engine  # resolved lazily if not given
        self.diversity_checker = diversity_checker or DiversityChecker()

        # Phase 13 — off by default (in-memory only) unless a repository
        # is supplied. When present, every round and the starting roster
        # are persisted to SQLite as they happen.
        self.repository = repository

        # Phase 15 — off by default (no bus, no events published, zero
        # overhead). When set, run_round() publishes the 10 event types
        # from the spec's streaming flow as the round progresses.
        self.event_bus = event_bus

        self.round_number = 0
        self.history: list[RoundOutcome] = []
        self.eliminated: list[EliminationRecord] = []
        self._eliminated_agents: dict[str, Agent] = {}  # agent_id -> Agent, never discarded

        # Complete evolutionary lineage (Phase 12's done condition): the
        # original roster's personalities plus every newborn since, so
        # get_lineage_chain() can walk parent -> child at any point.
        self.lineage: list[Personality] = [a.personality for a in agents]

        if self.repository:
            self.repository.save_agents([(a.personality, a.model) for a in self.active_agents])

    async def run_round(self, question: str) -> RoundOutcome:
        self.round_number += 1
        await self._emit(EventType.ROUND_STARTED, {"question": question})

        # Step 1 — every active agent answers concurrently (Phase 4).
        # Hooks only fire when an event_bus is set — no overhead otherwise.
        on_start = (lambda agent: self._emit(EventType.AGENT_STARTED, {"agent_id": agent.agent_id})) if self.event_bus else None
        on_complete = (
            (lambda agent, answer: self._emit(
                EventType.AGENT_COMPLETED, {"agent_id": agent.agent_id, "success": answer.success}
            ))
            if self.event_bus
            else None
        )
        round_result = await run_agent_round(
            self.active_agents, question, round_number=self.round_number,
            on_agent_start=on_start, on_agent_complete=on_complete,
        )

        # Step 2 — anonymize before judging (Phase 5).
        anonymized, reveal_map = anonymize_answers(round_result)

        # Step 3 — independent judges score every answer, concurrently.
        await self._emit(EventType.JUDGING_STARTED, {})
        judge_model = await self._get_judge_model()
        judges = build_judges(model=judge_model, manager=self.manager)

        async def evaluate_and_notify(judge):
            result = await judge.evaluate(question, anonymized)
            await self._emit(EventType.JUDGE_COMPLETED, {"judge_name": judge.name})
            return result

        judge_results = list(await asyncio.gather(*(evaluate_and_notify(j) for j in judges)))

        # Step 4 — peer voting, only if explicitly enabled (Phase 7).
        peer_voting = None
        if self.peer_voting_enabled:
            peer_voting = await conduct_peer_voting(self.active_agents, question, anonymized, reveal_map)

        # Step 5 — score & rank (Phase 6).
        leaderboard = self.scoring_engine.compute(
            judge_results, reveal_map, round_result, peer_voting=peer_voting
        )
        await self._emit(EventType.SCORES_UPDATED, {"entries": [e.model_dump() for e in leaderboard.entries]})

        # Step 6 — eliminate the lowest-ranked agent (Phase 9), unless
        # only one agent remains — the arena needs at least one survivor.
        eliminated_record = None
        if len(self.active_agents) > 1 and leaderboard.entries:
            eliminated_record = self._eliminate_lowest(leaderboard)
            await self._emit(
                EventType.AGENT_ELIMINATED,
                {"agent_id": eliminated_record.agent_id, "score": eliminated_record.final_score},
            )

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

        # Step 7 — evolve a replacement for the eliminated slot (Phase 12),
        # only if explicitly enabled. Uses this round's own outcome (just
        # appended to self.history) as part of the eliminated agent's
        # performance history, matching the spec's per-round evolution loop.
        if eliminated_record and self.evolve_on_elimination:
            await self._emit(EventType.EVOLUTION_STARTED, {"eliminated_agent_id": eliminated_record.agent_id})
            outcome.newborn = await self._evolve_replacement(eliminated_record)
            await self._emit(
                EventType.NEW_AGENT_CREATED, {"id": outcome.newborn.id, "name": outcome.newborn.name}
            )

        if self.repository:
            newborn_model = self.active_agents[-1].model if outcome.newborn else ""
            self.repository.save_round_outcome(outcome, newborn_model=newborn_model)

        await self._emit(
            EventType.ROUND_COMPLETED,
            {
                "eliminated": eliminated_record.agent_id if eliminated_record else None,
                "newborn": outcome.newborn.id if outcome.newborn else None,
            },
        )

        return outcome

    async def run_tournament(self, questions: list[str]) -> list[RoundOutcome]:
        """Run one round per question, in order (rounds must be sequential
        — each depends on the previous round's elimination/evolution
        state). `rounds = 8` from the spec just means passing 8
        questions; reuse the same question multiple times for repeats."""
        outcomes = []
        for question in questions:
            outcomes.append(await self.run_round(question))
        return outcomes

    def get_agent(self, agent_id: str) -> Agent | None:
        """Look up an agent whether it's still active or was eliminated —
        eliminated agents are kept, never deleted, so their `.history`
        (answers) and personality data stay reachable."""
        for agent in self.active_agents:
            if agent.agent_id == agent_id:
                return agent
        return self._eliminated_agents.get(agent_id)

    def all_agents(self) -> list[Agent]:
        """Every agent this engine has ever fielded, active or eliminated."""
        return [*self.active_agents, *self._eliminated_agents.values()]

    def status_of(self, agent_id: str) -> str | None:
        if any(a.agent_id == agent_id for a in self.active_agents):
            return "ACTIVE"
        if agent_id in self._eliminated_agents:
            return "ELIMINATED"
        return None

    def get_round(self, round_number: int) -> RoundOutcome | None:
        return next((o for o in self.history if o.round_number == round_number), None)

    def latest_leaderboard(self):
        return self.history[-1].leaderboard if self.history else None

    def get_lineage_chain(self, personality_id: str) -> list[Personality]:
        """Walk the family tree from the original generation-0 ancestor
        down to `personality_id`, oldest first. Powers questions like
        "how did we get here?" without needing Phase 13's persistence."""
        by_id = {p.id: p for p in self.lineage}
        chain: list[Personality] = []
        current = by_id.get(personality_id)
        while current is not None:
            chain.append(current)
            current = by_id.get(current.parent_agent) if current.parent_agent else None
        return list(reversed(chain))

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    async def _emit(self, event_type: EventType, data: dict) -> None:
        if self.event_bus:
            await self.event_bus.publish(ArenaEvent(type=event_type, round_number=self.round_number, data=data))

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

    async def _get_evolution_engine(self) -> EvolutionEngine:
        if self.evolution_engine is None:
            model = await self._get_judge_model()
            self.evolution_engine = EvolutionEngine(model=model, manager=self.manager)
        return self.evolution_engine

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

    async def _evolve_replacement(self, eliminated_record: EliminationRecord) -> Personality:
        eliminated_agent = self._eliminated_agents[eliminated_record.agent_id]
        evolution_input = build_evolution_input(eliminated_agent, self.history)

        evolution_engine = await self._get_evolution_engine()
        existing_personalities = [a.personality for a in self.active_agents]

        newborn = await evolve_with_diversity_check(
            evolution_engine, evolution_input, existing_personalities, checker=self.diversity_checker
        )

        # The newborn inherits the eliminated agent's concrete model —
        # the slot's *capability* carries over, only the personality changes.
        newborn_agent = Agent(personality=newborn, model=eliminated_agent.model, manager=self.manager)
        self.active_agents.append(newborn_agent)
        self.lineage.append(newborn)

        logger.info(
            "Round %d: %r evolved into %r (generation %d)",
            self.round_number, eliminated_agent.personality.name, newborn.name, newborn.generation,
        )
        return newborn