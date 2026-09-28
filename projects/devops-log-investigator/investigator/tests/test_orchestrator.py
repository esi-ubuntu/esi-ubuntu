from __future__ import annotations

import importlib

import httpx
import pytest


def load_adapter_api():
    try:
        llm = importlib.import_module("app.llm")
        mcp_client = importlib.import_module("app.mcp_client")
        models = importlib.import_module("app.models")
    except ModuleNotFoundError as exc:
        pytest.fail(f"adapter implementation missing: {exc}")
    return llm, mcp_client, models


@pytest.mark.asyncio
async def test_ollama_chat_parses_tool_calls():
    llm, _, models = load_adapter_api()

    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "search", "arguments": {"index": "logs-*", "rows": 10}}}
                    ],
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama:11434") as http:
        client = llm.OllamaClient("http://ollama:11434", model="qwen3:8b-q4_K_M", http_client=http)
        response = await client.chat(
            [models.Message(role="user", content="چند خطا داشتیم؟")],
            [models.ToolSpec(name="search", description="Search logs", input_schema={"type": "object"})],
        )

    assert response.content == ""
    assert response.tool_calls[0].name == "search"
    assert response.tool_calls[0].arguments == {"index": "logs-*", "rows": 10}


@pytest.mark.asyncio
async def test_ollama_chat_raises_typed_error_when_runtime_unavailable():
    llm, _, models = load_adapter_api()

    def handler(request):
        raise httpx.ConnectError("ollama offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama:11434") as http:
        client = llm.OllamaClient("http://ollama:11434", model="qwen3:8b-q4_K_M", http_client=http)
        with pytest.raises(llm.LLMUnavailable, match="offline"):
            await client.chat([models.Message(role="user", content="test")])


@pytest.mark.asyncio
async def test_mcp_call_converts_timeout_to_typed_error():
    _, mcp_client, _ = load_adapter_api()

    async def timeout_call(tool, arguments):
        raise TimeoutError("mcp timeout")

    client = mcp_client.ElasticMCPClient("http://elastic-mcp:8080/mcp", call_impl=timeout_call)

    with pytest.raises(mcp_client.MCPUnavailable, match="timeout"):
        await client.call("search", {"index": "logs-*"})


@pytest.mark.asyncio
async def test_mcp_call_rejects_malformed_result():
    _, mcp_client, _ = load_adapter_api()

    async def malformed_call(tool, arguments):
        return "not-a-dict"

    client = mcp_client.ElasticMCPClient("http://elastic-mcp:8080/mcp", call_impl=malformed_call)

    with pytest.raises(mcp_client.MCPProtocolError, match="result"):
        await client.call("search", {"index": "logs-*"})


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        if not self.responses:
            raise AssertionError("LLM script exhausted")
        return self.responses.pop(0)


class ScriptedMCP:
    def __init__(self, expected):
        self.expected = list(expected)
        self.calls = []

    async def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        if not self.expected:
            raise AssertionError("MCP script exhausted")
        expected_tool, result = self.expected.pop(0)
        assert tool == expected_tool
        return result


def make_policy():
    from app.policy import Policy

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


def make_catalog():
    from app.catalog import Catalog, CatalogEntry

    return Catalog(
        health="ok",
        entries=[
            CatalogEntry(
                kind="search",
                source_id="dup",
                title="Duplicate Debit",
                index_patterns=["payments-*"],
                fields=["customer.national_id", "account.number", "transaction.id", "amount", "operation"],
                query="operation:DB",
            )
        ],
    )


def final_response(models, *, answer, status="OK", confidence=0.98):
    import json

    return models.LLMResponse(
        content=json.dumps(
            {
                "status": status,
                "answer_fa": answer,
                "confidence": confidence,
                "resolved_time_window": {"start": "2026-09-27T08:00:00+03:30", "end": "2026-09-27T12:00:00+03:30"},
            },
            ensure_ascii=False,
        )
    )


@pytest.mark.asyncio
async def test_investigator_counts_http_500_and_cross_checks():
    orchestrator = importlib.import_module("app.orchestrator")
    models = importlib.import_module("app.models")
    llm = ScriptedLLM(
        [
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM logs-* | WHERE http.response.status_code == 500 | STATS count = COUNT(*)"})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM logs-* | WHERE http.response.status_code == 500 | STATS count2 = COUNT(*)"})], content=""),
            final_response(models, answer="از صبح ۱۲ خطای ۵۰۰ ثبت شده است."),
        ]
    )
    mcp = ScriptedMCP([("esql", {"count": 12}), ("esql", {"count2": 12})])
    agent = orchestrator.Investigator(policy=make_policy(), catalog=make_catalog(), llm=llm, mcp=mcp)

    result = await agent.investigate("از صبح چند خطای 500 داشتیم؟", now=__import__("datetime").datetime(2026, 9, 27, 12, 0, tzinfo=__import__("datetime").timezone.utc))

    assert result.status == "OK"
    assert "۱۲" in result.answer_fa
    assert result.verification == "cross_checked"
    assert len(result.queries) == 2


