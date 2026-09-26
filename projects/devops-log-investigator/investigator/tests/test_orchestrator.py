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
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"index": "logs-*", "rows": 10}}}]}})

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
