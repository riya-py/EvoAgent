"""
RoundResult schema — Phase 4.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.models.agent import AgentAnswer


class RoundResult(BaseModel):
    round_number: int
    question: str
    answers: list[AgentAnswer]
    total_time_ms: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for a in self.answers if a.success)