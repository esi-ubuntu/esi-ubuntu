from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from fnmatch import fnmatchcase
from typing import Any


class MCPError(RuntimeError):
    pass


class MCPUnavailable(MCPError):
    pass


class MCPProtocolError(MCPError):
    pass


CallImpl = Callable[[str, dict[str, Any]], Awaitable[object]]


class ElasticMCPClient:
    def __init__(
        self,
        endpoint: str,
        *,
        call_impl: CallImpl | None = None,
        max_sample_rows: int = 25,
        max_time_range_hours: int = 24,
        allowed_index_patterns: tuple[str, ...] = (),
    ) -> None:
        self.endpoint = endpoint
        self._call_impl = call_impl or self._default_call
        self.max_sample_rows = max_sample_rows
        self.max_time_range_hours = max_time_range_hours
        self.allowed_index_patterns = allowed_index_patterns

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        transport_arguments = self._to_transport_arguments(tool, arguments)
        try:
            result = await self._call_impl(tool, transport_arguments)
        except (TimeoutError, OSError) as exc:
            raise MCPUnavailable(str(exc)) from exc
        normalized = self._normalize_result(result)
        if isinstance(normalized, list):
            normalized = {"items": normalized}
        if not isinstance(normalized, dict):
            raise MCPProtocolError("MCP tool result is not an object")
        if tool == "list_indices" and self.allowed_index_patterns:
            normalized = self._filter_index_discovery(normalized)
        return normalized

    def _to_transport_arguments(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "list_indices":
            pattern = arguments.get("index_pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                raise MCPProtocolError("list_indices requires index_pattern")
            return {"index_pattern": pattern}

        if tool == "get_mappings":
            return {"index": arguments["index"]}

        if tool == "search":
            index = arguments.get("index")
            if not isinstance(index, str) or not index:
                raise MCPProtocolError("search requires index")

            requested_rows = arguments.get("rows", self.max_sample_rows)
            try:
                rows = int(requested_rows)
            except (TypeError, ValueError) as exc:
                raise MCPProtocolError("invalid search row count") from exc
            rows = max(0, min(rows, self.max_sample_rows))

            query_body: dict[str, Any] = {"size": rows}
            hours = arguments.get("time_range_hours")
            if hours is not None:
                try:
                    bounded_hours = float(hours)
                except (TypeError, ValueError) as exc:
                    raise MCPProtocolError("invalid search time range") from exc
                bounded_hours = max(0.0, min(bounded_hours, float(self.max_time_range_hours)))
                timestamp_field = str(arguments.get("timestamp_field") or "@timestamp")
                value = int(bounded_hours) if bounded_hours.is_integer() else bounded_hours
                query_body["query"] = {
                    "range": {
                        timestamp_field: {
                            "gte": f"now-{value}h",
                            "lte": "now",
                        }
                    }
                }

            translated: dict[str, Any] = {"index": index, "query_body": query_body}
            fields = arguments.get("fields")
            if isinstance(fields, list):
                translated["fields"] = [str(field) for field in fields]
            return translated

        if tool == "esql":
            return {"query": arguments["query"]}

        return dict(arguments)

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

    def _filter_index_discovery(self, payload: object) -> object:
        if isinstance(payload, list):
            return [
                item
                for item in (self._filter_index_discovery(value) for value in payload)
                if item is not None
            ]
        if isinstance(payload, dict):
            index_name = payload.get("index")
            if isinstance(index_name, str) and not any(
                fnmatchcase(index_name, pattern) for pattern in self.allowed_index_patterns
            ):
                return None
            return {
                key: self._filter_index_discovery(value)
                for key, value in payload.items()
            }
        return payload

    @staticmethod
    def _normalize_result(result: object) -> object:
        if isinstance(result, (dict, list)):
            return result

        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, (dict, list)):
            return structured
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, (dict, list)):
            return structured

        content = getattr(result, "content", None)
        if isinstance(content, list):
            decoded_items: list[object] = []
            plain_text: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if not isinstance(text, str):
                    continue
                try:
                    decoded = json.loads(text)
                except ValueError:
                    plain_text.append(text)
                    continue
                if isinstance(decoded, list):
                    decoded_items.extend(decoded)
                else:
                    decoded_items.append(decoded)

            if decoded_items:
                if len(decoded_items) == 1 and isinstance(decoded_items[0], dict):
                    return decoded_items[0]
                return decoded_items
            if plain_text:
                return {"content": plain_text[0] if len(plain_text) == 1 else plain_text}
        return result
