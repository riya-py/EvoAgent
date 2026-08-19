import json

import pytest
import respx
from httpx import Response

from app.evolution import EvolutionEngine, slugify
from app.models.evolution import EvolutionInput
from app.ollama_manager import OllamaManager
from app.personalities import get_personality

HOST = "http://ollama.test"

VALID_DRAFT = {
    "name": "Creative Engineer",
    "description": "Unconventional ideas grounded in technical feasibility.",
    "system_prompt": "You are the Creative Engineer. You generate novel ideas but validate them for feasibility.",
    "specialties": ["unconventional ideas", "technical feasibility"],
    "weaknesses": ["can be slower to respond due to double-checking"],
}


@pytest.fixture
def manager():
    return OllamaManager(host=HOST, timeout=5)


@pytest.fixture
def evolution_input():
    creative = get_personality("creative")
    return EvolutionInput(
        eliminated_personality=creative,
        average_score=4.5,
        critiques=["Poor factual accuracy.", "Great original ideas though."],
        strengths=creative.specialties,
        weaknesses=creative.weaknesses,
        failed_questions=["Explain load-bearing structures."],
        successful_questions=["Design a chair."],
    )


def test_slugify_produces_clean_ids():
    assert slugify("Creative Engineer") == "creative_engineer"
    assert slugify("  Weird!!  Name??  ") == "weird_name"
    assert slugify("") == "personality"


@respx.mock
async def test_evolve_produces_personality_with_computed_lineage(manager, evolution_input):
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": json.dumps(VALID_DRAFT)}))

    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
    child = await engine.evolve(evolution_input)

    assert child.name == "Creative Engineer"
    assert child.id == "creative_engineer"
    assert child.generation == 1  # parent (Creative) is generation 0
    assert child.parent_agent == "creative"
    assert "technical feasibility" in child.specialties


@respx.mock
async def test_evolve_handles_markdown_fenced_json(manager, evolution_input):
    fenced = f"```json\n{json.dumps(VALID_DRAFT)}\n```"
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": fenced}))

    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
    child = await engine.evolve(evolution_input)

    assert child.name == "Creative Engineer"


@respx.mock
async def test_evolve_raises_on_generation_failure(manager, evolution_input):
    import httpx

    respx.post(f"{HOST}/api/generate").mock(side_effect=httpx.ConnectError("boom"))

    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
    with pytest.raises(ValueError):
        await engine.evolve(evolution_input)


@respx.mock
async def test_evolve_raises_on_malformed_json(manager, evolution_input):
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": "not json at all"}))

    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
    with pytest.raises(ValueError):
        await engine.evolve(evolution_input)


def test_build_user_prompt_includes_history(manager, evolution_input):
    engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
    prompt = engine.build_user_prompt(evolution_input)

    assert "Creative" in prompt
    assert "Poor factual accuracy." in prompt
    assert "Design a chair." in prompt
    assert "Explain load-bearing structures." in prompt