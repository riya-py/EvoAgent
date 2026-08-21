"""
build_agents() — Phase 3.

Bridges Phase 2 (personalities + preferred model families) and the
Agent class: for every personality, resolve its preferred family to
whatever's actually installed in Ollama, and construct an Agent.

This is what proves the single-Agent architecture (Phase 3) generalizes
to all 8 personalities without any concurrency or arena logic yet —
that comes in Phase 4.
"""
from __future__ import annotations

import logging

from app.agent import Agent
from app.config import settings
from app.model_assignment import get_preferred_family
from app.ollama_manager import OllamaManager, ollama_manager
from app.personalities import list_personalities

logger = logging.getLogger(__name__)


async def build_agents(manager: OllamaManager | None = None) -> list[Agent]:
    """
    Build one Agent per personality, each pointed at a concrete
    installed model matching its preferred family. Falls back to
    whatever model IS installed if the preferred family is missing,
    so the arena still runs with a partial local model library.

    Dev overrides (off by default): DEV_MODEL_OVERRIDE pins every agent
    to one exact model regardless of family (avoids Ollama swapping
    models in and out of memory on slow/CPU-only hardware);
    DEV_AGENT_LIMIT runs a smaller roster instead of all 8, for a
    faster feedback loop while testing.
    """
    manager = manager or ollama_manager
    installed = await manager.list_models()

    fallback_model = installed[0].name if installed else None

    personalities = list_personalities()
    if settings.dev_agent_limit:
        personalities = personalities[: settings.dev_agent_limit]
        logger.warning(
            "DEV_AGENT_LIMIT=%d set — running with %d of 8 personalities",
            settings.dev_agent_limit,
            len(personalities),
        )

    agents: list[Agent] = []
    for personality in personalities:
        if settings.dev_model_override:
            model = settings.dev_model_override
        else:
            family = get_preferred_family(personality.id)
            model = await manager.find_model_by_family(family)

            if model is None:
                model = fallback_model
                if model is None:
                    logger.warning(
                        "No Ollama models installed at all — agent %s will fail until "
                        "a model is pulled.",
                        personality.id,
                    )
                    model = f"{family}:unavailable"
                else:
                    logger.warning(
                        "No installed model for family %r (personality %s) — "
                        "falling back to %r",
                        family,
                        personality.id,
                        model,
                    )

        agents.append(Agent(personality=personality, model=model, manager=manager))

    return agents