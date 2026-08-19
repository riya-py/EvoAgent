"""
Pydantic schemas used by the OllamaManager (Phase 1).

Kept separate from ollama_manager.py so later phases (Agent, Judge, ...)
can import these shapes without importing the manager itself.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Families we explicitly recognize when categorizing installed models.
# Anything else falls back to "other".
KNOWN_MODEL_FAMILIES = ["qwen", "llama", "mistral", "gemma"]


class ModelInfo(BaseModel):
    """A single model reported by `GET /api/tags` on the Ollama server."""

    name: str
    family: str = "other"
    size_bytes: Optional[int] = None
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None

    @classmethod
    def from_family_guess(cls, name: str, **kwargs) -> "ModelInfo":
        lowered = name.lower()
        family = next((f for f in KNOWN_MODEL_FAMILIES if f in lowered), "other")
        return cls(name=name, family=family, **kwargs)


class GenerationResult(BaseModel):
    """
    Result of a single OllamaManager.generate() call.

    This is the record we track per-call: which model answered, how long
    it took, whether it succeeded, and token usage when Ollama reports it.
    """

    model: str
    prompt: str
    response: str = ""
    success: bool = True
    response_time_ms: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    error: Optional[str] = None

    @property
    def total_tokens(self) -> Optional[int]:
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class HealthStatus(BaseModel):
    ollama_reachable: bool
    host: str
    models_installed: int = 0
    detail: Optional[str] = None