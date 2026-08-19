"""
Peer voting schemas — Phase 7.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PeerVote(BaseModel):
    voter_agent_id: str
    voted_for_letter: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class PeerVotingResult(BaseModel):
    votes: list[PeerVote]
    vote_counts: dict[str, int] = {}  # letter -> count of successful votes

    @property
    def total_votes_cast(self) -> int:
        return sum(1 for v in self.votes if v.success)