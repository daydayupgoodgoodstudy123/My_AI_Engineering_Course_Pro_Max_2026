"""Mem0-shaped hybrid memory: a vector store, a KV store and a graph store behind one add/search surface.

Every add() writes one record to the vector store, its KV facts to the KV store and the
relationships it asserts to the graph store. Token overlap stands in for embeddings.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from .graph import GraphStore

SCOPES = ("user", "session", "agent")


@dataclass
class Record:
    rid: str
    text: str
    scope: str
    user_id: str
    session_id: str
    agent_id: str
    importance: float
    ts: float
    tags: tuple[str, ...] = ()
    last_read: float | None = None

    @property
    def touched(self) -> float:
        """When the record was last written or read."""
        return self.ts if self.last_read is None else max(self.ts, self.last_read)


@dataclass(frozen=True)
class Viewer:
    """Who is asking: a user, in one session, talking to one agent."""

    user_id: str
    session_id: str
    agent_id: str = "assistant"

    def can_see(self, record: Record) -> bool:
        """Every memory belongs to one user, whatever its scope.

        A session memory is also kept to its session, and an agent memory to its agent.
        """
        if record.user_id != self.user_id:
            return False
        if record.scope == "session":
            return record.session_id == self.session_id
        if record.scope == "agent":
            return record.agent_id == self.agent_id
        return True


def tokens(text: str) -> list[str]:
    """Lower-case word tokens."""
    return re.findall(r"\w+", text.lower())


class VectorStore:
    """Records, searchable by text similarity. Token overlap stands in for an embedding model."""

    def __init__(self) -> None:
        self._records: dict[str, Record] = {}

    def add(self, record: Record) -> None:
        self._records[record.rid] = record

    def get(self, rid: str) -> Record:
        """The record with this rid. Unknown rids raise KeyError."""
        return self._records[rid]

    def records(self) -> list[Record]:
        """Every record, in the order they were added."""
        return list(self._records.values())

    def search(
        self,
        query: str,
        top_k: int | None = 5,
        where: Callable[[Record], bool] | None = None,
    ) -> list[tuple[float, Record]]:
        """(Jaccard similarity, record) pairs for the records that share a token with the query.

        Best first; ties keep insertion order. where, when given, keeps only the records it
        accepts, and is applied before the list is cut to top_k. top_k=None keeps every match.
        """
        q = set(tokens(query))
        scored: list[tuple[float, Record]] = []
        for record in self._records.values():
            if where is not None and not where(record):
                continue
            r = set(tokens(record.text))
            overlap = len(q & r)
            if overlap:
                scored.append((overlap / len(q | r), record))
        scored.sort(key=lambda pair: -pair[0])
        return scored if top_k is None else scored[:top_k]


@dataclass(frozen=True)
class KVKey:
    user_id: str
    fact_type: str
    entity: str


class KVStore:
    """Facts keyed on (user_id, fact_type, entity). A later put of the same key replaces the earlier one."""

    def __init__(self) -> None:
        self._map: dict[KVKey, Record] = {}

    def put(self, key: KVKey, record: Record) -> None:
        self._map[key] = record

    def get(self, key: KVKey) -> Record | None:
        return self._map.get(key)

    def by_user(self, user_id: str) -> list[Record]:
        return [r for k, r in self._map.items() if k.user_id == user_id]

    def items(self) -> list[tuple[KVKey, Record]]:
        return list(self._map.items())


@dataclass
class Mem0Config:
    w_relevance: float = 0.6
    w_importance: float = 0.2
    w_recency: float = 0.2
    recency_halflife_s: float = 86400.0


class Mem0:
    """The add/search facade over the three stores."""

    def __init__(self, config: Mem0Config | None = None, *, clock: Callable[[], float] = time.time) -> None:
        self.vector = VectorStore()
        self.kv = KVStore()
        self.graph = GraphStore()
        self.config = config or Mem0Config()
        self.clock = clock
        self._counter = 0

    def now(self) -> float:
        return float(self.clock())

    def add(
        self,
        text: str,
        *,
        user_id: str,
        session_id: str,
        scope: str = "user",
        agent_id: str = "assistant",
        importance: float = 0.5,
        tags: tuple[str, ...] = (),
        kv_triples: tuple[tuple[str, str], ...] = (),
        graph_triples: tuple[tuple[str, str, str], ...] = (),
    ) -> str:
        """Write one memory to all three stores and return its rid: m001, m002, ...

        kv_triples are (fact_type, entity) pairs: the KV store maps (user_id, fact_type, entity)
        to this record. graph_triples are (subject, relation, object) edges this record asserts.
        """
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {scope!r}")
        now = self.now()
        self._counter += 1
        rid = f"m{self._counter:03d}"
        record = Record(rid, text, scope, user_id, session_id, agent_id, float(importance), now, tuple(tags))
        self.vector.add(record)
        for fact_type, entity in kv_triples:
            self.kv.put(KVKey(user_id, fact_type, entity), record)
        for subject, relation, obj in graph_triples:
            self.graph.add_edge(subject, relation, obj, rid=rid, at=now)
        return rid

    def record(self, rid: str) -> Record:
        """The record with this rid. Unknown rids raise KeyError."""
        return self.vector.get(rid)

    def _recency(self, record: Record, now: float) -> float:
        elapsed = max(0.0, now - record.touched)
        half = self.config.recency_halflife_s
        return 0.5 ** (elapsed / half) if half > 0 else 1.0

    def search(self, query: str, *, viewer: Viewer, top_k: int = 5) -> list[tuple[float, Record]]:
        """The viewer's best top_k memories for a query, as (score, record) pairs, best first.

        This is the vector path only; fusion.recall is the search that reads all three stores.
        The candidates are the top_k * 3 records most similar to the query among the ones the
        viewer can see (Viewer.can_see), so a memory that shares no token with the query never
        comes back, and neither does another user's memory or a session or agent memory from
        somewhere else. Each candidate is scored
            w_relevance * similarity + w_importance * importance + w_recency * recency,
        where recency halves every recency_halflife_s after the record was last touched.
        Ties go to the lower rid. Searching does not change any record.
        """
        now = self.now()
        c = self.config
        fused: list[tuple[float, Record]] = []
        for rel, record in self.vector.search(query, top_k=top_k * 3, where=viewer.can_see):
            score = c.w_relevance * rel + c.w_importance * record.importance + c.w_recency * self._recency(record, now)
            fused.append((score, record))
        fused.sort(key=lambda pair: (-pair[0], pair[1].rid))
        return fused[:top_k]
