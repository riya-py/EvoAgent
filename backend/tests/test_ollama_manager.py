import json

import httpx
import pytest
import respx
from httpx import Response

from app.ollama_manager import OllamaManager

HOST = "http://ollama.test"


@pytest.fixture
def manager():
    return OllamaManager(host=HOST, timeout=5)


@respx.mock
async def test_list_models_categorizes_families(manager):
    respx.get(f"{HOST}/api/tags").mock(
        return_value=Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:7b", "size": 123, "details": {"parameter_size": "7B", "quantization_level": "Q4_0"}},
                    {"name": "llama3:8b", "size": 456, "details": {}},
                    {"name": "some-custom-model", "size": 789, "details": {}},
                ]
            },
        )
    )

    models = await manager.list_models()

    assert len(models) == 3
    by_name = {m.name: m for m in models}
    assert by_name["qwen2.5:7b"].family == "qwen"
    assert by_name["qwen2.5:7b"].parameter_size == "7B"
    assert by_name["llama3:8b"].family == "llama"
    assert by_name["some-custom-model"].family == "other"


@respx.mock
async def test_model_exists_matches_tag_prefix(manager):
    respx.get(f"{HOST}/api/tags").mock(
        return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    )

    assert await manager.model_exists("qwen2.5:7b") is True
    assert await manager.model_exists("qwen2.5") is True  # prefix match
    assert await manager.model_exists("mistral") is False


@respx.mock
async def test_generate_success_tracks_timing_and_tokens(manager):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(
            200,
            json={
                "response": "Hello!",
                "prompt_eval_count": 12,
                "eval_count": 4,
            },
        )
    )

    result = await manager.generate(model="qwen2.5:7b", prompt="Say hello")

    assert result.success is True
    assert result.response == "Hello!"
    assert result.model == "qwen2.5:7b"
    assert result.response_time_ms >= 0
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 4
    assert result.total_tokens == 16


@respx.mock
async def test_generate_failure_returns_result_not_exception(manager):
    respx.post(f"{HOST}/api/generate").mock(side_effect=httpx.ConnectError("boom"))

    result = await manager.generate(model="qwen2.5:7b", prompt="Say hello")

    assert result.success is False
    assert result.error is not None
    assert result.response == ""


@respx.mock
async def test_stream_yields_incremental_chunks(manager):
    lines = [
        json.dumps({"response": "Hel", "done": False}),
        json.dumps({"response": "lo!", "done": False}),
        json.dumps({"response": "", "done": True}),
    ]
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, text="\n".join(lines))
    )

    chunks = [c async for c in manager.stream(model="qwen2.5:7b", prompt="Say hello")]

    assert chunks == ["Hel", "lo!"]


@respx.mock
async def test_health_check_reports_reachable(manager):
    respx.get(f"{HOST}/api/tags").mock(
        return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    )

    status = await manager.health_check()

    assert status.ollama_reachable is True
    assert status.models_installed == 1


@respx.mock
async def test_health_check_reports_unreachable(manager):
    respx.get(f"{HOST}/api/tags").mock(side_effect=httpx.ConnectError("connection refused"))

    status = await manager.health_check()

    assert status.ollama_reachable is False
    assert status.detail is not None