@pytest.mark.asyncio
async def test_investigator_returns_top_timeout_service():
    orchestrator = importlib.import_module("app.orchestrator")
    models = importlib.import_module("app.models")
    llm = ScriptedLLM(
        [
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM logs-* | WHERE message LIKE \"*timeout*\" | STATS c = COUNT(*) BY service.name | SORT c DESC | LIMIT 5"})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM logs-* | WHERE event.outcome == \"timeout\" | STATS c = COUNT(*) BY service.name | SORT c DESC | LIMIT 5"})], content=""),
            final_response(models, answer="سرویس payment-api با ۳۱ timeout بیشترین مقدار را داشته است."),
        ]
    )
    mcp = ScriptedMCP([
        ("esql", {"rows": [["payment-api", 31], ["auth-api", 7]]}),
        ("esql", {"rows": [["payment-api", 31], ["auth-api", 7]]}),
    ])
    agent = orchestrator.Investigator(policy=make_policy(), catalog=make_catalog(), llm=llm, mcp=mcp)

    result = await agent.investigate("کدام سرویس بیشترین timeout را داشته؟")

    assert result.status == "OK"
    assert "payment-api" in result.answer_fa
    assert result.verification == "cross_checked"


@pytest.mark.asyncio
async def test_duplicate_debit_probe_redacts_pii_before_llm_and_returns_count():
    orchestrator = importlib.import_module("app.orchestrator")
    models = importlib.import_module("app.models")
    llm = ScriptedLLM(
        [
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="get_mappings", arguments={"index": "payments-*"})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="search", arguments={"index": "payments-*", "rows": 5, "time_range_hours": 4, "fields": ["customer.national_id", "account.number", "transaction.id", "amount", "operation"]})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM payments-* | WHERE operation == \"DB\" | STATS c = COUNT(*) BY customer.national_id, account.number, transaction.id, amount | WHERE c > 1 | STATS people = COUNT_DISTINCT(customer.national_id)"})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM payments-* | WHERE operation == \"DB\" | STATS c = COUNT(*) BY transaction.id, account.number, amount | WHERE c > 1 | STATS duplicates = COUNT(*)"})], content=""),
            final_response(models, answer="۳ کد ملی دارای برداشت تکراری برای یک تراکنش شناسایی شد."),
        ]
    )
    mcp = ScriptedMCP([
        ("get_mappings", {"fields": ["customer.national_id", "account.number", "transaction.id", "amount", "operation"]}),
        ("search", {"hits": [{"customer.national_id": "0012345678", "account.number": "123456789", "transaction.id": "tx-1", "amount": 1000, "operation": "DB"}]}),
        ("esql", {"people": 3}),
        ("esql", {"duplicates": 3}),
    ])
    agent = orchestrator.Investigator(
        policy=make_policy(),
        catalog=make_catalog(),
        llm=llm,
        mcp=mcp,
        sensitive_fields={"customer.national_id", "account.number"},
    )

    result = await agent.investigate("از صبح چند کد ملی بابت یک تراکنش دوبار برداشت شدند؟")

    assert result.status == "OK"
    assert "۳" in result.answer_fa
    tool_context = "\n".join(message.content for call in llm.calls for message in call if getattr(message, "role", "") == "tool")
    assert "0012345678" not in tool_context
    assert "123456789" not in tool_context
    assert "[REDACTED]" in tool_context


@pytest.mark.asyncio
async def test_suspicious_zero_is_not_accepted_until_repaired_and_cross_checked():
    orchestrator = importlib.import_module("app.orchestrator")
    models = importlib.import_module("app.models")
    llm = ScriptedLLM(
        [
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM payments-* | WHERE operation == \"DEBIT\" | STATS count = COUNT(*)"})], content=""),
            final_response(models, answer="هیچ موردی نبود.", confidence=0.95),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="search", arguments={"index": "payments-*", "rows": 5, "time_range_hours": 4, "fields": ["operation"]})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM payments-* | WHERE operation == \"DB\" | STATS count = COUNT(*)"})], content=""),
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="esql", arguments={"query": "FROM payments-* | WHERE operation == \"DB\" | STATS check = COUNT(*)"})], content=""),
            final_response(models, answer="۳ مورد پیدا شد.", confidence=0.99),
        ]
    )
    mcp = ScriptedMCP([
        ("esql", {"count": 0}),
        ("search", {"hits": [{"operation": "DB"}]}),
        ("esql", {"count": 3}),
        ("esql", {"check": 3}),
    ])
    agent = orchestrator.Investigator(policy=make_policy(), catalog=make_catalog(), llm=llm, mcp=mcp)

    result = await agent.investigate("برداشت تکراری چند مورد بود؟")

    assert result.status == "OK"
    assert "۳" in result.answer_fa
    assert len(mcp.calls) == 4
    assert result.verification == "cross_checked"


@pytest.mark.asyncio
async def test_ambiguous_semantics_returns_data_not_verified_instead_of_fabricating():
    orchestrator = importlib.import_module("app.orchestrator")
    models = importlib.import_module("app.models")
    llm = ScriptedLLM(
        [
            models.LLMResponse(tool_calls=[models.LLMToolCall(name="get_mappings", arguments={"index": "transactions-*"})], content=""),
            final_response(models, answer="معنای برداشت موفق از داده موجود قابل اثبات نیست.", status="DATA_NOT_VERIFIED", confidence=0.2),
        ]
    )
    mcp = ScriptedMCP([("get_mappings", {"fields": ["opaque_a", "opaque_b"]})])
    agent = orchestrator.Investigator(policy=make_policy(), catalog=make_catalog(), llm=llm, mcp=mcp)

    result = await agent.investigate("چند برداشت موفق بدون برگشت داشتیم؟")

    assert result.status == "DATA_NOT_VERIFIED"
    assert result.verification == "not_verified"
