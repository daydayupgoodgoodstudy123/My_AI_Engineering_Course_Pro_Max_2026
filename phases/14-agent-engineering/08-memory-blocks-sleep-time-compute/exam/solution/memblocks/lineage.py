"""Where consolidated records come from, so a stale source can take its summaries down with it."""
from __future__ import annotations

from dataclasses import dataclass

from .archival import Archival


@dataclass(frozen=True)
class Rederive:
    """A consolidated record that has to be derived again."""

    rid: str
    chain: tuple[str, ...]  # derivations from the invalidated record down to rid, both included
    reason: str  # why the invalidated record is invalid


class Lineage:
    """Each summary or merged fact the sleep-time agent writes remembers its sources."""

    def __init__(self, archival: Archival) -> None:
        self.archival = archival
        self._sources: dict[str, tuple[str, ...]] = {}
        self._made_from: dict[str, list[str]] = {}  # source -> records derived from it
        self._created: dict[str, int] = {}

    def derive(self, text: str, sources: list[str], at: float = 0.0) -> str:
        """Insert a record made from sources and return its id.

        Sources must already be in the archive (unknown ids raise KeyError), so derivations
        never form a cycle.
        """
        for source in sources:
            self.archival.get(source)
        rid = self.archival.insert(text, at)
        self._sources[rid] = tuple(dict.fromkeys(sources))
        self._created[rid] = len(self._created)
        for source in self._sources[rid]:
            self._made_from.setdefault(source, []).append(rid)
        return rid

    def invalidate(self, rid: str, reason: str) -> list[Rederive]:
        """Invalidate rid, and every valid record made from it, directly or through other records.

        Each of those records is invalidated with the reason "derived from <source>", naming
        the record before it on its chain. A record's chain is the shortest path of derivations
        from rid down to it, and may pass through records that are already invalid; between
        equally short paths, the one through the earlier-created source. rid keeps its first
        reason if it was already invalid.

        Returns one Rederive per record this call invalidated, rid itself excluded, in creation
        order (so every record comes after the records it was made from). Each carries rid's
        reason as the archive holds it.
        """
        root = self.archival.get(rid)
        self.archival.invalidate(rid, reason)
        reached: set[str] = set()
        stack = [rid]
        while stack:  # no recursion: a chain of rolling summaries can be thousands deep
            for child in self._made_from.get(stack.pop(), ()):
                if child not in reached:
                    reached.add(child)
                    stack.append(child)
        chains = {rid: (rid,)}
        out = []
        for child in sorted(reached, key=self._created.__getitem__):
            via = min(
                (source for source in self._sources[child] if source in chains),
                key=lambda source: (len(chains[source]), self._created.get(source, -1)),
            )
            chains[child] = chains[via] + (child,)
            if self.archival.invalidate(child, f"derived from {via}"):
                out.append(Rederive(child, chains[child], root.reason))
        return out
