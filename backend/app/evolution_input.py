"""
build_evolution_input() — Phase 10.

Walks the ArenaEngine's round history and assembles everything the
spec says the Evolution LLM needs about the agent that just got
eliminated: its personality, average score, judge critiques (looked up
via that round's reveal_map so we never need to break anonymity going
forward), and which questions it did well/poorly on.
"""
from __future__ import annotations

from statistics import mean

from app.agent import Agent
from app.models.arena import RoundOutcome
from app.models.evolution import EvolutionInput

# A round counts as "successful" for this agent if its final leaderboard
# score for that round was at least this. Below it counts as "failed".
# Halfway up a 1-10 scale — good enough for Phase 10; nothing here claims
# statistical rigor, it's a simple bucketing heuristic for the prompt.
SUCCESS_THRESHOLD = 6.0


def build_evolution_input(agent: Agent, round_outcomes: list[RoundOutcome]) -> EvolutionInput:
    scores: list[float] = []
    critiques: list[str] = []
    failed_questions: list[str] = []
    successful_questions: list[str] = []

    for outcome in round_outcomes:
        letter = next((l for l, aid in outcome.reveal_map.items() if aid == agent.agent_id), None)
        if letter is None:
            continue  # agent didn't answer (or wasn't in) this round

        entry = next((e for e in outcome.leaderboard.entries if e.agent_id == agent.agent_id), None)
        if entry is None:
            continue

        scores.append(entry.score)

        for judge_result in outcome.judge_results:
            for score in judge_result.scores:
                if score.answer_id == letter and score.critique:
                    critiques.append(score.critique)

        if entry.score >= SUCCESS_THRESHOLD:
            successful_questions.append(outcome.round_result.question)
        else:
            failed_questions.append(outcome.round_result.question)

    return EvolutionInput(
        eliminated_personality=agent.personality,
        average_score=round(mean(scores), 2) if scores else 0.0,
        critiques=critiques,
        strengths=list(agent.personality.specialties),
        weaknesses=list(agent.personality.weaknesses),
        failed_questions=failed_questions,
        successful_questions=successful_questions,
    )