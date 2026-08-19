import httpx
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app


@respx.mock
def test_health_ok_when_ollama_reachable():
    respx.get("http://ollama.test/api/tags").mock(
        return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
    )

    with TestClient(app) as client:
        resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["ollama"]["ollama_reachable"] is True
    assert body["ollama"]["models_installed"] == 1


@respx.mock
def test_health_reports_ollama_down_but_api_still_ok():
    respx.get("http://ollama.test/api/tags").mock(side_effect=httpx.ConnectError("connection refused"))

    with TestClient(app) as client:
        resp = client.get("/api/health")

    # The API itself is fine even if Ollama is offline.
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ollama"]["ollama_reachable"] is False