import asyncio
import time
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from app.agent import Agent
from app.arena_round import run_round
from app.display import format_round_table
from app.models.agent import AgentAnswer
from app.ollama_manager import OllamaManager
from app.personalities import list_personalities

HOST = "http://ollama.test"


@pytest.fixture
def eight_agents():
    manager = OllamaManager(host=HOST, timeout=5)
    return [Agent(personality=p, model="qwen2.5:7b", manager=manager) for p in list_personalities()]


@respx.mock
async def test_run_round_produces_eight_answers_in_agent_order(eight_agents):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": "some answer"})
    )

    result = await run_round(eight_agents, "Explain TCP congestion control.", round_number=1)

    assert result.round_number == 1
    assert len(result.answers) == 8
    assert result.success_count == 8
    # Order must match the agents list passed in (Scientist first, etc.)
    assert [a.agent_id for a in result.answers] == [a.agent_id for a in eight_agents]


async def test_agents_answer_concurrently_not_sequentially(eight_agents):
    async def slow_answer(question: str) -> AgentAnswer:
        await asyncio.sleep(0.05)
        return AgentAnswer(
            agent_id="x", personality_name="x", model="x", question=question, answer="ok"
        )

    for agent in eight_agents:
        agent.answer = AsyncMock(side_effect=slow_answer)

    started = time.perf_counter()
    await run_round(eight_agents, "Explain TCP congestion control.")
    elapsed = time.perf_counter() - started

    # If this were sequential it would take >= 8 * 0.05s = 0.4s. Concurrent
    # execution should land close to a single 0.05s call.
    assert elapsed < 0.2


@respx.mock
async def test_run_round_survives_one_agent_failing(eight_agents):
    import httpx

    call_count = {"n": 0}

    def responder(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("simulated failure")
        return Response(200, json={"response": "ok"})

    respx.post(f"{HOST}/api/generate").mock(side_effect=responder)

    result = await run_round(eight_agents, "Explain TCP congestion control.")

    assert len(result.answers) == 8
    assert result.success_count == 7
    assert result.answers[0].success is False


@respx.mock
def test_format_round_table_matches_spec_shape(eight_agents):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": "Congestion control avoids overload."})
    )

    result = asyncio.run(run_round(eight_agents, "Explain TCP congestion control."))
    table = format_round_table(result)

    assert table.startswith("Round 1")
    assert "Scientist" in table
    assert "Devil's Advocate" in table
    assert "→" in table
    # 8 arrow lines + header + blank line
    assert table.count("→") == 8