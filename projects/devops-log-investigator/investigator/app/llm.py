from __future__ import annotations

import json

import httpx

from .models import LLMResponse, LLMToolCall, Message, ToolSpec


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLMProtocolError(LLMError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, *, model: str, http_client: httpx.AsyncClient | None = None, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http = http_client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def chat(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema}}
                for tool in tools
            ]
        try:
            response = await self.http.post("/api/chat", json=payload)
        except httpx.RequestError as exc:
            raise LLMUnavailable(str(exc)) from exc
        if response.status_code >= 400:
            raise LLMError(f"Ollama HTTP {response.status_code}: {response.text[:200]}")
        try:
            body = response.json()
            message = body["message"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMProtocolError(f"invalid Ollama response: {exc}") from exc

        parsed_calls: list[LLMToolCall] = []
        for item in message.get("tool_calls", []) or []:
            function = item.get("function", {}) if isinstance(item, dict) else {}
            name = function.get("name")
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError as exc:
                    raise LLMProtocolError("invalid tool arguments") from exc
            if name and isinstance(arguments, dict):
                parsed_calls.append(LLMToolCall(name=str(name), arguments=arguments))
        return LLMResponse(content=str(message.get("content") or ""), tool_calls=parsed_calls)
