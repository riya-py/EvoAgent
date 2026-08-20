import asyncio
import json
import re

import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.arena_engine import ArenaEngine
from app.events import EventBus, EventType
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


def _drain(queue: asyncio.Queue) -> list:
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


@pytest.fixture
def mocked_ollama():
    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
        respx.post(f"{HOST}/api/generate").mock(side_effect=_responder)
        yield


async def test_run_round_emits_full_event_sequence_with_evolution(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    bus = EventBus()
    engine = ArenaEngine(
        agents=_agents(manager), manager=manager, evolve_on_elimination=True, event_bus=bus
    )
    queue = bus.subscribe()

    await engine.run_round("Explain TCP congestion control.")
    events = _drain(queue)
    types = [e.type for e in events]

    # Phase boundaries are strictly ordered (each phase fully awaits the
    # previous one) even though *within* a phase, agents/judges finish
    # in a non-deterministic order.
    assert types[0] == EventType.ROUND_STARTED
    assert types[-1] == EventType.ROUND_COMPLETED
    assert types.count(EventType.AGENT_STARTED) == 8
    assert types.count(EventType.AGENT_COMPLETED) == 8
    assert types.count(EventType.JUDGE_COMPLETED) == 3
    assert types.count(EventType.SCORES_UPDATED) == 1
    assert types.count(EventType.AGENT_ELIMINATED) == 1
    assert types.count(EventType.EVOLUTION_STARTED) == 1
    assert types.count(EventType.NEW_AGENT_CREATED) == 1

    judging_started_index = types.index(EventType.JUDGING_STARTED)
    last_agent_event_index = max(
        i for i, t in enumerate(types) if t in (EventType.AGENT_STARTED, EventType.AGENT_COMPLETED)
    )
    assert judging_started_index > last_agent_event_index

    scores_index = types.index(EventType.SCORES_UPDATED)
    last_judge_index = max(i for i, t in enumerate(types) if t == EventType.JUDGE_COMPLETED)
    assert scores_index > last_judge_index

    eliminated_index = types.index(EventType.AGENT_ELIMINATED)
    assert eliminated_index > scores_index

    evolution_started_index = types.index(EventType.EVOLUTION_STARTED)
    new_agent_index = types.index(EventType.NEW_AGENT_CREATED)
    assert evolution_started_index > eliminated_index
    assert new_agent_index > evolution_started_index


async def test_run_round_without_event_bus_does_not_error(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager)  # no event_bus

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.round_number == 1  # ran normally, nothing to publish to


async def test_events_carry_the_correct_round_number(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    bus = EventBus()
    engine = ArenaEngine(agents=_agents(manager), manager=manager, event_bus=bus)
    queue = bus.subscribe()

    await engine.run_round("Q1")
    first_round_events = _drain(queue)
    assert all(e.round_number == 1 for e in first_round_events)

    await engine.run_round("Q2")
    second_round_events = _drain(queue)
    assert all(e.round_number == 2 for e in second_round_events)