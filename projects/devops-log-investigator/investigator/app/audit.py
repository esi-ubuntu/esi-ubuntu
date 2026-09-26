from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    request_id: str
    timestamp: datetime
    question: str
    status: str
    model_id: str
    resolved_time_window: dict[str, str] | None = None
    candidate_indices: list[str] = field(default_factory=list)
    selected_fields: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    result_counts: dict[str, int] = field(default_factory=dict)
    verification: str | None = None
    confidence: float | None = None
    repairs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "investigations.jsonl"

    def write(self, record: AuditRecord) -> Path:
        payload = asdict(record)
        payload["timestamp"] = record.timestamp.isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return self.path
