import pytest
import respx
from httpx import Response

from app.agent import RESPONSE_GUARDRAIL, Agent
from app.ollama_manager import OllamaManager
from app.personalities import get_personality

HOST = "http://ollama.test"


@pytest.fixture
def manager():
    return OllamaManager(host=HOST, timeout=5)


@pytest.fixture
def scientist_agent(manager):
    return Agent(personality=get_personality("scientist"), model="qwen2.5:7b", manager=manager)


def test_build_system_prompt_includes_personality_and_guardrail(scientist_agent):
    prompt = scientist_agent.build_system_prompt()
    assert "Scientist" in prompt
    assert "evidence" in prompt.lower()
    assert RESPONSE_GUARDRAIL in prompt


@respx.mock
async def test_answer_success_produces_agent_answer(scientist_agent):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(
            200,
            json={"response": "TCP congestion control works by...", "eval_count": 20, "prompt_eval_count": 8},
        )
    )

    result = await scientist_agent.answer("Explain TCP congestion control.")

    assert result.agent_id == "scientist"
    assert result.personality_name == "Scientist"
    assert result.model == "qwen2.5:7b"
    assert result.success is True
    assert "TCP congestion control" in result.answer
    assert result.generation_time_ms >= 0
    assert scientist_agent.history == [result]


@respx.mock
async def test_answer_failure_is_tracked_not_raised(scientist_agent):
    import httpx

    respx.post(f"{HOST}/api/generate").mock(side_effect=httpx.ConnectError("boom"))

    result = await scientist_agent.answer("Explain TCP congestion control.")

    assert result.success is False
    assert result.error is not None
    assert len(scientist_agent.history) == 1


@respx.mock
async def test_statistics_aggregate_across_multiple_calls(scientist_agent):
    respx.post(f"{HOST}/api/generate").mock(
        side_effect=[
            Response(200, json={"response": "answer one"}),
            Response(200, json={"response": "answer two"}),
        ]
    )

    await scientist_agent.answer("Question 1")
    await scientist_agent.answer("Question 2")

    stats = scientist_agent.statistics
    assert stats.total_calls == 2
    assert stats.success_count == 2
    assert stats.failure_count == 0
    assert stats.avg_generation_time_ms >= 0


@respx.mock
async def test_different_personalities_produce_different_system_prompts(manager):
    """Same Agent architecture, 8 different personalities -> 8 different
    system prompts / styles, satisfying Phase 3's done condition."""
    from app.personalities import list_personalities

    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": "some answer"})
    )

    agents = [Agent(personality=p, model="qwen2.5:7b", manager=manager) for p in list_personalities()]
    prompts = {a.build_system_prompt() for a in agents}

    assert len(agents) == 8
    assert len(prompts) == 8  # all distinct

    for agent in agents:
        result = await agent.answer("Explain TCP congestion control.")
        assert result.success is True