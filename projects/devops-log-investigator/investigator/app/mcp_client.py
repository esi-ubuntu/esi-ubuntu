from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any


class MCPError(RuntimeError):
    pass


class MCPUnavailable(MCPError):
    pass


class MCPProtocolError(MCPError):
    pass


CallImpl = Callable[[str, dict[str, Any]], Awaitable[object]]


class ElasticMCPClient:
    def __init__(self, endpoint: str, *, call_impl: CallImpl | None = None) -> None:
        self.endpoint = endpoint
        self._call_impl = call_impl or self._default_call

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self._call_impl(tool, arguments)
        except (TimeoutError, OSError) as exc:
            raise MCPUnavailable(str(exc)) from exc
        normalized = self._normalize_result(result)
        if not isinstance(normalized, dict):
            raise MCPProtocolError("MCP tool result is not an object")
        return normalized

    async def _default_call(self, tool: str, arguments: dict[str, Any]) -> object:
        try:
            from mcp import Client
        except ImportError as exc:
            raise MCPUnavailable("Python MCP SDK is not installed") from exc
        try:
            async with Client(self.endpoint) as client:
                return await client.call_tool(tool, arguments)
        except Exception as exc:
            if isinstance(exc, MCPError):
                raise
            raise MCPUnavailable(str(exc)) from exc

    @staticmethod
    def _normalize_result(result: object) -> object:
        if isinstance(result, dict):
            return result
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        content = getattr(result, "content", None)
        if isinstance(content, list):
            texts = [getattr(item, "text", None) for item in content]
            texts = [value for value in texts if isinstance(value, str)]
            if len(texts) == 1:
                try:
                    decoded = json.loads(texts[0])
                except ValueError:
                    return {"content": texts[0]}
                return decoded
            if texts:
                return {"content": texts}
        return result
