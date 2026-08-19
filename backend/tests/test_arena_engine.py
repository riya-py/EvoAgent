import json
import re

import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.arena_engine import ArenaEngine
from app.display import format_elimination
from app.ollama_manager import OllamaManager
from app.personalities import list_personalities

HOST = "http://ollama.test"


def _agents(manager: OllamaManager) -> list[Agent]:
    return [Agent(personality=p, model="qwen2.5:7b", manager=manager) for p in list_personalities()]


def _generic_responder(request):
    """Routes a mocked /api/generate call to an agent-answer, judge-score,
    or peer-vote style response based on which system prompt was sent —
    all three go through the same endpoint in real life too."""
    payload = json.loads(request.content)
    system = payload.get("system", "")
    prompt = payload.get("prompt", "")

    if "JSON array" in system:  # judge system prompt
        letters = re.findall(r"Answer ([A-H]):", prompt)
        scores = [
            {
                "answer_id": letter,
                "accuracy": 10 - i,
                "reasoning": 10 - i,
                "utility": 10 - i,
                "overall": float(10 - i),
                "critique": "ok",
            }
            for i, letter in enumerate(letters)
        ]
        return Response(200, json={"response": json.dumps(scores)})

    if "JSON object" in system:  # peer-vote system prompt
        letters = re.findall(r"Answer ([A-H]):", prompt)
        vote = letters[0] if letters else "A"
        return Response(200, json={"response": json.dumps({"vote": vote})})

    # otherwise: a regular agent answering the arena question
    return Response(200, json={"response": "A reasonable answer to the question."})


@pytest.fixture
def mocked_ollama():
    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(
            return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        )
        respx.post(f"{HOST}/api/generate").mock(side_effect=_generic_responder)
        yield


async def test_run_round_produces_a_complete_outcome(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.round_number == 1
    assert len(outcome.round_result.answers) == 8
    assert outcome.round_result.success_count == 8
    assert len(outcome.judge_results) == 3
    assert len(outcome.leaderboard.entries) == 8
    assert outcome.peer_voting is None  # disabled by default


async def test_round_eliminates_exactly_one_agent(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.eliminated is not None
    assert len(engine.active_agents) == 7
    assert len(engine.eliminated) == 1
    # The eliminated agent must be the one ranked last on the leaderboard.
    assert outcome.eliminated.agent_id == outcome.leaderboard.entries[-1].agent_id


async def test_eliminated_agent_is_never_deleted(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager)

    outcome = await engine.run_round("Explain TCP congestion control.")
    eliminated_id = outcome.eliminated.agent_id

    assert eliminated_id not in [a.agent_id for a in engine.active_agents]
    recovered = engine.get_agent(eliminated_id)
    assert recovered is not None
    assert recovered.agent_id == eliminated_id
    assert len(recovered.history) == 1  # its one answer from the round is preserved


async def test_multiple_rounds_shrink_roster_by_one_each_time(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager)

    await engine.run_round("Q1")
    assert len(engine.active_agents) == 7

    await engine.run_round("Q2")
    assert len(engine.active_agents) == 6
    assert len(engine.eliminated) == 2
    assert len(engine.history) == 2


async def test_never_eliminates_the_last_remaining_agent(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    solo_agent = _agents(manager)[:1]
    engine = ArenaEngine(agents=solo_agent, manager=manager)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.eliminated is None
    assert len(engine.active_agents) == 1


async def test_peer_voting_enabled_flows_through_to_outcome(mocked_ollama):
    manager = OllamaManager(host=HOST, timeout=5)
    engine = ArenaEngine(agents=_agents(manager), manager=manager, peer_voting_enabled=True)

    outcome = await engine.run_round("Explain TCP congestion control.")

    assert outcome.peer_voting is not None
    assert outcome.peer_voting.total_votes_cast > 0
    assert outcome.leaderboard.peer_vote_weight > 0.0


def test_arena_engine_requires_at_least_one_agent():
    with pytest.raises(ValueError):
        ArenaEngine(agents=[])


def test_format_elimination_message():
    from app.models.elimination import EliminationRecord

    record = EliminationRecord(
        agent_id="minimalist", personality_name="Minimalist", round_number=3, final_score=4.2,
        reason="Lowest score (4.2) in round 3",
    )
    message = format_elimination(record)
    assert "Minimalist" in message
    assert "Round 3" in message
    assert "4.2" in message