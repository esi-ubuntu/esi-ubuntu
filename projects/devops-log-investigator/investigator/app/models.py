from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ValidatedToolCall:
    tool: str
    arguments: dict[str, Any]
