"""
Evolution schemas — Phase 10.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.personality import Personality


class EvolutionInput(BaseModel):
    """Everything the Evolution LLM is given about the eliminated agent,
    per the spec: personality, performance history, average score, judge
    critiques, strengths, weaknesses, failed questions, successful
    questions."""

    eliminated_personality: Personality
    average_score: float
    critiques: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    failed_questions: list[str] = Field(default_factory=list)
    successful_questions: list[str] = Field(default_factory=list)


class NewPersonalityDraft(BaseModel):
    """
    The raw shape we ask the Evolution LLM to return. Deliberately
    narrower than the full Personality model — id/generation/parent_agent
    are computed in code, not trusted from the LLM's output, the same
    way Agent model resolution never trusts a personality to name its
    own model.
    """

    name: str
    description: str
    system_prompt: str
    specialties: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)