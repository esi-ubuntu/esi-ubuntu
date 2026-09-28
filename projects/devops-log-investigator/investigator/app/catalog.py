from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CatalogEntry:
    kind: str
    source_id: str
    title: str
    index_patterns: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    query: str | None = None


@dataclass(frozen=True)
class Catalog:
    entries: list[CatalogEntry]
    health: str
    error: str | None = None

    def find_candidates(self, concepts: list[str]) -> list[CatalogEntry]:
        needles = [value.strip().casefold() for value in concepts if value and value.strip()]
        if not needles:
            return []
        matches: list[CatalogEntry] = []
        for entry in self.entries:
            haystack = " ".join([entry.title, entry.query or "", *entry.index_patterns, *entry.fields]).casefold()
            if any(needle in haystack for needle in needles):
                matches.append(entry)
        return matches
