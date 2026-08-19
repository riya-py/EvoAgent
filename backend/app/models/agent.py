"""
Schemas for a single Agent's output and running statistics — Phase 3.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AgentAnswer(BaseModel):
    """One answer produced by one agent for one question.

    Deliberately does NOT carry a chain-of-thought / reasoning-trace
    field — per the spec, agents return conclusions and concise
    explanations, not private step-by-step reasoning.
    """

    agent_id: str
    personality_name: str
    model: str
    question: str
    answer: str = ""
    success: bool = True
    generation_time_ms: float = 0.0
    error: Optional[str] = None


class AgentStatistics(BaseModel):
    """Running totals for one agent, derived from its answer history."""

    agent_id: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_generation_time_ms: float = 0.0