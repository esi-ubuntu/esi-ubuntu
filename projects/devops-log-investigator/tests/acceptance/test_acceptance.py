from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.catalog import Catalog, CatalogEntry
from app.main import create_app
from app.models import LLMResponse, LLMToolCall
from app.orchestrator import Investigator
from app.policy import Policy
from app.settings import Settings


class ScriptedLLM:
    model = "qwen3:8b-q4_K_M"

    def __init__(self, responses):
        self.responses = list(responses)
        self.transcript = []

    async def chat(self, messages, tools=None):
        self.transcript.append(list(messages))
        if not self.responses:
            raise AssertionError("LLM scenario exhausted")
        return self.responses.pop(0)


class ScriptedMCP:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    async def call(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        if not self.steps:
            raise AssertionError("MCP scenario exhausted")
        expected_tool, result = self.steps.pop(0)
        assert tool == expected_tool
        return result


def tool(name: str, **arguments) -> LLMResponse:
    return LLMResponse(content="", tool_calls=[LLMToolCall(name=name, arguments=arguments)])


def final(answer: str, *, confidence: float = 0.98) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(
            {
                "status": "OK",
                "answer_fa": answer,
                "confidence": confidence,
                "resolved_time_window": {
                    "start": "2026-09-27T08:00:00+03:30",
                    "end": "2026-09-27T12:00:00+03:30",
                },
            },
            ensure_ascii=False,
        )
    )


def policy() -> Policy:
    return Policy(
        allowed_indices=("logs-*", "payments-*", "transactions-*"),
        denied_indices=(".security-*", ".internal-*"),
        denied_fields=("card.number", "auth.token"),
        max_time_range_hours=24,
        max_rows=500,
        max_sample_rows=25,
        max_calls=20,
        max_repairs=3,
    )


def catalog() -> Catalog:
    return Catalog(
        health="ok",
        entries=[
            CatalogEntry(
                kind="dashboard",
                source_id="http-errors",
                title="HTTP Errors",
                index_patterns=["logs-*"],
                fields=["http.response.status_code", "service.name", "message"],
            ),
            CatalogEntry(
                kind="search",
                source_id="duplicate-debit",
                title="Duplicate Debit",
                index_patterns=["payments-*"],
                fields=[
                    "customer.national_id",
                    "account.number",
                    "transaction.id",
                    "amount",
                    "operation",
                ],
                query="operation:DB",
            ),
        ],
    )


async def ask(question: str, responses, mcp_steps):
    llm = ScriptedLLM(responses)
    mcp = ScriptedMCP(mcp_steps)
    investigator = Investigator(
        policy=policy(),
        catalog=catalog(),
        llm=llm,
        mcp=mcp,
        sensitive_fields={"customer.national_id", "account.number"},
    )
    app = create_app(investigator=investigator, settings=Settings(logical_model="log-investigator"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "log-investigator", "messages": [{"role": "user", "content": question}]},
        )
    return response, llm, mcp


@pytest.mark.asyncio
async def test_acceptance_http_500_question_requires_no_index_or_field_from_operator():
    question = "از صبح چند خطای 500 داشتیم؟"
    response, _, mcp = await ask(
        question,
        [
            tool("list_indices"),
            tool("get_mappings", index="logs-*"),
            tool("esql", query="FROM logs-* | WHERE http.response.status_code == 500 | STATS count = COUNT(*)"),
            tool("esql", query="FROM logs-* | WHERE http.response.status_code == 500 | STATS check = COUNT(*)"),
            final("از صبح ۱۲ خطای ۵۰۰ ثبت شده است."),
        ],
        [
            ("list_indices", {"indices": ["logs-prod-2026.09", "payments-prod-2026.09"]}),
            ("get_mappings", {"fields": ["http.response.status_code", "service.name"]}),
            ("esql", {"count": 12}),
            ("esql", {"check": 12}),
        ],
    )
    assert "logs-" not in question and "http.response" not in question
    assert response.status_code == 200
    assert "۱۲" in response.json()["choices"][0]["message"]["content"]
    assert response.json()["investigator"]["verification"] == "cross_checked"
    assert [name for name, _ in mcp.calls[:2]] == ["list_indices", "get_mappings"]


