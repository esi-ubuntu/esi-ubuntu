from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.mcp_client import ElasticMCPClient
from app.models import ToolCall
from app.policy import Policy, PolicyViolation


def make_policy() -> Policy:
    return Policy(
        allowed_indices=("logs-*", "payments-*"),
        denied_indices=(".security-*", ".internal-*"),
        denied_fields=("card.number", "auth.token"),
        max_time_range_hours=24,
        max_rows=500,
        max_sample_rows=25,
        max_calls=20,
        max_repairs=3,
    )


def test_list_indices_pattern_is_injected_from_allowlist_not_model_input():
    policy = make_policy()

    validated = policy.validate_tool_call(
        ToolCall(tool="list_indices", arguments={"index_pattern": "*"})
    )

    assert validated.arguments["index_pattern"] == "logs-*,payments-*"


def test_esql_rejects_lookup_join_even_when_from_source_is_allowed():
    policy = make_policy()

    with pytest.raises(PolicyViolation, match="multi-source"):
        policy.validate_tool_call(
            ToolCall(
                tool="esql",
                arguments={"query": "FROM logs-* | LOOKUP JOIN secret_lookup ON service.name"},
            )
        )


def test_esql_rejects_enrich_command():
    policy = make_policy()

    with pytest.raises(PolicyViolation, match="multi-source"):
        policy.validate_tool_call(
            ToolCall(
                tool="esql",
                arguments={"query": "FROM logs-* | ENRICH customer-policy ON customer.id"},
            )
        )


@pytest.mark.asyncio
async def test_search_is_translated_to_real_elastic_mcp_schema_and_capped():
    captured = {}

    async def call_impl(tool, arguments):
        captured["tool"] = tool
        captured["arguments"] = arguments
        return []

    client = ElasticMCPClient(
        "http://elastic-mcp:8080/mcp",
        call_impl=call_impl,
        max_sample_rows=25,
        max_time_range_hours=24,
    )

    await client.call(
        "search",
        {
            "index": "payments-*",
            "rows": 100,
            "time_range_hours": 4,
            "timestamp_field": "event.created",
            "fields": ["operation", "transaction.id"],
        },
    )

    assert captured["tool"] == "search"
    assert captured["arguments"] == {
        "index": "payments-*",
        "fields": ["operation", "transaction.id"],
        "query_body": {
            "size": 25,
            "query": {
                "range": {
                    "event.created": {
                        "gte": "now-4h",
                        "lte": "now",
                    }
                }
            },
        },
    }


@pytest.mark.asyncio
async def test_list_indices_uses_real_schema_and_filters_unapproved_results():
    captured = {}

    async def call_impl(tool, arguments):
        captured["tool"] = tool
        captured["arguments"] = arguments
        return [
            {"index": "logs-prod-2026.09", "status": "open", "docs.count": 10},
            {"index": ".security-7", "status": "open", "docs.count": 1},
            {"index": "payments-prod-2026.09", "status": "open", "docs.count": 20},
        ]

    client = ElasticMCPClient(
        "http://elastic-mcp:8080/mcp",
        call_impl=call_impl,
        allowed_index_patterns=("logs-*", "payments-*"),
    )

    result = await client.call(
        "list_indices",
        {"index_pattern": "logs-*,payments-*"},
    )

    assert captured["arguments"] == {"index_pattern": "logs-*,payments-*"}
    names = [item["index"] for item in result["items"]]
    assert names == ["logs-prod-2026.09", "payments-prod-2026.09"]


@dataclass
class TextContent:
    text: str


@dataclass
class FakeMCPResult:
    content: list[TextContent]


@pytest.mark.asyncio
async def test_real_mcp_text_plus_json_content_is_normalized_to_items():
    async def call_impl(tool, arguments):
        return FakeMCPResult(
            content=[
                TextContent("Found 2 indices:"),
                TextContent('[{"index":"logs-a"},{"index":"logs-b"}]'),
            ]
        )

    client = ElasticMCPClient(
        "http://elastic-mcp:8080/mcp",
        call_impl=call_impl,
        allowed_index_patterns=("logs-*",),
    )

    result = await client.call("list_indices", {"index_pattern": "logs-*"})

    assert result == {"items": [{"index": "logs-a"}, {"index": "logs-b"}]}
