from __future__ import annotations

import json
from typing import Any

import httpx

from .catalog import Catalog, CatalogEntry


class KibanaClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        space_id: str | None = None,
        http_client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.space_id = space_id
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"
        self.http = http_client or httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout)

    def fetch_catalog(self) -> Catalog:
        prefix = f"/s/{self.space_id}" if self.space_id else ""
        params = [
            ("type", "data-view"),
            ("type", "index-pattern"),
            ("type", "search"),
            ("type", "dashboard"),
            ("type", "visualization"),
            ("type", "lens"),
            ("per_page", "10000"),
        ]
        try:
            response = self.http.get(f"{prefix}/api/saved_objects/_find", params=params)
        except httpx.RequestError as exc:
            return Catalog(entries=[], health="unavailable", error=str(exc))

        if response.status_code in (401, 403):
            return Catalog(entries=[], health="unauthorized", error=f"HTTP {response.status_code}")
        if response.status_code >= 400:
            return Catalog(entries=[], health="error", error=f"HTTP {response.status_code}")

        try:
            objects = response.json().get("saved_objects", [])
        except (ValueError, AttributeError) as exc:
            return Catalog(entries=[], health="error", error=f"invalid Kibana response: {exc}")

        parsed: list[tuple[CatalogEntry, list[dict[str, Any]]]] = []
        pattern_by_id: dict[str, list[str]] = {}
        for obj in objects:
            entry = self._parse_object(obj)
            if entry is None:
                continue
            references = obj.get("references") if isinstance(obj, dict) else []
            parsed.append((entry, references if isinstance(references, list) else []))
            if entry.kind in {"index-pattern", "data-view"}:
                pattern_by_id[entry.source_id] = entry.index_patterns

        entries: list[CatalogEntry] = []
        for entry, references in parsed:
            referenced_patterns = list(entry.index_patterns)
            for ref in references:
                if not isinstance(ref, dict):
                    continue
                if ref.get("type") in {"index-pattern", "data-view"}:
                    referenced_patterns.extend(pattern_by_id.get(str(ref.get("id", "")), []))
            entries.append(
                CatalogEntry(
                    kind=entry.kind,
                    source_id=entry.source_id,
                    title=entry.title,
                    index_patterns=list(dict.fromkeys(referenced_patterns)),
                    fields=entry.fields,
                    query=entry.query,
                )
            )
        return Catalog(entries=entries, health="ok")

    @staticmethod
    def _parse_object(obj: Any) -> CatalogEntry | None:
        if not isinstance(obj, dict) or not isinstance(obj.get("attributes"), dict):
            return None
        attrs = obj["attributes"]
        kind = str(obj.get("type", ""))
        source_id = str(obj.get("id", ""))
        title = str(attrs.get("title") or attrs.get("name") or "")
        if not kind or not source_id:
            return None

        patterns: list[str] = []
        if kind in {"index-pattern", "data-view"} and title:
            patterns.append(title)

        fields: list[str] = []
        raw_fields = attrs.get("fields")
        if isinstance(raw_fields, str):
            try:
                decoded_fields = json.loads(raw_fields)
                if isinstance(decoded_fields, list):
                    fields = [str(item["name"]) for item in decoded_fields if isinstance(item, dict) and item.get("name")]
            except ValueError:
                pass

        query: str | None = None
        meta = attrs.get("kibanaSavedObjectMeta")
        if isinstance(meta, dict) and isinstance(meta.get("searchSourceJSON"), str):
            try:
                search_source = json.loads(meta["searchSourceJSON"])
                candidate = search_source.get("query") if isinstance(search_source, dict) else None
                if isinstance(candidate, dict):
                    query_value = candidate.get("query")
                    if isinstance(query_value, str):
                        query = query_value
            except ValueError:
                pass

        return CatalogEntry(kind=kind, source_id=source_id, title=title, index_patterns=patterns, fields=fields, query=query)
