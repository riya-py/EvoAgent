"""
Elimination schema — Phase 9.

Per the spec: an eliminated agent is never deleted. This record — plus
the Agent object itself, which ArenaEngine keeps in
`_eliminated_agents` rather than discarding — is what lets you ask
"what happened to the Scientist in Round 5?" later (fully answerable
once Phase 13 persists this to SQLite; for now it lives in memory on
the ArenaEngine instance).
"""
from __future__ import annotations

from pydantic import BaseModel


class EliminationRecord(BaseModel):
    agent_id: str
    personality_name: str
    round_number: int
    final_score: float
    reason: str