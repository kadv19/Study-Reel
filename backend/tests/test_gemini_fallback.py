import json

import httpx
import pytest
from fastapi import HTTPException

from app.engine import gemini_client as gc


def _client_with_failing_gemini(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            raise RuntimeError("503 UNAVAILABLE")

    class Client:
        models = Models()

    client = gc.GeminiClient.__new__(gc.GeminiClient)
    client.model = "gemini-3.6-flash"
    client.cache_dir = None
    client.client = Client()
    monkeypatch.setattr(gc, "GEMINI_CHAIN_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(gc, "GEMINI_CHAIN_RETRY_DELAY_SECONDS", 0)
    return client


def test_groq_request_payload_and_parse(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({"topics": [{"header": "H", "body": "B"}]})
                    }
                }]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("FALLBACK_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("FALLBACK_API_KEY", "test-key")
    monkeypatch.setenv("FALLBACK_MODEL", "test-model")
    monkeypatch.setattr(httpx, "post", fake_post)

    client = gc.GeminiClient.__new__(gc.GeminiClient)
    client.model = "gemini-3.6-flash"
    result = client._generate_groq("syllabus", "system")

    assert result == [{"header": "H", "body": "B"}]
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert client.model == "groq:test-model"


def test_gemini_exhaustion_uses_groq(monkeypatch, caplog):
    client = _client_with_failing_gemini(monkeypatch)
    called = {"groq": False}

    def fake_groq(self, contents, system_prompt):
        called["groq"] = True
        return [{"header": "H", "body": "B"}]

    monkeypatch.setattr(gc.GeminiClient, "_generate_groq", fake_groq)
    monkeypatch.setattr(
        gc.GeminiClient,
        "_generate_ollama",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Ollama should not run")),
    )

    result = client._generate("syllabus", None, "system")

    assert result == [{"header": "H", "body": "B"}]
    assert called["groq"] is True
    assert "Falling back to Groq..." in caplog.text


def test_groq_failure_uses_remote_ollama(monkeypatch):
    client = _client_with_failing_gemini(monkeypatch)
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.com")

    def fail_groq(self, contents, system_prompt):
        raise RuntimeError("Groq down")

    monkeypatch.setattr(gc.GeminiClient, "_generate_groq", fail_groq)
    monkeypatch.setattr(
        gc.GeminiClient,
        "_generate_ollama",
        lambda self, contents, system_prompt: [{"header": "O", "body": "B"}],
    )

    assert client._generate("syllabus", None, "system") == [{"header": "O", "body": "B"}]


def test_groq_failure_skips_localhost_ollama(monkeypatch):
    client = _client_with_failing_gemini(monkeypatch)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    def fail_groq(self, contents, system_prompt):
        raise RuntimeError("Groq down")

    monkeypatch.setattr(gc.GeminiClient, "_generate_groq", fail_groq)

    with pytest.raises(HTTPException) as excinfo:
        client._generate("syllabus", None, "system")

    assert excinfo.value.status_code == 503
