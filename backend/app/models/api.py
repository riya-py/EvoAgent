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


class AgentSummary(BaseModel):
    agent_id: str
    personality_name: str
    model: str
    generation: int
    parent_agent: Optional[str] = None
    status: str  # "ACTIVE" | "ELIMINATED"
    statistics: AgentStatistics

    # Phase 16 (Agent Cards) needs these on the card face — computed from
    # arena history in arena_service, not stored on the Agent itself.
    latest_score: Optional[float] = None
    average_score: Optional[float] = None
    rounds_survived: int = 0


class RoundSummary(BaseModel):
    round_number: int
    question: str
    success_count: int
    eliminated_agent_id: Optional[str] = None
    newborn_id: Optional[str] = None