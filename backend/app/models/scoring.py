"""
Scoring schemas — Phase 6.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    personality_name: str

    # The weighted-judge component (accuracy/reasoning/utility -> single
    # number) — always present.
    judge_score: float
    avg_accuracy: float
    avg_reasoning: float
    avg_utility: float

    # The peer-voting component (Phase 7) — only populated when peer
    # voting is enabled for this scoring pass.
    vote_score: Optional[float] = None
    votes_received: Optional[int] = None

    # What the leaderboard is actually ranked by: judge_score alone
    # when peer voting is off, or the blended judge+vote score when on.
    score: float


class Leaderboard(BaseModel):
    round_number: int
    weights: dict[str, float]
    peer_vote_weight: float = 0.0
    entries: list[LeaderboardEntry]