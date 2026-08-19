import json
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from app.diversity import DiversityChecker, evolve_with_diversity_check, personality_similarity
from app.evolution import EvolutionEngine
from app.models.evolution import EvolutionInput
from app.models.personality import Personality
from app.ollama_manager import OllamaManager
from app.personalities import PERSONALITIES, get_personality

HOST = "http://ollama.test"


@pytest.fixture
def evolution_input():
    creative = get_personality("creative")
    return EvolutionInput(
        eliminated_personality=creative,
        average_score=4.5,
        strengths=creative.specialties,
        weaknesses=creative.weaknesses,
    )


def test_identical_personality_is_maximally_similar_to_itself():
    creative = get_personality("creative")
    assert personality_similarity(creative, creative) == pytest.approx(1.0, abs=0.01)


def test_near_duplicate_is_flagged_too_similar():
    creative = get_personality("creative")
    near_duplicate = Personality(
        id="creative_2",
        name="Creative Engineer",  # shares "Creative" word with original
        description=creative.description,
        system_prompt=creative.system_prompt,  # identical prompt
        specialties=creative.specialties,
        weaknesses=creative.weaknesses,
    )

    checker = DiversityChecker()
    assert checker.is_too_similar(near_duplicate, [creative]) is True


def test_distinct_personality_is_not_flagged():
    scientist = get_personality("scientist")
    minimalist = get_personality("minimalist")

    checker = DiversityChecker()
    assert checker.is_too_similar(minimalist, [scientist]) is False


def test_most_similar_returns_the_closest_match():
    creative = get_personality("creative")
    checker = DiversityChecker()

    match, score = checker.most_similar(creative, PERSONALITIES)
    # Comparing Creative against the full roster (which includes Creative
    # itself) should return itself as the closest match, score 1.0.
    assert match.id == "creative"
    assert score == pytest.approx(1.0, abs=0.01)


@respx.mock
async def test_evolve_with_diversity_check_regenerates_until_diverse(evolution_input):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)

    creative = get_personality("creative")
    too_similar_draft = Personality(
        id="creative_2", name="Creative Two", description=creative.description,
        system_prompt=creative.system_prompt, specialties=creative.specialties, weaknesses=creative.weaknesses,
    )
    diverse_draft = Personality(
        id="pragmatist", name="Pragmatist", description="Grounded, step-by-step problem solver.",
        system_prompt="You are the Pragmatist. You favor simple, tested, boring solutions over novelty.",
        specialties=["risk reduction", "proven methods"], weaknesses=["low originality"],
    )

    engine.evolve = AsyncMock(side_effect=[too_similar_draft, diverse_draft])

    result = await evolve_with_diversity_check(
        engine, evolution_input, existing_personalities=[creative], max_attempts=3
    )

    assert result.id == "pragmatist"
    assert engine.evolve.await_count == 2


async def test_evolve_with_diversity_check_raises_after_max_attempts(evolution_input):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)

    creative = get_personality("creative")
    always_too_similar = Personality(
        id="creative_2", name="Creative Two", description=creative.description,
        system_prompt=creative.system_prompt, specialties=creative.specialties, weaknesses=creative.weaknesses,
    )
    engine.evolve = AsyncMock(return_value=always_too_similar)

    with pytest.raises(ValueError):
        await evolve_with_diversity_check(engine, evolution_input, existing_personalities=[creative], max_attempts=2)

    assert engine.evolve.await_count == 2