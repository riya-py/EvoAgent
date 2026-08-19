"""
Evolution Engine — Phase 10.

The signature feature: takes everything build_evolution_input() gathered
about an eliminated personality and asks the Evolution LLM to design its
replacement — one that keeps what worked and targets what didn't.

Example from the spec:
    Creative (strength: unconventional ideas; weakness: poor factual
    accuracy, poor technical feasibility)
        -> Creative Engineer (strength: creativity + unconventional
           thinking; improvement: technical feasibility + factual
           checking)

id/generation/parent_agent are computed here in code — never trusted
from the LLM's JSON — matching the same MODEL != PERSONALITY discipline
from Phase 2: the LLM designs behavior, the system assigns identity.
"""
from __future__ import annotations

import logging
import re

from app.json_utils import extract_json_array
from app.models.evolution import EvolutionInput, NewPersonalityDraft
from app.models.personality import Personality
from app.ollama_manager import OllamaManager, ollama_manager

logger = logging.getLogger(__name__)

_EVOLUTION_SYSTEM_PROMPT = """\
You are the Evolution Engine for an AI personality competition. An AI \
personality was just eliminated for scoring too low. Your job is to design \
its successor: a new personality that keeps what made the original good \
and directly addresses what made it lose.

Example:
  Eliminated: "Creative" — strength: unconventional ideas; weakness: poor \
factual accuracy, poor technical feasibility.
  Evolved: "Creative Engineer" — keeps creativity and unconventional \
thinking, but is now grounded in technical feasibility and factual \
checking.

Respond with ONLY a JSON object in this exact shape and nothing else — no \
preamble, no markdown fences:
{
  "name": "Creative Engineer",
  "description": "One sentence describing this personality.",
  "system_prompt": "The full system prompt this personality will run with.",
  "specialties": ["...", "..."],
  "weaknesses": ["...", "..."]
}
"""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "personality"


class EvolutionEngine:
    def __init__(self, model: str, manager: OllamaManager | None = None):
        self.model = model
        self.manager = manager or ollama_manager

    def build_system_prompt(self) -> str:
        return _EVOLUTION_SYSTEM_PROMPT

    def build_user_prompt(self, evolution_input: EvolutionInput) -> str:
        p = evolution_input.eliminated_personality
        lines = [
            f'Eliminated personality: "{p.name}" (generation {p.generation})',
            f"Description: {p.description}",
            f"Average score across its rounds: {evolution_input.average_score}",
            f"Declared strengths: {', '.join(evolution_input.strengths) or 'none recorded'}",
            f"Declared weaknesses: {', '.join(evolution_input.weaknesses) or 'none recorded'}",
        ]
        if evolution_input.critiques:
            lines.append("Judge critiques:")
            lines.extend(f"  - {c}" for c in evolution_input.critiques)
        if evolution_input.successful_questions:
            lines.append("Questions it handled well:")
            lines.extend(f"  - {q}" for q in evolution_input.successful_questions)
        if evolution_input.failed_questions:
            lines.append("Questions it handled poorly:")
            lines.extend(f"  - {q}" for q in evolution_input.failed_questions)
        lines.append("\nDesign its successor now.")
        return "\n".join(lines)

    async def evolve(self, evolution_input: EvolutionInput) -> Personality:
        result = await self.manager.generate(
            model=self.model,
            prompt=self.build_user_prompt(evolution_input),
            system=self.build_system_prompt(),
        )
        if not result.success:
            raise ValueError(f"Evolution generation failed: {result.error}")

        parsed = extract_json_array(result.response)
        draft = NewPersonalityDraft(**parsed[0])

        parent = evolution_input.eliminated_personality
        return Personality(
            id=slugify(draft.name),
            name=draft.name,
            description=draft.description,
            system_prompt=draft.system_prompt,
            specialties=draft.specialties,
            weaknesses=draft.weaknesses,
            generation=parent.generation + 1,
            parent_agent=parent.id,
        )