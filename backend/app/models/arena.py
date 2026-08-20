"""
RoundOutcome schema — Phase 8.

The complete result of one ArenaEngine.run_round() call: every step
from the spec's flow diagram bundled into one object —
    answers -> judge scores -> (optional) peer votes -> leaderboard -> elimination
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.elimination import EliminationRecord
from app.models.judge import JudgeResult
from app.models.personality import Personality
from app.models.round import RoundResult
from app.models.scoring import Leaderboard
from app.models.voting import PeerVotingResult


class RoundOutcome(BaseModel):
    round_number: int
    round_result: RoundResult
    judge_results: list[JudgeResult]
    leaderboard: Leaderboard
    peer_voting: Optional[PeerVotingResult] = None
    eliminated: Optional[EliminationRecord] = None

    # letter -> agent_id for this round, kept so later phases (Evolution,
    # Persistence) can trace a judge's per-letter critique back to the
    # agent it was actually about, without re-exposing it to judges.
    reveal_map: dict[str, str] = Field(default_factory=dict)

    # The replacement personality created for the eliminated slot, when
    # Multi-Round Evolution (Phase 12) is turned on. None when either
    # nobody was eliminated this round, or evolution is off (Phase 9's
    # plain shrink-the-roster behavior).
    newborn: Optional[Personality] = None