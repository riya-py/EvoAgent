"""
AI Arena — FastAPI entrypoint.

Phase 0 scope: app boots, DB initializes, Ollama reachability is checked
(non-fatal — the API should still come up even if Ollama is offline),
and GET /api/health reports on all three.

Per the phase plan: FastAPI stays a thin shell. Arena/agent/judge logic
gets added to app/ in later phases and is only *wired up* here — this
file should never contain arena logic itself.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import check_db, init_db
from app.logging_config import setup_logging
from app.ollama_manager import ollama_manager
from app.routers.arena import router as arena_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.env)
    init_db()

    health = await ollama_manager.health_check()
    if health.ollama_reachable:
        logger.info(
            "Ollama connection OK — %d model(s) available at %s",
            health.models_installed,
            health.host,
        )
    else:
        logger.warning(
            "Ollama not reachable at %s (%s). API will still start; "
            "generation calls will fail until Ollama is up.",
            health.host,
            health.detail,
        )

    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(arena_router)


@app.get("/api/health")
async def health():
    db_ok = check_db()
    ollama_status = await ollama_manager.health_check()

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "env": settings.env,
        "database": {"connected": db_ok},
        "ollama": ollama_status.model_dump(),
    }