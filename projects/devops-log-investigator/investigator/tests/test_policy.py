from __future__ import annotations

import importlib
from pathlib import Path

import pytest


POLICY_YAML = """
allowed_indices:
  - logs-*
  - payments-*
  - transactions-*
denied_indices:
  - .security-*
  - .internal-*
denied_fields:
  - card.number
  - auth.token
max_time_range_hours: 24
max_rows: 500
max_sample_rows: 25
max_calls: 20
max_repairs: 3
"""


def load_api():
    try:
        models = importlib.import_module("app.models")
        policy = importlib.import_module("app.policy")
    except ModuleNotFoundError as exc:
        pytest.fail(f"policy implementation missing: {exc}")
    return models, policy


def write_policy(tmp_path: Path) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_YAML, encoding="utf-8")
    return path


def build_call(models, *, tool="search", index="logs-prod-2026.09", rows=100, hours=1, fields=None):
    return models.ToolCall(
        tool=tool,
        arguments={
            "index": index,
            "rows": rows,
            "time_range_hours": hours,
            "fields": fields or ["service.name", "http.response.status_code"],
        },
    )


def test_allows_read_only_search_on_approved_index(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    validated = policy.validate_tool_call(build_call(models))
    assert validated.tool == "search"
    assert validated.arguments["index"] == "logs-prod-2026.09"


def test_rejects_wildcard_escape_outside_allowlist(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="index"):
        policy.validate_tool_call(build_call(models, index="*"))


def test_rejects_explicit_denied_index(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="index"):
        policy.validate_tool_call(build_call(models, index=".security-7"))


def test_rejects_excessive_row_count(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="rows"):
        policy.validate_tool_call(build_call(models, rows=501))


def test_rejects_excessive_time_range(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="time"):
        policy.validate_tool_call(build_call(models, hours=25))


def test_rejects_unsupported_tool_before_network_execution(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="tool"):
        policy.validate_tool_call(build_call(models, tool="delete_index"))


def test_rejects_denied_field_request(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    with pytest.raises(policy_module.PolicyViolation, match="field"):
        policy.validate_tool_call(build_call(models, fields=["service.name", "card.number"]))


def test_rejects_esql_source_outside_allowlist_even_without_index_argument(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    call = models.ToolCall(tool="esql", arguments={"query": "FROM .security-* | STATS count = COUNT(*)"})
    with pytest.raises(policy_module.PolicyViolation, match="index"):
        policy.validate_tool_call(call)


def test_allows_esql_when_all_from_sources_are_allowlisted(tmp_path):
    models, policy_module = load_api()
    policy = policy_module.Policy.load(str(write_policy(tmp_path)))
    call = models.ToolCall(tool="esql", arguments={"query": "FROM logs-* | WHERE http.response.status_code == 500 | STATS count = COUNT(*)"})
    validated = policy.validate_tool_call(call)
    assert validated.tool == "esql"
