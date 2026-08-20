"""
API-facing DTOs — Phase 14.

Deliberately separate from the domain models (Personality, RoundOutcome,
...): these are shaped for what the API wants to show, not for what the
engine needs internally. Where a domain model already IS the right
shape for a response (RoundOutcome, Leaderboard, Personality), routes
return it directly instead of duplicating it here.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.models.agent import AgentStatistics


class ScorePoint(BaseModel):
    round_number: int
    score: float


class AgentSummary(BaseModel):
    agent_id: str
    personality_name: str
    description: str
    model: str
    generation: int
    parent_agent: Optional[str] = None
    status: str  # "ACTIVE" | "ELIMINATED"
    statistics: AgentStatistics
    specialties: list[str] = []
    weaknesses: list[str] = []

    # Phase 16 (Agent Cards) needs these on the card face — computed from
    # arena history in arena_service, not stored on the Agent itself.
    latest_score: Optional[float] = None
    average_score: Optional[float] = None
    rounds_survived: int = 0

    # Phase 18 (Leaderboard + Analytics)
    wins: int = 0  # rounds this agent ranked #1
    losses: int = 0  # rounds this agent was eliminated
    score_history: list[ScorePoint] = []

    # Phase 19 (Evolution Tree) — populated only for eliminated agents.
    elimination_reason: Optional[str] = None


class RoundSummary(BaseModel):
    round_number: int
    question: str
    success_count: int
    eliminated_agent_id: Optional[str] = None
    newborn_id: Optional[str] = None