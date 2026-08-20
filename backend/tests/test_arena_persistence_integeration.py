import json
import re

import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.arena_engine import ArenaEngine
from app.database import init_db
from app.ollama_manager import OllamaManager
from app.persistence import ArenaRepository
from app.personalities import list_personalities

HOST = "http://ollama.test"

NEWBORN_DRAFT = {
    "name": "Strategic Engineer",
    "description": "Combines strategic framing with concrete engineering tradeoffs.",
    "system_prompt": "You are the Strategic Engineer. You frame answers around goals but ground them in feasibility.",
    "specialties": ["goal framing", "practical tradeoff analysis"],
    "weaknesses": ["can overexplain simple questions"],
}


def _agents(manager: OllamaManager) -> list[Agent]:
    return [Agent(personality=p, model="qwen2.5:7b", manager=manager) for p in list_personalities()]


def _responder(request):
    payload = json.loads(request.content)
    system = payload.get("system", "")
    prompt = payload.get("prompt", "")

    if "JSON array" in system:
        letters = re.findall(r"Answer ([A-H]):", prompt)
        scores = [
            {"answer_id": l, "accuracy": 10 - i, "reasoning": 10 - i, "utility": 10 - i, "overall": float(10 - i), "critique": "ok"}
            for i, l in enumerate(letters)
        ]
        return Response(200, json={"response": json.dumps(scores)})

    if "Evolution Engine" in system:
        return Response(200, json={"response": json.dumps(NEWBORN_DRAFT)})

    return Response(200, json={"response": "A reasonable answer to the question."})


@pytest.fixture
def repo():
    init_db()
    return ArenaRepository()


@respx.mock
async def test_arena_engine_with_repository_persists_starting_roster(repo):
    respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
    respx.post(f"{HOST}/api/generate").mock(side_effect=_responder)

    manager = OllamaManager(host=HOST, timeout=5)
    ArenaEngine(agents=_agents(manager), manager=manager, repository=repo)

    assert repo.get_agent_record("scientist") is not None
    assert repo.get_agent_record("strategist") is not None


@respx.mock
async def test_arena_engine_with_repository_persists_each_round_automatically(repo):
    respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
    respx.post(f"{HOST}/api/generate").mock(side_effect=_responder)

    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(
        agents=_agents(manager), manager=manager, repository=repo, evolve_on_elimination=True
    )

    outcome = await engine.run_round("Explain TCP congestion control.")

    # The round's data should be queryable straight from the repository,
    # not just from engine.history in memory.
    result = repo.what_happened_to(outcome.eliminated.agent_id, round_number=1)
    assert result["eliminated"] is not None
    assert result["answer"] is not None

    # The newborn should already be a queryable agent, with its model set.
    newborn_record = repo.get_agent_record(outcome.newborn.id)
    assert newborn_record is not None
    assert newborn_record["model"]  # non-empty — inherited from the eliminated agent's model