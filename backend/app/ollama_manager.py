"""
OllamaManager — Phase 1.

Everything the rest of the app knows about talking to Ollama lives here.
Later phases (Agent, Judge, Evolution) call through this class rather
than hitting httpx directly, so retry/timeout/logging behavior stays
in one place.
"""
from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator, Optional

import httpx

from app.config import settings
from app.models.ollama import GenerationResult, HealthStatus, ModelInfo

logger = logging.getLogger(__name__)


class OllamaManager:
    def __init__(self, host: Optional[str] = None, timeout: Optional[int] = None):
        self.host = (host or settings.ollama_host).rstrip("/")
        self.timeout = timeout or settings.ollama_timeout_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.host, timeout=self.timeout)

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------
    async def list_models(self) -> list[ModelInfo]:
        """Return every model Ollama currently has installed locally."""
        async with self._client() as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()

        models: list[ModelInfo] = []
        for entry in data.get("models", []):
            details = entry.get("details", {})
            models.append(
                ModelInfo.from_family_guess(
                    name=entry.get("name", "unknown"),
                    size_bytes=entry.get("size"),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                )
            )
        logger.info("Discovered %d installed Ollama model(s)", len(models))
        return models

    async def model_exists(self, model_name: str) -> bool:
        models = await self.list_models()
        installed = {m.name for m in models}
        # Allow "qwen2.5" to match an installed "qwen2.5:7b"-style tag.
        if model_name in installed:
            return True
        return any(name.split(":")[0] == model_name for name in installed)

    async def find_model_by_family(self, family: str) -> Optional[str]:
        """
        Return the name of an installed model belonging to `family`
        (e.g. "qwen", "llama", "mistral", "gemma"), or None if nothing
        installed matches. Used to resolve a personality's preferred
        model family into a concrete, actually-installed model name.
        """
        models = await self.list_models()
        for m in models:
            if m.family == family:
                return m.name
        return None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
    ) -> GenerationResult:
        """Single non-streaming generation call. Never raises — failures
        come back as a GenerationResult with success=False so callers
        (Agents, later on) can handle a bad model/timeout gracefully."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": settings.ollama_num_ctx, "num_predict": settings.ollama_num_predict},
        }
        if system:
            payload["system"] = system

        start = time.perf_counter()
        try:
            async with self._client() as client:
                resp = await client.post("/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning("Generation failed for model=%s: %s", model, exc)
            return GenerationResult(
                model=model,
                prompt=prompt,
                success=False,
                response_time_ms=elapsed_ms,
                error=str(exc),
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        return GenerationResult(
            model=model,
            prompt=prompt,
            response=data.get("response", ""),
            success=True,
            response_time_ms=elapsed_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    async def stream(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Yield response text chunks as they arrive from Ollama."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"num_ctx": settings.ollama_num_ctx, "num_predict": settings.ollama_num_predict},
        }
        if system:
            payload["system"] = system

        async with self._client() as client:
            async with client.stream("POST", "/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    piece = chunk.get("response", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    async def health_check(self) -> HealthStatus:
        try:
            models = await self.list_models()
            return HealthStatus(
                ollama_reachable=True,
                host=self.host,
                models_installed=len(models),
            )
        except httpx.HTTPError as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return HealthStatus(
                ollama_reachable=False,
                host=self.host,
                detail=str(exc),
            )


# Shared instance the rest of the app can import directly.
ollama_manager = OllamaManager()