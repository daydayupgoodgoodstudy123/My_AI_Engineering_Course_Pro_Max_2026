"""What the agent runtime calls: discovery at session start, the catalog, and live disclosure."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable
from pathlib import Path
from typing import Optional

from .budget import FittedCatalog, fit_catalog
from .cache import DiscoveryCache
from .catalog import Catalog, CatalogBudget, CatalogEntry, build_catalog
from .disclosure import Request, disclosure_events
from .discovery import Discovery, Scope, discover_scope, resolve_collisions
from .refgraph import ReferenceReport, reference_graph


class SkillHost:
    def __init__(self, scopes: Iterable[Scope], cache: Optional[DiscoveryCache] = None) -> None:
        self.scopes = sorted(scopes, key=lambda scope: (scope.rank, scope.name))
        self.cache = cache

    def discover(self) -> Discovery:
        """Every configured scope, best rank first, through the cache when there is one."""
        candidates, rejected = [], []
        for scope in self.scopes:
            found = self.cache.discover(scope) if self.cache is not None else discover_scope(scope)
            candidates.extend(found.candidates)
            rejected.extend(found.rejected)
        return Discovery(tuple(candidates), tuple(rejected))

    def catalog(self, budget: CatalogBudget) -> Catalog:
        """The catalog under explicit operator limits (the catalog CLI)."""
        return build_catalog(self.discover().candidates, budget)

    def publish(self, context_window: Optional[int], count_tokens: Callable[[str], int]) -> FittedCatalog:
        """The catalog fitted to this session's context window."""
        winners, _ = resolve_collisions(self.discover().candidates)
        return fit_catalog(winners, context_window, count_tokens)

    def session(
        self,
        requests: AsyncIterator[Request],
        entries: Iterable[CatalogEntry],
        max_read_bytes: int = 4096,
    ) -> AsyncIterator[str]:
        """One session's activations and reads; disclosure_events defines the log lines."""
        return disclosure_events(requests, entries, max_read_bytes)

    def references(self, entry: CatalogEntry) -> ReferenceReport:
        """The reference graph of a published skill, for package review."""
        return reference_graph(Path(entry.source))
