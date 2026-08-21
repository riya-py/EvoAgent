"""
GroqManager — hosted-API alternative to OllamaManager.

Groq's API is OpenAI-compatible (chat completions), which is a
different shape than Ollama's native /api/generate. This class exists
purely to translate that shape back into the exact same
GenerationResult / ModelInfo / HealthStatus contracts OllamaManager
uses, so nothing downstream (Agent, Judge, Evolution, agent_factory)
needs to know or care which provider is actually active — they just
call manager.generate(), manager.list_models(), etc. either way.

This is intentionally NOT a subclass of OllamaManager — it's a
duck-typed drop-in. See app/ollama_manager.py's bottom-of-file factory
for how the active provider gets selected.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Optional

import httpx

from app.config import settings
from app.models.ollama import GenerationResult, HealthStatus, ModelInfo

logger = logging.getLogger(__name__)


class GroqManager:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.api_key = api_key or settings.groq_api_key
        self.base_url = (base_url or settings.groq_base_url).rstrip("/")
        self.timeout = timeout or settings.groq_timeout_seconds
        # Kept for parity with OllamaManager's constructor/attributes —
        # some callers (health check display, logs) read `.host`.
        self.host = self.base_url
        # Caps how many Groq calls this instance has in flight at once —
        # see groq_max_concurrency in config.py for why this matters.
        self._semaphore = asyncio.Semaphore(settings.groq_max_concurrency)

    def _client(self) -> httpx.AsyncClient:
        if not self.api_key:
            logger.warning(
                "GROQ_API_KEY is not set — Groq calls will fail with a 401 "
                "until it's added to .env."
            )
        headers = {"Authorization": f"Bearer {self.api_key or ''}"}
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, headers=headers)

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------
    async def list_models(self) -> list[ModelInfo]:
        """Return every model Groq currently hosts. Reuses the same
        family-guessing helper OllamaManager uses, since Groq's model
        names (e.g. 'llama-3.3-70b-versatile', 'gemma2-9b-it') happen
        to contain the same family keywords."""
        async with self._client() as client:
            resp = await client.get("/models")
            resp.raise_for_status()
            data = resp.json()

        models: list[ModelInfo] = [
            ModelInfo.from_family_guess(name=entry.get("id", "unknown"))
            for entry in data.get("data", [])
        ]
        logger.info("Discovered %d Groq-hosted model(s)", len(models))
        return models

    async def model_exists(self, model_name: str) -> bool:
        models = await self.list_models()
        return any(m.name == model_name for m in models)

    async def find_model_by_family(self, family: str) -> Optional[str]:
        models = await self.list_models()
        for m in models:
            if m.family == family:
                return m.name
        return None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _build_messages(self, prompt: str, system: Optional[str]) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
    ) -> GenerationResult:
        """Single non-streaming generation call. Never raises — failures
        come back as a GenerationResult with success=False, matching
        OllamaManager's contract exactly.

        Queues behind self._semaphore (see groq_max_concurrency) and
        retries a bounded number of times on 429, honoring Groq's
        `retry-after` header when present."""
        payload = {
            "model": model,
            "messages": self._build_messages(prompt, system),
            "stream": False,
            "max_tokens": settings.groq_max_tokens,
        }

        start = time.perf_counter()
        async with self._semaphore:
            attempt = 0
            while True:
                try:
                    async with self._client() as client:
                        resp = await client.post("/chat/completions", json=payload)
                        if resp.status_code == 429 and attempt < settings.groq_max_retries:
                            wait_s = float(
                                resp.headers.get("retry-after", settings.groq_retry_fallback_seconds)
                            )
                            attempt += 1
                            logger.info(
                                "Groq rate-limited (model=%s), retry %d/%d in %.1fs",
                                model, attempt, settings.groq_max_retries, wait_s,
                            )
                            await asyncio.sleep(wait_s)
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    logger.warning("Groq generation failed for model=%s: %s", model, exc)
                    return GenerationResult(
                        model=model,
                        prompt=prompt,
                        success=False,
                        response_time_ms=elapsed_ms,
                        error=str(exc),
                    )
                break

        elapsed_ms = (time.perf_counter() - start) * 1000
        choice = (data.get("choices") or [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return GenerationResult(
            model=model,
            prompt=prompt,
            response=text,
            success=True,
            response_time_ms=elapsed_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    async def stream(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Yield response text chunks as they arrive (SSE 'data: ...' lines,
        OpenAI-compatible format)."""
        payload = {
            "model": model,
            "messages": self._build_messages(prompt, system),
            "stream": True,
            "max_tokens": settings.groq_max_tokens,
        }

        async with self._client() as client:
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    import json as _json
                    chunk = _json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    piece = delta.get("content", "")
                    if piece:
                        yield piece

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    async def health_check(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(
                ollama_reachable=False,
                host=self.host,
                detail="GROQ_API_KEY is not set",
            )
        try:
            models = await self.list_models()
            return HealthStatus(
                ollama_reachable=True,
                host=self.host,
                models_installed=len(models),
            )
        except httpx.HTTPError as exc:
            logger.warning("Groq health check failed: %s", exc)
            return HealthStatus(
                ollama_reachable=False,
                host=self.host,
                detail=str(exc),
            )