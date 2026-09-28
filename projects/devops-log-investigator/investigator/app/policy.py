from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import re
from typing import Any

import yaml

from .models import ToolCall, ValidatedToolCall


_ALLOWED_TOOLS = frozenset({"list_indices", "get_mappings", "search", "esql"})
_UNSAFE_ESQL_CLAUSES = (r"\bLOOKUP\s+JOIN\b", r"\bENRICH\b")


class PolicyViolation(ValueError):
    pass


@dataclass(frozen=True)
class Policy:
    allowed_indices: tuple[str, ...]
    denied_indices: tuple[str, ...]
    denied_fields: tuple[str, ...]
    max_time_range_hours: int
    max_rows: int
    max_sample_rows: int
    max_calls: int
    max_repairs: int

    @classmethod
    def load(cls, path: str) -> "Policy":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(
            allowed_indices=tuple(raw.get("allowed_indices", ())),
            denied_indices=tuple(raw.get("denied_indices", ())),
            denied_fields=tuple(raw.get("denied_fields", ())),
            max_time_range_hours=int(raw["max_time_range_hours"]),
            max_rows=int(raw["max_rows"]),
            max_sample_rows=int(raw["max_sample_rows"]),
            max_calls=int(raw["max_calls"]),
            max_repairs=int(raw["max_repairs"]),
        )

    def validate_tool_call(self, call: ToolCall) -> ValidatedToolCall:
        if call.tool not in _ALLOWED_TOOLS:
            raise PolicyViolation(f"tool is not allowed: {call.tool}")

        arguments = dict(call.arguments)

        if call.tool == "list_indices":
            if not self.allowed_indices:
                raise PolicyViolation("index allowlist is empty")
            # The LLM never chooses the discovery pattern. Always overwrite it with
            # the deterministic allowlist so hidden/unapproved index names cannot be enumerated.
            arguments["index_pattern"] = ",".join(self.allowed_indices)

        index = arguments.get("index")
        if index is not None:
            self._validate_index(str(index))

        index_pattern = arguments.get("index_pattern")
        if index_pattern is not None:
            for pattern in str(index_pattern).split(","):
                self._validate_index(pattern.strip())

        if call.tool == "esql":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip():
                raise PolicyViolation("esql query is required")
            for unsafe in _UNSAFE_ESQL_CLAUSES:
                if re.search(unsafe, query, flags=re.IGNORECASE):
                    raise PolicyViolation("esql multi-source command is not allowed")
            sources = self._extract_esql_sources(query)
            if not sources:
                raise PolicyViolation("esql index source is required")
            for source in sources:
                self._validate_index(source)

        rows = arguments.get("rows")
        if rows is not None and (
            not isinstance(rows, int)
            or isinstance(rows, bool)
            or rows < 0
            or rows > self.max_rows
        ):
            raise PolicyViolation(f"rows exceeds allowed limit: {rows}")

        hours = arguments.get("time_range_hours")
        if hours is not None and (
            not isinstance(hours, (int, float))
            or isinstance(hours, bool)
            or hours < 0
            or hours > self.max_time_range_hours
        ):
            raise PolicyViolation(f"time range exceeds allowed limit: {hours}")

        fields = arguments.get("fields") or []
        for field in fields:
            if any(fnmatchcase(str(field), pattern) for pattern in self.denied_fields):
                raise PolicyViolation(f"field is denied: {field}")

        timestamp_field = arguments.get("timestamp_field")
        if timestamp_field and any(
            fnmatchcase(str(timestamp_field), pattern) for pattern in self.denied_fields
        ):
            raise PolicyViolation(f"field is denied: {timestamp_field}")

        return ValidatedToolCall(tool=call.tool, arguments=arguments)

    def filter_index_discovery(self, payload: object) -> object:
        """Remove index records outside the allowlist before data reaches the LLM."""
        if isinstance(payload, list):
            return [
                item
                for item in (self.filter_index_discovery(value) for value in payload)
                if item is not None
            ]
        if isinstance(payload, dict):
            index_name = payload.get("index")
            if isinstance(index_name, str) and not self._is_concrete_index_allowed(index_name):
                return None
            return {
                key: self.filter_index_discovery(value)
                for key, value in payload.items()
            }
        return payload

    def _is_concrete_index_allowed(self, index: str) -> bool:
        if any(fnmatchcase(index, pattern) for pattern in self.denied_indices):
            return False
        return any(fnmatchcase(index, pattern) for pattern in self.allowed_indices)

    def _validate_index(self, index: str) -> None:
        if not index:
            raise PolicyViolation("index is empty")
        if any(fnmatchcase(index, pattern) for pattern in self.denied_indices):
            raise PolicyViolation(f"index is denied: {index}")

        contains_wildcard = any(char in index for char in "*?[")
        if contains_wildcard:
            allowed = index in self.allowed_indices
        else:
            allowed = any(fnmatchcase(index, pattern) for pattern in self.allowed_indices)

        if not allowed:
            raise PolicyViolation(f"index is outside allowlist: {index}")

    @staticmethod
    def _extract_esql_sources(query: str) -> list[str]:
        match = re.search(r"\bFROM\s+([^|]+)", query, flags=re.IGNORECASE)
        if not match:
            return []
        source_clause = re.split(
            r"\bMETADATA\b", match.group(1), maxsplit=1, flags=re.IGNORECASE
        )[0]
        return [
            item.strip().strip('"`')
            for item in source_clause.split(",")
            if item.strip()
        ]