@pytest.mark.asyncio
async def test_acceptance_timeout_ranking_question_discovers_service_field_autonomously():
    question = "کدام سرویس بیشترین timeout را داشته؟"
    response, _, mcp = await ask(
        question,
        [
            tool("list_indices"),
            tool("get_mappings", index="logs-*"),
            tool("esql", query='FROM logs-* | WHERE message LIKE "*timeout*" | STATS c = COUNT(*) BY service.name | SORT c DESC | LIMIT 5'),
            tool("esql", query='FROM logs-* | WHERE event.outcome == "timeout" | STATS c = COUNT(*) BY service.name | SORT c DESC | LIMIT 5'),
            final("سرویس payment-api با ۳۱ timeout بیشترین مقدار را داشته است."),
        ],
        [
            ("list_indices", {"indices": ["logs-prod-2026.09"]}),
            ("get_mappings", {"fields": ["message", "event.outcome", "service.name"]}),
            ("esql", {"rows": [["payment-api", 31], ["auth-api", 7]]}),
            ("esql", {"rows": [["payment-api", 31], ["auth-api", 7]]}),
        ],
    )
    assert "service.name" not in question and "logs-" not in question
    assert response.status_code == 200
    assert "payment-api" in response.json()["choices"][0]["message"]["content"]
    assert response.json()["investigator"]["verification"] == "cross_checked"
    assert mcp.calls[0][0] == "list_indices"


@pytest.mark.asyncio
async def test_acceptance_duplicate_debit_question_discovers_semantics_and_redacts_probe_pii():
    question = "از صبح چند کد ملی داشتیم که بابت یک تراکنش دوبار از حسابشان برداشت شده؟"
    response, llm, mcp = await ask(
        question,
        [
            tool("list_indices"),
            tool("get_mappings", index="payments-*"),
            tool(
                "search",
                index="payments-*",
                rows=5,
                time_range_hours=4,
                fields=["customer.national_id", "account.number", "transaction.id", "amount", "operation"],
            ),
            tool(
                "esql",
                query='FROM payments-* | WHERE operation == "DB" | STATS c = COUNT(*) BY customer.national_id, account.number, transaction.id, amount | WHERE c > 1 | STATS people = COUNT_DISTINCT(customer.national_id)',
            ),
            tool(
                "esql",
                query='FROM payments-* | WHERE operation == "DB" | STATS c = COUNT(*) BY transaction.id, account.number, amount | WHERE c > 1 | STATS duplicates = COUNT(*)',
            ),
            final("۳ کد ملی دارای برداشت تکراری برای یک تراکنش شناسایی شد."),
        ],
        [
            ("list_indices", {"indices": ["payments-prod-2026.09"]}),
            ("get_mappings", {"fields": ["customer.national_id", "account.number", "transaction.id", "amount", "operation"]}),
            (
                "search",
                {
                    "hits": [
                        {
                            "customer.national_id": "0012345678",
                            "account.number": "123456789",
                            "transaction.id": "tx-1",
                            "amount": 1000,
                            "operation": "DB",
                        }
                    ]
                },
            ),
            ("esql", {"people": 3}),
            ("esql", {"duplicates": 3}),
        ],
    )
    assert "payments-" not in question and "transaction.id" not in question
    assert response.status_code == 200
    body = response.json()
    assert "۳" in body["choices"][0]["message"]["content"]
    assert body["investigator"]["verification"] == "cross_checked"
    assert [name for name, _ in mcp.calls[:3]] == ["list_indices", "get_mappings", "search"]
    tool_context = "\n".join(
        message.content
        for call in llm.transcript
        for message in call
        if getattr(message, "role", "") == "tool"
    )
    assert "0012345678" not in tool_context
    assert "123456789" not in tool_context
    assert "[REDACTED]" in tool_context
