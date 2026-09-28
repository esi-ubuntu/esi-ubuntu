from __future__ import annotations

from typing import Any


REDACTED = "[REDACTED]"


def redact_payload(payload: object, sensitive_fields: set[str]) -> object:
    return _redact(payload, sensitive_fields, "")


def _redact(value: Any, sensitive_fields: set[str], path: str) -> Any:
    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if child_path in sensitive_fields or key_text in sensitive_fields:
                result[key] = REDACTED
            else:
                result[key] = _redact(child, sensitive_fields, child_path)
        return result
    if isinstance(value, list):
        return [_redact(item, sensitive_fields, path) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, sensitive_fields, path) for item in value)
    return value
