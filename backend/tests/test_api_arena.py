import json
import re

import pytest
import respx
from httpx import Response

from app import arena_service
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


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_get_agents_lists_all_eight_before_any_round(client, mocked_ollama):
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 8
    assert all(a["status"] == "ACTIVE" for a in agents)


def test_get_agent_detail_for_known_agent(client, mocked_ollama):
    resp = client.get("/api/agents/scientist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["personality_name"] == "Scientist"
    assert body["status"] == "ACTIVE"


def test_get_agent_detail_404_for_unknown_agent(client, mocked_ollama):
    resp = client.get("/api/agents/does-not-exist")
    assert resp.status_code == 404


def test_get_rounds_is_empty_before_any_round(client, mocked_ollama):
    resp = client.get("/api/rounds")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_leaderboard_404_before_any_round(client, mocked_ollama):
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 404


def test_post_question_rejects_empty_question(client, mocked_ollama):
    resp = client.post("/api/arena/question", json={"question": "   "})
    assert resp.status_code == 400


def test_post_question_runs_a_round_and_returns_full_outcome(client, mocked_ollama):
    resp = client.post("/api/arena/question", json={"question": "Explain TCP congestion control."})
    assert resp.status_code == 200
    body = resp.json()

    assert body["round_number"] == 1
    assert len(body["round_result"]["answers"]) == 8
    assert len(body["judge_results"]) == 3
    assert len(body["leaderboard"]["entries"]) == 8
    assert body["eliminated"] is not None
    assert body["newborn"] is not None  # evolve_on_elimination defaults True for the API's engine


def test_after_a_round_leaderboard_and_rounds_endpoints_reflect_it(client, mocked_ollama):
    client.post("/api/arena/question", json={"question": "Explain TCP congestion control."})

    rounds_resp = client.get("/api/rounds")
    assert rounds_resp.status_code == 200
    rounds = rounds_resp.json()
    assert len(rounds) == 1
    assert rounds[0]["round_number"] == 1
    assert rounds[0]["success_count"] == 8

    round_detail = client.get("/api/rounds/1")
    assert round_detail.status_code == 200
    assert round_detail.json()["round_number"] == 1

    missing_round = client.get("/api/rounds/2")
    assert missing_round.status_code == 404

    leaderboard_resp = client.get("/api/leaderboard")
    assert leaderboard_resp.status_code == 200
    assert len(leaderboard_resp.json()["entries"]) == 8


def test_arena_current_reflects_state_after_a_round(client, mocked_ollama):
    client.post("/api/arena/question", json={"question": "Explain TCP congestion control."})

    resp = client.get("/api/arena/current")
    assert resp.status_code == 200
    body = resp.json()
    assert body["round_number"] == 1
    assert len(body["active_agent_ids"]) == 8  # replaced, not shrunk
    assert body["eliminated_count"] == 1


def test_evolution_lineage_grows_after_a_round(client, mocked_ollama):
    before = client.get("/api/evolution").json()
    assert len(before) == 8

    client.post("/api/arena/question", json={"question": "Explain TCP congestion control."})

    after = client.get("/api/evolution").json()
    assert len(after) == 9
    newborn = next(p for p in after if p["generation"] == 1)
    assert newborn["name"] == "Strategic Engineer"


def test_agent_detail_shows_eliminated_status_after_replacement(client, mocked_ollama):
    outcome = client.post("/api/arena/question", json={"question": "Explain TCP congestion control."}).json()
    eliminated_id = outcome["eliminated"]["agent_id"]

    resp = client.get(f"/api/agents/{eliminated_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ELIMINATED"


def test_health_endpoint_still_works_alongside_arena_routes(client, mocked_ollama):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"