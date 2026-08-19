"""
Personality → preferred model family — Phase 2.

Kept in its own module, deliberately separate from app/personalities.py,
because the spec is explicit: MODEL != PERSONALITY. This is the only
place that couples the two, and it maps to a *family* (qwen/llama/
mistral/gemma), not a specific installed tag — app/agent.py resolves
the family to whatever's actually installed via
OllamaManager.find_model_by_family().

  Scientist       -> qwen
  Engineer        -> llama
  Creative        -> mistral

...matches the example in the spec; the other 5 personalities are
spread across the same 4 families, two personalities per family.
"""
from app.models.ollama import KNOWN_MODEL_FAMILIES

PERSONALITY_MODEL_FAMILY: dict[str, str] = {
    "scientist": "qwen",
    "professor": "qwen",
    "engineer": "llama",
    "researcher": "llama",
    "devils_advocate": "mistral",
    "creative": "mistral",
    "minimalist": "gemma",
    "strategist": "gemma",
}


def get_preferred_family(personality_id: str) -> str:
    try:
        family = PERSONALITY_MODEL_FAMILY[personality_id]
    except KeyError:
        raise ValueError(f"No model family assigned for personality id: {personality_id!r}") from None
    assert family in KNOWN_MODEL_FAMILIES, f"{family!r} is not a known model family"
    return family