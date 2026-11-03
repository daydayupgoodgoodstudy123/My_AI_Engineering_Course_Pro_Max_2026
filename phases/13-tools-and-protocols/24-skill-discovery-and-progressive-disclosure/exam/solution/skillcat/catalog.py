"""The model-facing catalog: one compact entry per published skill, under the operator's limits."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Optional

from .discovery import Collision, SkillCandidate, resolve_collisions


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    description: str
    scope: str
    source: str


@dataclass(frozen=True)
class CatalogBudget:
    """Operator limits for build_catalog."""

    max_entries: int = 50
    max_description_chars: int = 240
    max_catalog_chars: int = 8_000


@dataclass(frozen=True)
class Catalog:
    entries: tuple[CatalogEntry, ...]
    collisions: tuple[Collision, ...]
    omitted: tuple[str, ...]
    catalog_chars: int


def entry_for(candidate: SkillCandidate, description: Optional[str] = None) -> CatalogEntry:
    """The catalog entry of a candidate, with its own description unless another is given."""
    text = candidate.description if description is None else description
    return CatalogEntry(candidate.name, text, candidate.scope, str(candidate.source))


def model_json(entries: Iterable[CatalogEntry]) -> str:
    """The exact catalog text the model receives: compact JSON, sorted keys, non-ASCII kept."""
    payload = {"entries": [asdict(entry) for entry in entries]}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def shorten(text: str, limit: int) -> str:
    """text cut to at most limit characters, ending in an ellipsis when something was cut."""
    if limit < 1:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: limit - 1].rstrip() + "…"


def build_catalog(candidates: Iterable[SkillCandidate], budget: CatalogBudget) -> Catalog:
    """Resolve collisions, then publish the winners in priority order (rank, then name).

    Descriptions are shortened to max_description_chars and entries past max_entries are
    omitted. Then entries are omitted from the end until model_json(entries) is at most
    max_catalog_chars long. omitted lists every left-out name in priority order, and
    catalog_chars is len(model_json(entries)).
    """
    if min(budget.max_entries, budget.max_description_chars, budget.max_catalog_chars) < 1:
        raise ValueError("catalog budgets must be positive")
    winners, collisions = resolve_collisions(candidates)
    ordered = sorted(winners, key=lambda c: (c.rank, c.name))
    entries = [
        entry_for(c, shorten(c.description, budget.max_description_chars))
        for c in ordered[: budget.max_entries]
    ]
    omitted = [c.name for c in ordered[budget.max_entries :]]
    used = len(model_json([]))
    if used > budget.max_catalog_chars:
        raise ValueError("even an empty catalog exceeds max_catalog_chars")
    kept = 0
    for entry in entries:
        extra = len(model_json([entry])) - len(model_json([])) + (1 if kept else 0)
        if used + extra > budget.max_catalog_chars:
            break
        used += extra
        kept += 1
    omitted[:0] = [entry.name for entry in entries[kept:]]
    return Catalog(tuple(entries[:kept]), collisions, tuple(omitted), used)
