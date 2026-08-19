import json

import httpx
import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.models.judge import AnonymizedAnswer
from app.ollama_manager import OllamaManager
from app.peer_voting import conduct_peer_voting, get_agent_vote
from app.personalities import get_personality

HOST = "http://ollama.test"

ANSWERS = [
    AnonymizedAnswer(letter="A", answer="Scientist's answer"),
    AnonymizedAnswer(letter="B", answer="Engineer's answer"),
    AnonymizedAnswer(letter="C", answer="Creative's answer"),
]
REVEAL_MAP = {"A": "scientist", "B": "engineer", "C": "creative"}


@pytest.fixture
def manager():
    return OllamaManager(host=HOST, timeout=5)


def _agent(personality_id: str, manager: OllamaManager) -> Agent:
    return Agent(personality=get_personality(personality_id), model="qwen2.5:7b", manager=manager)


@respx.mock
async def test_get_agent_vote_parses_valid_vote(manager):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": '{"vote": "C"}'})
    )

    agent = _agent("scientist", manager)
    # Scientist's own answer (A) is excluded from choices, as the arena would do.
    choices = [a for a in ANSWERS if a.letter != "A"]

    vote = await get_agent_vote(agent, "Which answer is best?", choices)

    assert vote.success is True
    assert vote.voted_for_letter == "C"
    assert vote.voter_agent_id == "scientist"


@respx.mock
async def test_get_agent_vote_rejects_vote_outside_offered_choices(manager):
    # Model tries to vote for "A" even though it wasn't offered (its own answer).
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": '{"vote": "A"}'})
    )

    agent = _agent("scientist", manager)
    choices = [a for a in ANSWERS if a.letter != "A"]

    vote = await get_agent_vote(agent, "Which answer is best?", choices)

    assert vote.success is False
    assert "not an offered" in vote.error


@respx.mock
async def test_get_agent_vote_handles_unparseable_response(manager):
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": "I like B I guess"}))

    agent = _agent("engineer", manager)
    choices = [a for a in ANSWERS if a.letter != "B"]

    vote = await get_agent_vote(agent, "Which answer is best?", choices)

    assert vote.success is False


@respx.mock
async def test_conduct_peer_voting_excludes_self_from_choices(manager):
    """Every agent's own answer must never appear in the prompt sent to it."""
    captured_prompts: dict[str, str] = {}

    def responder(request: httpx.Request):
        payload = json.loads(request.content)
        captured_prompts[payload["model"] + str(len(captured_prompts))] = payload["prompt"]
        return Response(200, json={"response": '{"vote": "A"}'})

    respx.post(f"{HOST}/api/generate").mock(side_effect=responder)

    agents = [_agent("scientist", manager), _agent("engineer", manager), _agent("creative", manager)]
    await conduct_peer_voting(agents, "Which answer is best?", ANSWERS, REVEAL_MAP)

    prompts = list(captured_prompts.values())
    scientist_prompt = next(p for p in prompts if "Scientist's answer" not in p)
    assert "Scientist's answer" not in scientist_prompt


@respx.mock
async def test_conduct_peer_voting_tallies_votes():
    manager = OllamaManager(host=HOST, timeout=5)
    agents = [_agent("scientist", manager), _agent("engineer", manager), _agent("creative", manager)]

    # scientist -> B, engineer -> C, creative -> B
    votes_in_order = [
        Response(200, json={"response": '{"vote": "B"}'}),
        Response(200, json={"response": '{"vote": "C"}'}),
        Response(200, json={"response": '{"vote": "B"}'}),
    ]
    respx.post(f"{HOST}/api/generate").mock(side_effect=votes_in_order)

    result = await conduct_peer_voting(agents, "Which answer is best?", ANSWERS, REVEAL_MAP)

    assert len(result.votes) == 3
    assert result.total_votes_cast == 3
    assert result.vote_counts == {"B": 2, "C": 1}


@respx.mock
async def test_conduct_peer_voting_survives_one_agent_failing():
    manager = OllamaManager(host=HOST, timeout=5)
    agents = [_agent("scientist", manager), _agent("engineer", manager), _agent("creative", manager)]

    call_count = {"n": 0}

    def responder(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("simulated failure")
        # "A" is scientist's own letter, but scientist's call already
        # failed above, so subsequent voters (engineer, creative) can
        # safely vote "A" without it being their own excluded letter.
        return Response(200, json={"response": '{"vote": "A"}'})

    respx.post(f"{HOST}/api/generate").mock(side_effect=responder)

    result = await conduct_peer_voting(agents, "Which answer is best?", ANSWERS, REVEAL_MAP)

    assert len(result.votes) == 3
    assert sum(1 for v in result.votes if not v.success) == 1
    assert result.total_votes_cast == 2