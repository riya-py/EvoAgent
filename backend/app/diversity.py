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


# ---------------------------------------------------------------------------
# Diversity checking
# ---------------------------------------------------------------------------


def _tokens(text: str) -> set[str]:
    """Return normalized word tokens for lightweight text similarity."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def personality_similarity(a: Personality, b: Personality) -> float:
    """
    Estimate how similar two personalities are.

    Returns a value between 0.0 and 1.0:
        1.0 = effectively identical
        0.0 = no meaningful overlap
    """
    if a.id == b.id:
        return 1.0

    # Identical system prompts indicate effectively identical behavior.
    if a.system_prompt.strip() == b.system_prompt.strip():
        return 1.0

    text_a = " ".join(
        [
            a.name,
            a.description,
            a.system_prompt,
            " ".join(a.specialties),
            " ".join(a.weaknesses),
        ]
    )

    text_b = " ".join(
        [
            b.name,
            b.description,
            b.system_prompt,
            " ".join(b.specialties),
            " ".join(b.weaknesses),
        ]
    )

    tokens_a = _tokens(text_a)
    tokens_b = _tokens(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)

    return intersection / union if union else 0.0


class DiversityChecker:
    """Checks whether newly evolved personalities are sufficiently distinct."""

    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold

    def most_similar(
        self,
        personality: Personality,
        existing_personalities: list[Personality],
    ) -> tuple[Personality, float]:
        """Return the existing personality most similar to the candidate."""
        if not existing_personalities:
            raise ValueError("existing_personalities cannot be empty")

        match = max(
            existing_personalities,
            key=lambda p: personality_similarity(personality, p),
        )

        score = personality_similarity(personality, match)

        return match, score

    def is_too_similar(
        self,
        personality: Personality,
        existing_personalities: list[Personality],
    ) -> bool:
        """Return True when the candidate is too similar to an existing personality."""
        if not existing_personalities:
            return False

        _, score = self.most_similar(personality, existing_personalities)

        return score >= self.threshold


async def evolve_with_diversity_check(
    engine: EvolutionEngine,
    evolution_input: EvolutionInput,
    existing_personalities: list[Personality],
    max_attempts: int = 3,
) -> Personality:
    """
    Evolve repeatedly until the generated personality is sufficiently
    different from the existing roster.

    Raises:
        ValueError: if every attempt produces a personality that is too similar.
    """
    checker = DiversityChecker()

    for attempt in range(1, max_attempts + 1):
        candidate = await engine.evolve(evolution_input)

        if not checker.is_too_similar(
            candidate,
            existing_personalities,
        ):
            return candidate

        logger.warning(
            "Evolution attempt %d/%d produced a personality too similar "
            "to the existing roster.",
            attempt,
            max_attempts,
        )

    raise ValueError(
        f"Evolution failed diversity check after {max_attempts} attempts"
    )