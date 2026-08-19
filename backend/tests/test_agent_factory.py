import respx
from httpx import Response

from app.agent_factory import build_agents
from app.ollama_manager import OllamaManager

HOST = "http://ollama.test"


@respx.mock
async def test_build_agents_resolves_all_four_families():
    respx.get(f"{HOST}/api/tags").mock(
        return_value=Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:7b"},
                    {"name": "llama3:8b"},
                    {"name": "mistral:7b"},
                    {"name": "gemma2:9b"},
                ]
            },
        )
    )

    manager = OllamaManager(host=HOST, timeout=5)
    agents = await build_agents(manager)

    assert len(agents) == 8
    by_id = {a.agent_id: a.model for a in agents}
    assert by_id["scientist"] == "qwen2.5:7b"
    assert by_id["engineer"] == "llama3:8b"
    assert by_id["creative"] == "mistral:7b"
    assert by_id["minimalist"] == "gemma2:9b"


@respx.mock
async def test_build_agents_falls_back_when_family_missing():
    # Only a llama model is installed — every agent should still get a
    # usable model rather than crash.
    respx.get(f"{HOST}/api/tags").mock(
        return_value=Response(200, json={"models": [{"name": "llama3:8b"}]})
    )

    manager = OllamaManager(host=HOST, timeout=5)
    agents = await build_agents(manager)

    assert len(agents) == 8
    models = {a.model for a in agents}
    assert models == {"llama3:8b"}


@respx.mock
async def test_build_agents_with_no_models_installed_uses_placeholder():
    respx.get(f"{HOST}/api/tags").mock(return_value=Response(200, json={"models": []}))

    manager = OllamaManager(host=HOST, timeout=5)
    agents = await build_agents(manager)

    assert len(agents) == 8
    for agent in agents:
        assert agent.model.endswith(":unavailable")