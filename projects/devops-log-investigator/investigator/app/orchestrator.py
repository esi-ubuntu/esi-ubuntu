from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .audit import AuditRecord, AuditWriter
from .catalog import Catalog
from .models import LLMResponse, Message, ToolCall, ToolSpec
from .policy import Policy, PolicyViolation
from .redaction import redact_payload


@dataclass(frozen=True)
class InvestigationResult:
    answer_fa: str
    status: str
    confidence: float
    resolved_time_window: dict[str, str] | None
    indices: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    verification: str = "not_verified"
    request_id: str = ""


class Investigator:
    def __init__(
        self,
        *,
        policy: Policy,
        catalog: Catalog,
        llm: Any,
        mcp: Any,
        audit_writer: AuditWriter | None = None,
        sensitive_fields: set[str] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.policy = policy
        self.catalog = catalog
        self.llm = llm
        self.mcp = mcp
        self.audit_writer = audit_writer
        self.sensitive_fields = set(sensitive_fields or ())
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    async def investigate(self, question: str, now: datetime | None = None) -> InvestigationResult:
        request_id = uuid4().hex
        current_time = now or datetime.now(timezone.utc)
        messages = self._initial_messages(question, current_time)
        tool_specs = _tool_specs()

        queries: list[str] = []
        indices: list[str] = []
        fields: list[str] = []
        repairs: list[str] = []
        analytic_results: list[object] = []
        calls = 0

        max_turns = self.policy.max_calls + self.policy.max_repairs + 6
        for _ in range(max_turns):
            try:
                response: LLMResponse = await self.llm.chat(messages, tool_specs)
            except Exception as exc:
                return self._finish_not_verified(
                    question=question,
                    current_time=current_time,
                    request_id=request_id,
                    reason=f"local LLM unavailable: {exc}",
                    queries=queries,
                    indices=indices,
                    fields=fields,
                    repairs=repairs,
                )

            if response.tool_calls:
                for proposed in response.tool_calls:
                    if calls >= self.policy.max_calls:
                        return self._finish_not_verified(
                            question=question,
                            current_time=current_time,
                            request_id=request_id,
                            reason="maximum Elasticsearch call budget reached",
                            queries=queries,
                            indices=indices,
                            fields=fields,
                            repairs=repairs,
                        )
                    try:
                        validated = self.policy.validate_tool_call(
                            ToolCall(tool=proposed.name, arguments=proposed.arguments)
                        )
                    except PolicyViolation as exc:
                        if len(repairs) >= self.policy.max_repairs:
                            return self._finish_not_verified(
                                question=question,
                                current_time=current_time,
                                request_id=request_id,
                                reason=f"query rejected by policy: {exc}",
                                queries=queries,
                                indices=indices,
                                fields=fields,
                                repairs=repairs,
                            )
                        repairs.append(str(exc))
                        messages.append(
                            Message(
                                role="system",
                                content=(
                                    "درخواست ابزار توسط گارد امنیتی رد شد. علت: "
                                    f"{exc}. فقط با داده و ایندکس‌های مجاز دوباره برنامه‌ریزی کن."
                                ),
                            )
                        )
                        break

                    calls += 1
                    self._track_call(validated.tool, validated.arguments, queries, indices, fields)
                    try:
                        raw_result = await self.mcp.call(validated.tool, validated.arguments)
                    except Exception as exc:
                        if len(repairs) >= self.policy.max_repairs:
                            return self._finish_not_verified(
                                question=question,
                                current_time=current_time,
                                request_id=request_id,
                                reason=f"Elasticsearch tool failed: {exc}",
                                queries=queries,
                                indices=indices,
                                fields=fields,
                                repairs=repairs,
                            )
                        repairs.append(f"{validated.tool}: {exc}")
                        messages.append(
                            Message(
                                role="system",
                                content=f"اجرای ابزار {validated.tool} شکست خورد: {exc}. فرضیه/کوئری را اصلاح کن.",
                            )
                        )
                        break

                    safe_result = redact_payload(raw_result, self.sensitive_fields)
                    messages.append(
                        Message(
                            role="tool",
                            content=json.dumps(
                                {"tool": validated.tool, "result": safe_result},
                                ensure_ascii=False,
                                default=str,
                            ),
                        )
                    )
                    if validated.tool in {"search", "esql"}:
                        analytic_results.append(raw_result)
                continue

            final = _parse_final_response(response.content)
            if final is None:
                if len(repairs) >= self.policy.max_repairs:
                    return self._finish_not_verified(
                        question=question,
                        current_time=current_time,
                        request_id=request_id,
                        reason="model did not return a valid structured final answer",
                        queries=queries,
                        indices=indices,
                        fields=fields,
                        repairs=repairs,
                    )
                repairs.append("invalid final response")
                messages.append(
                    Message(
                        role="system",
                        content="پاسخ نهایی نامعتبر بود. فقط JSON نهایی با status، answer_fa، confidence و resolved_time_window برگردان.",
                    )
                )
                continue

            status = str(final.get("status") or "DATA_NOT_VERIFIED")
            if status == "OK" and _has_unverified_zero(analytic_results):
                if len(repairs) >= self.policy.max_repairs:
                    return self._finish_not_verified(
                        question=question,
                        current_time=current_time,
                        request_id=request_id,
                        reason="zero result could not be independently verified",
                        queries=queries,
                        indices=indices,
                        fields=fields,
                        repairs=repairs,
                    )
                repairs.append("suspicious zero required probe/repair")
                messages.append(
                    Message(
                        role="system",
                        content=(
                            "نتیجه صفر هنوز قابل اعتماد نیست. قبل از پاسخ نهایی با mapping/sample کوچک بررسی کن "
                            "که مقدار/نام فیلد درست است، سپس کوئری اصلاح‌شده و یک cross-check مستقل اجرا کن."
                        ),
                    )
                )
                continue

            verification = "not_verified"
            if status == "OK":
                verification = "cross_checked" if len(analytic_results) >= 2 else "single_source"

            result = InvestigationResult(
                answer_fa=str(final.get("answer_fa") or ""),
                status=status,
                confidence=_bounded_confidence(final.get("confidence")),
                resolved_time_window=_normalized_time_window(final.get("resolved_time_window")),
                indices=_dedupe(indices),
                fields=_dedupe(fields),
                queries=list(queries),
                verification=verification,
                request_id=request_id,
            )
            self._write_audit(result, question, current_time, repairs)
            return result

        return self._finish_not_verified(
            question=question,
            current_time=current_time,
            request_id=request_id,
            reason="investigation turn budget exhausted",
            queries=queries,
            indices=indices,
            fields=fields,
            repairs=repairs,
        )

    def _initial_messages(self, question: str, now: datetime) -> list[Message]:
        catalog_payload = [
            {
                "kind": entry.kind,
                "title": entry.title,
                "index_patterns": entry.index_patterns,
                "fields": entry.fields,
                "query": entry.query,
            }
            for entry in self.catalog.entries[:50]
        ]
        return [
            Message(role="system", content=self.system_prompt),
            Message(
                role="system",
                content=json.dumps(
                    {
                        "current_time": now.isoformat(),
                        "kibana_catalog_health": self.catalog.health,
                        "kibana_catalog": catalog_payload,
                    },
                    ensure_ascii=False,
                ),
            ),
            Message(role="user", content=question),
        ]

    @staticmethod
    def _track_call(
        tool: str,
        arguments: dict[str, Any],
        queries: list[str],
        indices: list[str],
        fields: list[str],
    ) -> None:
        index = arguments.get("index")
        if isinstance(index, str):
            indices.append(index)
        requested_fields = arguments.get("fields")
        if isinstance(requested_fields, list):
            fields.extend(str(value) for value in requested_fields)
        if tool == "esql":
            query = arguments.get("query")
            if isinstance(query, str):
                queries.append(query)
                indices.extend(Policy._extract_esql_sources(query))

    def _finish_not_verified(
        self,
        *,
        question: str,
        current_time: datetime,
        request_id: str,
        reason: str,
        queries: list[str],
        indices: list[str],
        fields: list[str],
        repairs: list[str],
    ) -> InvestigationResult:
        result = InvestigationResult(
            answer_fa=f"DATA_NOT_VERIFIED: {reason}",
            status="DATA_NOT_VERIFIED",
            confidence=0.0,
            resolved_time_window=None,
            indices=_dedupe(indices),
            fields=_dedupe(fields),
            queries=list(queries),
            verification="not_verified",
            request_id=request_id,
        )
        self._write_audit(result, question, current_time, repairs)
        return result

    def _write_audit(
        self,
        result: InvestigationResult,
        question: str,
        timestamp: datetime,
        repairs: list[str],
    ) -> None:
        if self.audit_writer is None:
            return
        model_id = str(getattr(self.llm, "model", "local-llm"))
        self.audit_writer.write(
            AuditRecord(
                request_id=result.request_id,
                timestamp=timestamp,
                question=question,
                status=result.status,
                model_id=model_id,
                resolved_time_window=result.resolved_time_window,
                candidate_indices=result.indices,
                selected_fields=result.fields,
                queries=result.queries,
                verification=result.verification,
                confidence=result.confidence,
                repairs=list(repairs),
            )
        )


def _tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="list_indices",
            description="List readable Elasticsearch indices when the relevant data location is unknown.",
            input_schema={"type": "object", "properties": {}},
        ),
        ToolSpec(
            name="get_mappings",
            description="Inspect mappings for an approved index pattern.",
            input_schema={"type": "object", "properties": {"index": {"type": "string"}}, "required": ["index"]},
        ),
        ToolSpec(
            name="search",
            description="Run a small bounded read-only sample/search on an approved index.",
            input_schema={
                "type": "object",
                "properties": {
                    "index": {"type": "string"},
                    "rows": {"type": "integer"},
                    "time_range_hours": {"type": "number"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index"],
            },
        ),
        ToolSpec(
            name="esql",
            description="Execute a read-only ES|QL aggregation/query on approved FROM sources.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        ),
    ]


def _parse_final_response(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    if not isinstance(value.get("status"), str) or not isinstance(value.get("answer_fa"), str):
        return None
    return value


def _has_unverified_zero(results: list[object]) -> bool:
    if not results:
        return False
    last_numeric = None
    for result in results:
        state = _result_state(result)
        if state in {"zero", "positive"}:
            last_numeric = state
    if last_numeric != "zero":
        return False
    zero_count = sum(1 for result in results if _result_state(result) == "zero")
    return zero_count < 2


def _result_state(value: object) -> str:
    if isinstance(value, dict):
        numeric_values: list[float] = []
        for key, item in value.items():
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                key_text = str(key).casefold()
                if any(token in key_text for token in ("count", "people", "duplicate", "check", "total", "value", " c", "c")):
                    numeric_values.append(float(item))
        if numeric_values:
            return "zero" if all(item == 0 for item in numeric_values) else "positive"
        for key in ("hits", "rows"):
            item = value.get(key)
            if isinstance(item, list):
                return "zero" if not item else "positive"
    return "unknown"


def _bounded_confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _normalized_time_window(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return {"start": start, "end": end}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


_DEFAULT_SYSTEM_PROMPT = """تو یک Investigator کاملاً read-only برای Elasticsearch/Kibana هستی.
هیچ نام index یا field را حدس قطعی نزن: از catalog، mapping و probe کوچک برای کشف معنا استفاده کن.
هر ابزار فقط خواندنی است و گارد بیرونی محدودیت‌ها را اعمال می‌کند.
برای نتیجه صفر، قبل از پاسخ نهایی صحت نام field/value و وجود داده مرتبط را probe کن و سپس cross-check مستقل انجام بده.
برای نتایج مثبت مهم نیز در صورت امکان یک cross-check مستقل بزن.
اگر معنای داده قابل اثبات نیست، status=DATA_NOT_VERIFIED بده و عدد نساز.
پاسخ نهایی فقط JSON باشد با کلیدهای status، answer_fa، confidence، resolved_time_window.
"""
