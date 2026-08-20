import json
import re

import pytest
import respx
from httpx import Response

from app import arena_service
from app.events import EventType
from app.main import app
from fastapi.testclient import TestClient

HOST = "http://ollama.test"

NEWBORN_DRAFT = {
    "name": "Strategic Engineer",
    "description": "Combines strategic framing with concrete engineering tradeoffs.",
    "system_prompt": "You are the Strategic Engineer. You frame answers around goals but ground them in feasibility.",
    "specialties": ["goal framing", "practical tradeoff analysis"],
    "weaknesses": ["can overexplain simple questions"],
}


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


@pytest.fixture(autouse=True)
def _reset_engine():
    arena_service.reset_engine()
    yield
    arena_service.reset_engine()


@pytest.fixture
def mocked_ollama():
    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]}))
        respx.post(f"{HOST}/api/generate").mock(side_effect=_responder)
        yield


async def test_service_event_bus_streams_a_full_round(mocked_ollama):
    """Drives the same path the WebSocket route relays: subscribe to the
    shared engine's bus, run a round through the service layer, confirm
    every event type from the spec's list shows up in the right order."""
    from app.database import init_db

    init_db()  # normally done by the app's lifespan; this test bypasses TestClient
    engine = await arena_service.get_engine()
    queue = engine.event_bus.subscribe()

    await arena_service.ask_question("Explain TCP congestion control.")

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e.type for e in events]

    assert types[0] == EventType.ROUND_STARTED
    assert types[-1] == EventType.ROUND_COMPLETED
    for expected in [
        EventType.AGENT_STARTED, EventType.AGENT_COMPLETED, EventType.JUDGING_STARTED,
        EventType.JUDGE_COMPLETED, EventType.SCORES_UPDATED, EventType.AGENT_ELIMINATED,
        EventType.EVOLUTION_STARTED, EventType.NEW_AGENT_CREATED,
    ]:
        assert expected in types


def test_websocket_endpoint_connects_and_streams_round_started(mocked_ollama):
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/arena") as websocket:
            response = client.post("/api/arena/question", json={"question": "Explain TCP congestion control."})
            assert response.status_code == 200

            first_event = websocket.receive_json()
            assert first_event["type"] == "ROUND_STARTED"
            assert first_event["round_number"] == 1