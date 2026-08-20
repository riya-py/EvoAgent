import json
import re

import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.arena_engine import ArenaEngine
from app.ollama_manager import OllamaManager
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


def _make_responder(newborn_draft=NEWBORN_DRAFT):
    def responder(request):
        payload = json.loads(request.content)
        system = payload.get("system", "")
        prompt = payload.get("prompt", "")

        if "JSON array" in system:  # judge
            letters = re.findall(r"Answer ([A-H]):", prompt)
            scores = [
                {"answer_id": l, "accuracy": 10 - i, "reasoning": 10 - i, "utility": 10 - i, "overall": float(10 - i), "critique": "ok"}
                for i, l in enumerate(letters)
            ]
            return Response(200, json={"response": json.dumps(scores)})

        if "Evolution Engine" in system:  # evolution
            return Response(200, json={"response": json.dumps(newborn_draft)})

        if "JSON object" in system:  # peer vote
            letters = re.findall(r"Answer ([A-H]):", prompt)
            return Response(200, json={"response": json.dumps({"vote": letters[0] if letters else "A"})})

        return Response(200, json={"response": "A reasonable answer to the question."})

    return responder


@pytest.fixture
def mocked_ollama():
    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
        respx.post(f"{HOST}/api/generate").mock(side_effect=_make_responder())
        yield


async def test_evolve_on_elimination_keeps_roster_size_constant(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.eliminated is not None
    assert outcome.newborn is not None
    assert outcome.newborn.name == "Strategic Engineer"
    assert len(engine.active_agents) == 8  # replaced, not shrunk


async def test_newborn_has_correct_lineage(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.newborn.generation == 1
    assert outcome.newborn.parent_agent == outcome.eliminated.agent_id
    newborn_agent = engine.get_agent(outcome.newborn.id)
    assert newborn_agent is not None
    assert newborn_agent.agent_id in [a.agent_id for a in engine.active_agents]


async def test_evolve_on_elimination_false_still_shrinks_roster(mocked_ollama):
    """Default behavior (Phase 9) must be unchanged when the flag is off."""
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=False)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.newborn is None
    assert len(engine.active_agents) == 7


async def test_run_tournament_runs_rounds_in_order(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)

    outcomes = await engine.run_tournament(["Q1", "Q2", "Q3"])

    assert [o.round_number for o in outcomes] == [1, 2, 3]
    assert len(engine.history) == 3
    # Roster stays at 8 across every round since evolution replaces the slot each time.
    assert len(engine.active_agents) == 8
    assert len(engine.eliminated) == 3


async def test_lineage_grows_with_each_evolution(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)

    assert len(engine.lineage) == 8  # original 8, generation 0

    await engine.run_round("Q1")
    assert len(engine.lineage) == 9

    await engine.run_round("Q2")
    assert len(engine.lineage) == 10


async def test_get_lineage_chain_walks_from_root_to_newborn(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)

    outcome = await engine.run_round("Explain TCP congestion control.")
    chain = engine.get_lineage_chain(outcome.newborn.id)

    assert len(chain) == 2  # original eliminated personality -> newborn
    assert chain[0].id == outcome.eliminated.agent_id
    assert chain[1].id == outcome.newborn.id


async def test_diversity_check_regenerates_a_too_similar_newborn(mocked_ollama):
    """If the Evolution LLM's first draft is essentially a clone of a
    *surviving* personality (Scientist, who is not eliminated this
    round), DiversityChecker should force a retry — then accept a
    genuinely distinct draft on the second attempt."""
    from app.personalities import get_personality

    scientist = get_personality("scientist")
    scientist_clone_draft = {
        "name": "Scientist Prime",
        "description": scientist.description,
        "system_prompt": scientist.system_prompt,
        "specialties": scientist.specialties,
        "weaknesses": scientist.weaknesses,
    }

    call_state = {"evolution_calls": 0}
    base_responder = _make_responder()

    def responder(request):
        payload = json.loads(request.content)
        if "Evolution Engine" in payload.get("system", ""):
            call_state["evolution_calls"] += 1
            if call_state["evolution_calls"] == 1:
                return Response(200, json={"response": json.dumps(scientist_clone_draft)})
            return Response(200, json={"response": json.dumps(NEWBORN_DRAFT)})
        return base_responder(request)

    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
        respx.post(f"{HOST}/api/generate").mock(side_effect=responder)

        manager = OllamaManager(host=HOST, timeout=5)
        engine = ArenaEngine(agents=_agents(manager), manager=manager, evolve_on_elimination=True)
        outcome = await engine.run_round("Explain TCP congestion control.")

    assert call_state["evolution_calls"] == 2
    assert outcome.newborn.name == "Strategic Engineer"