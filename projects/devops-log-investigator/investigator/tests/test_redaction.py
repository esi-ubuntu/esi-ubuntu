from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone

import pytest


def load_api():
    try:
        audit = importlib.import_module("app.audit")
        redaction = importlib.import_module("app.redaction")
    except ModuleNotFoundError as exc:
        pytest.fail(f"redaction/audit implementation missing: {exc}")
    return audit, redaction


def test_redacts_flattened_sensitive_fields_but_keeps_counts():
    _, redaction = load_api()
    payload = {
        "customer.national_id": "0012345678",
        "account.number": "1234567890123456",
        "duplicate_count": 7,
        "service.name": "payment-api",
    }

    redacted = redaction.redact_payload(payload, {"customer.national_id", "account.number"})

    assert redacted["customer.national_id"] == redaction.REDACTED
    assert redacted["account.number"] == redaction.REDACTED
    assert redacted["duplicate_count"] == 7
    assert redacted["service.name"] == "payment-api"


def test_redacts_nested_sensitive_paths_without_removing_field_names():
    _, redaction = load_api()
    payload = {
        "customer": {"national_id": "0012345678", "segment": "vip"},
        "account": {"number": "1234567890", "bank": "example"},
    }

    redacted = redaction.redact_payload(payload, {"customer.national_id", "account.number"})

    assert set(redacted["customer"].keys()) == {"national_id", "segment"}
    assert redacted["customer"]["national_id"] == redaction.REDACTED
    assert redacted["account"]["number"] == redaction.REDACTED
    assert redacted["customer"]["segment"] == "vip"


def test_redacts_sensitive_fields_inside_lists():
    _, redaction = load_api()
    payload = [{"card.number": "6037990000000000", "count": 2}]

    redacted = redaction.redact_payload(payload, {"card.number"})

    assert redacted == [{"card.number": redaction.REDACTED, "count": 2}]


def test_audit_writer_appends_machine_readable_json_lines(tmp_path):
    audit, _ = load_api()
    writer = audit.AuditWriter(tmp_path)
    timestamp = datetime(2026, 9, 27, 0, 30, tzinfo=timezone.utc)

    first = audit.AuditRecord(
        request_id="req-1",
        timestamp=timestamp,
        question="چند خطای 500 داشتیم؟",
        status="OK",
        model_id="qwen3:8b-q4_K_M",
    )
    second = audit.AuditRecord(
        request_id="req-2",
        timestamp=timestamp,
        question="بیشترین timeout؟",
        status="DATA_NOT_VERIFIED",
        model_id="qwen3:8b-q4_K_M",
    )

    path1 = writer.write(first)
    path2 = writer.write(second)

    assert path1 == path2
    lines = path1.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    decoded = [json.loads(line) for line in lines]
    assert decoded[0]["request_id"] == "req-1"
    assert decoded[0]["timestamp"] == "2026-09-27T00:30:00+00:00"
    assert decoded[1]["status"] == "DATA_NOT_VERIFIED"
