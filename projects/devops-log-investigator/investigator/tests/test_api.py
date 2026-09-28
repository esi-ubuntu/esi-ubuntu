from __future__ import annotations

import importlib

import pytest
from httpx import ASGITransport, AsyncClient


class FakeInvestigator:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.questions: list[str] = []

    async def investigate(self, question: str, now=None):
        self.questions.append(question)
        if self.error:
            raise self.error
        return self.result


def make_result():
    from app.orchestrator import InvestigationResult

    return InvestigationResult(
        answer_fa="از صبح ۱۲ خطای ۵۰۰ ثبت شده است.",
        status="OK",
        confidence=0.98,
        resolved_time_window={"start": "2026-09-27T08:00:00+03:30", "end": "2026-09-27T12:00:00+03:30"},
        indices=["logs-*"],
        fields=["http.response.status_code"],
        queries=["FROM logs-* | WHERE http.response.status_code == 500 | STATS count = COUNT(*)"],
        verification="cross_checked",
        request_id="req-123",
    )


def load_api():
    try:
        return importlib.import_module("app.main")
    except ModuleNotFoundError as exc:
        pytest.fail(f"api implementation missing: {exc}")


@pytest.mark.asyncio
async def test_health_endpoint():
    api = load_api()
    app = api.create_app(investigator=FakeInvestigator(make_result()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_models_exposes_only_log_investigator():
    api = load_api()
    app = api.create_app(investigator=FakeInvestigator(make_result()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["data"]] == ["log-investigator"]


@pytest.mark.asyncio
async def test_chat_completion_returns_persian_answer_and_audit_metadata():
    api = load_api()
    fake = FakeInvestigator(make_result())
    app = api.create_app(investigator=fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "log-investigator",
                "messages": [
                    {"role": "system", "content": "ignored by investigator"},
                    {"role": "user", "content": "از صبح چند خطای 500 داشتیم؟"},
                ],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert fake.questions == ["از صبح چند خطای 500 داشتیم؟"]
    assert body["choices"][0]["message"]["content"] == "از صبح ۱۲ خطای ۵۰۰ ثبت شده است."
    assert body["investigator"]["verification"] == "cross_checked"
    assert body["investigator"]["request_id"] == "req-123"


@pytest.mark.asyncio
async def test_chat_rejects_empty_messages():
    api = load_api()
    app = api.create_app(investigator=FakeInvestigator(make_result()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json={"model": "log-investigator", "messages": []})
    assert response.status_code == 400
    assert "user message" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_chat_rejects_unsupported_model():
    api = load_api()
    app = api.create_app(investigator=FakeInvestigator(make_result()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "something-else", "messages": [{"role": "user", "content": "test"}]},
        )
    assert response.status_code == 400
    assert "model" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_chat_returns_503_when_investigator_dependency_fails():
    api = load_api()
    app = api.create_app(investigator=FakeInvestigator(error=RuntimeError("ollama unavailable")))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "log-investigator", "messages": [{"role": "user", "content": "test"}]},
        )
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()
