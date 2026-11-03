"""Fit the catalog into its share of the model's context window."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable, Optional

from .catalog import CatalogEntry, entry_for, model_json, shorten
from .discovery import SkillCandidate

CATALOG_PERCENT = 2
FALLBACK_CATALOG_CHARS = 8_000
SHORT_DESCRIPTION_CHARS = 72


@dataclass(frozen=True)
class Budget:
    limit: int
    unit: str  # "tokens" or "chars"


@dataclass(frozen=True)
class FittedCatalog:
    entries: tuple[CatalogEntry, ...]
    shortened: tuple[str, ...]
    omitted: tuple[str, ...]
    budget: Budget
    used: int


def catalog_budget(context_window: Optional[int]) -> Budget:
    """The catalog's budget for a session.

    A known context window (in tokens) gives the catalog 2 percent of it, rounded down to a
    whole token. Only an unknown window (None) falls back to 8,000 characters. The two are
    never combined: a known window is not also held to 8,000 characters.
    """
    if context_window is None:
        return Budget(FALLBACK_CATALOG_CHARS, "chars")
    if context_window <= 0:
        raise ValueError(f"a context window has a positive size, got {context_window}")
    return Budget(context_window * CATALOG_PERCENT // 100, "tokens")


def fit_catalog(
    winners: Iterable[SkillCandidate],
    context_window: Optional[int],
    count_tokens: Callable[[str], int],
) -> FittedCatalog:
    """Publish the winners of collision policy within catalog_budget(context_window).

    Entries come in priority order: rank, then name. The cost is measured on model_json(entries),
    the exact text the model receives: with count_tokens for a budget in tokens, as len() for a
    budget in characters. While the catalog is over budget:

    1. descriptions longer than SHORT_DESCRIPTION_CHARS are shortened with shorten(), one entry
       at a time, lowest priority first, stopping as soon as the catalog fits;
    2. if it still does not fit, entries are omitted, lowest priority first, until it fits.

    Names are never shortened. shortened and omitted are in priority order, and an omitted entry
    is listed as omitted only. used is the final cost. ValueError if even an empty catalog is
    over budget.
    """
    budget = catalog_budget(context_window)
    measure = count_tokens if budget.unit == "tokens" else len
    ordered = sorted(winners, key=lambda c: (c.rank, c.name))
    entries = [entry_for(c) for c in ordered]
    used = measure(model_json(entries))
    shortened: list[str] = []
    for index in reversed(range(len(entries))):
        if used <= budget.limit:
            break
        entry = entries[index]
        short = shorten(entry.description, SHORT_DESCRIPTION_CHARS)
        if short != entry.description:
            entries[index] = replace(entry, description=short)
            shortened.append(entry.name)
            used = measure(model_json(entries))
    omitted: list[str] = []
    while used > budget.limit and entries:
        omitted.append(entries.pop().name)
        used = measure(model_json(entries))
    if used > budget.limit:
        raise ValueError("even an empty catalog is over budget")
    gone = set(omitted)
    return FittedCatalog(
        tuple(entries),
        tuple(name for name in reversed(shortened) if name not in gone),
        tuple(reversed(omitted)),
        budget,
        used,
    )
