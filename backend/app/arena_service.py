"""
Arena service — Phase 14.

This is the "API -> ArenaEngine -> Agents/Judges/Evolution" arrow from
the spec's diagram, made concrete: FastAPI routes (app/routers/arena.py)
only ever call functions in this module. This module is the only thing
that touches ArenaEngine directly. No arena logic lives in FastAPI
route handlers themselves — they just translate HTTP <-> these calls.
"""
from __future__ import annotations

from app.agent_factory import build_agents
from app.arena_engine import ArenaEngine
from app.config import settings
from app.events import EventBus
from app.models.api import AgentSummary, RoundSummary
from app.models.arena import RoundOutcome
from app.models.scoring import Leaderboard
from app.persistence import ArenaRepository

_engine: ArenaEngine | None = None


async def get_engine() -> ArenaEngine:
    """Lazily build the one shared arena the whole API polls/drives.
    Built on first use rather than at import time, since it needs an
    async call (build_agents) to resolve real installed Ollama models."""
    global _engine
    if _engine is None:
        agents = await build_agents()
        _engine = ArenaEngine(
            agents=agents,
            evolve_on_elimination=settings.evolve_on_elimination,
            peer_voting_enabled=settings.peer_voting_enabled,
            repository=ArenaRepository(),
            event_bus=EventBus(),
        )
    return _engine


def reset_engine() -> None:
    """Test hook — forces the next get_engine() call to build a fresh
    arena instead of reusing whatever's already running."""
    global _engine
    _engine = None


async def ask_question(question: str) -> RoundOutcome:
    engine = await get_engine()
    return await engine.run_round(question)


def _summarize(engine: ArenaEngine, agent) -> AgentSummary:
    return AgentSummary(
        agent_id=agent.agent_id,
        personality_name=agent.personality.name,
        model=agent.model,
        generation=agent.personality.generation,
        parent_agent=agent.personality.parent_agent,
        status=engine.status_of(agent.agent_id) or "UNKNOWN",
        statistics=agent.statistics,
    )


async def list_agent_summaries() -> list[AgentSummary]:
    engine = await get_engine()
    return [_summarize(engine, a) for a in engine.all_agents()]


async def get_agent_summary(agent_id: str) -> AgentSummary | None:
    engine = await get_engine()
    agent = engine.get_agent(agent_id)
    if agent is None:
        return None
    return _summarize(engine, agent)


async def list_round_summaries() -> list[RoundSummary]:
    engine = await get_engine()
    return [
        RoundSummary(
            round_number=o.round_number,
            question=o.round_result.question,
            success_count=o.round_result.success_count,
            eliminated_agent_id=o.eliminated.agent_id if o.eliminated else None,
            newborn_id=o.newborn.id if o.newborn else None,
        )
        for o in engine.history
    ]


async def get_round(round_number: int) -> RoundOutcome | None:
    engine = await get_engine()
    return engine.get_round(round_number)


async def latest_leaderboard() -> Leaderboard | None:
    engine = await get_engine()
    return engine.latest_leaderboard()


async def current_state() -> dict:
    engine = await get_engine()
    return {
        "round_number": engine.round_number,
        "active_agent_ids": [a.agent_id for a in engine.active_agents],
        "eliminated_count": len(engine.eliminated),
        "evolve_on_elimination": engine.evolve_on_elimination,
        "peer_voting_enabled": engine.peer_voting_enabled,
    }


async def lineage_snapshot() -> list:
    engine = await get_engine()
    return [p.model_dump() for p in engine.lineage]