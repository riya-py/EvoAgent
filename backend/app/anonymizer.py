"""
Anonymization — Phase 5.

Judges must never see which personality or model produced an answer,
only "Answer A", "Answer B", etc. This module is the only place that
knows the letter -> agent_id mapping; judges never receive it.
"""
from __future__ import annotations

import string

from app.models.judge import AnonymizedAnswer
from app.models.round import RoundResult


def anonymize_answers(round_result: RoundResult) -> tuple[list[AnonymizedAnswer], dict[str, str]]:
    """
    Returns (anonymized_answers, reveal_map) where reveal_map is
    {letter: agent_id} — kept by the caller (e.g. the scoring engine
    in Phase 6) to translate judge feedback back to real agents *after*
    judging is complete. Only successful answers are anonymized; a
    failed agent has nothing worth judging.
    """
    letters = string.ascii_uppercase
    successful = [a for a in round_result.answers if a.success]
    if len(successful) > len(letters):
        raise ValueError(f"Cannot anonymize more than {len(letters)} answers")

    anonymized: list[AnonymizedAnswer] = []
    reveal_map: dict[str, str] = {}

    for letter, agent_answer in zip(letters, successful):
        anonymized.append(AnonymizedAnswer(letter=letter, answer=agent_answer.answer))
        reveal_map[letter] = agent_answer.agent_id

    return anonymized, reveal_map