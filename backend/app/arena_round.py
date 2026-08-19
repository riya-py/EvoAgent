"""
8-Agent Arena — Phase 4.

Goal per the spec: make all 8 agents answer the same question, run
concurrently (not one after another).

This module only fans a question out to N agents and collects the
results — it does not judge, score, eliminate, or evolve anything.
That starts with Phase 5 (judges) and comes together fully in Phase 8
(ArenaEngine).
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.agent import Agent
from app.models.round import RoundResult

logger = logging.getLogger(__name__)


async def run_round(agents: list[Agent], question: str, round_number: int = 1) -> RoundResult:
    """
    Ask every agent the same question at the same time via asyncio.gather
    (real concurrency: while one agent is awaiting its network response,
    the event loop is free to advance the others). Order of `answers`
    matches the order of `agents` passed in, regardless of which agent
    actually finishes first.
    """
    started = time.perf_counter()

    logger.info("Round %d starting — %d agents, question: %r", round_number, len(agents), question)

    results = await asyncio.gather(
        *(agent.answer(question) for agent in agents),
        return_exceptions=True,
    )

    answers = []
    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            # answer() itself is designed not to raise, but if a bug or
            # an unexpected error slips through, don't let one agent
            # take down the whole round.
            logger.error("Agent %s raised unexpectedly: %s", agent.agent_id, result)
            from app.models.agent import AgentAnswer

            answers.append(
                AgentAnswer(
                    agent_id=agent.agent_id,
                    personality_name=agent.personality.name,
                    model=agent.model,
                    question=question,
                    success=False,
                    error=str(result),
                )
            )
        else:
            answers.append(result)

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Round %d complete — %d/%d answers succeeded in %.0fms",
        round_number,
        sum(1 for a in answers if a.success),
        len(answers),
        elapsed_ms,
    )

    return RoundResult(
        round_number=round_number,
        question=question,
        answers=answers,
        total_time_ms=elapsed_ms,
    )