"""
Real-time events — Phase 15.

A minimal in-process pub/sub bus: ArenaEngine publishes ArenaEvents as a
round progresses, and any number of subscribers (typically one per
connected WebSocket client) get their own asyncio.Queue fed live.

Event types match the spec's flow exactly:
    ROUND_STARTED -> AGENT_STARTED -> AGENT_COMPLETED (xN, concurrent)
    -> JUDGING_STARTED -> JUDGE_COMPLETED (x3, concurrent)
    -> SCORES_UPDATED -> AGENT_ELIMINATED
    -> EVOLUTION_STARTED -> NEW_AGENT_CREATED (only if evolution ran)
    -> ROUND_COMPLETED
"""
from __future__ import annotations

import asyncio
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    ROUND_STARTED = "ROUND_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    JUDGING_STARTED = "JUDGING_STARTED"
    JUDGE_COMPLETED = "JUDGE_COMPLETED"
    SCORES_UPDATED = "SCORES_UPDATED"
    AGENT_ELIMINATED = "AGENT_ELIMINATED"
    EVOLUTION_STARTED = "EVOLUTION_STARTED"
    NEW_AGENT_CREATED = "NEW_AGENT_CREATED"
    ROUND_COMPLETED = "ROUND_COMPLETED"


class ArenaEvent(BaseModel):
    type: EventType
    round_number: int
    data: dict = Field(default_factory=dict)


class EventBus:
    """Fan-out pub/sub. Each subscriber gets its own queue so one slow
    consumer can't block another; publish() only ever appends, it never
    waits on a full queue (queues are unbounded)."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue[ArenaEvent]] = []

    def subscribe(self) -> asyncio.Queue[ArenaEvent]:
        queue: asyncio.Queue[ArenaEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ArenaEvent]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def publish(self, event: ArenaEvent) -> None:
        for queue in list(self._subscribers):
            await queue.put(event)