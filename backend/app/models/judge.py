"""
Schemas for judging — Phase 5.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AnonymizedAnswer(BaseModel):
    """
    What a judge is allowed to see: a letter and the answer text.
    No agent_id, personality name, or model — anonymity is what
    prevents personality/model bias in judging.
    """

    letter: str
    answer: str


class JudgeScore(BaseModel):
    """One judge's evaluation of one answer. Mirrors the JSON shape
    from the spec: {"answer_id": "C", "accuracy": 9, "reasoning": 8,
    "utility": 9, "overall": 8.7, "critique": "..."}."""

    answer_id: str  # the letter, e.g. "C"
    accuracy: int = Field(ge=1, le=10)
    reasoning: int = Field(ge=1, le=10)
    utility: int = Field(ge=1, le=10)
    overall: float = Field(ge=1, le=10)
    critique: str = ""


class JudgeResult(BaseModel):
    """All scores produced by one judge in one pass over one round."""

    judge_name: str
    focus: str
    scores: list[JudgeScore]