"""
Arena API routes — Phase 14, plus the Phase 15 WebSocket stream.

Thin HTTP <-> app.arena_service translation layer. No arena logic
lives here — every route just calls into arena_service and shapes the
HTTP response (status codes, 404s) around whatever it returns.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app import arena_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["arena"])


class QuestionRequest(BaseModel):
    question: str


@router.post("/arena/question")
async def post_question(body: QuestionRequest):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    return await arena_service.ask_question(body.question)


@router.get("/arena/current")
async def get_current_state():
    return await arena_service.current_state()


@router.get("/agents")
async def get_agents():
    return await arena_service.list_agent_summaries()


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    summary = await arena_service.get_agent_summary(agent_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return summary


@router.get("/rounds")
async def get_rounds():
    return await arena_service.list_round_summaries()


@router.get("/rounds/{round_number}")
async def get_round(round_number: int):
    outcome = await arena_service.get_round(round_number)
    if outcome is None:
        raise HTTPException(status_code=404, detail="round not found")
    return outcome


@router.get("/leaderboard")
async def get_leaderboard():
    leaderboard = await arena_service.latest_leaderboard()
    if leaderboard is None:
        raise HTTPException(status_code=404, detail="no rounds played yet")
    return leaderboard


@router.get("/evolution")
async def get_evolution():
    return await arena_service.lineage_snapshot()


@router.websocket("/ws/arena")
async def ws_arena(websocket: WebSocket):
    """Relays the shared engine's event bus straight to the client, one
    ArenaEvent per message, for as long as the socket stays open."""
    await websocket.accept()
    engine = await arena_service.get_engine()
    queue = engine.event_bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /api/ws/arena")
    finally:
        engine.event_bus.unsubscribe(queue)