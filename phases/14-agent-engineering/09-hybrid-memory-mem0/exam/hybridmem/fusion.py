"""Fused recall across the three stores: relevance, importance and recency in one weighted sum."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .memory import Mem0, Viewer

KV_HIT = 1.0  # the relevance of an exact KV hit


@dataclass(frozen=True)
class Query:
    """A query after query understanding: its text, the KV keys and the graph entities it names."""

    text: str
    kv_keys: tuple[tuple[str, str], ...] = ()  # (fact_type, entity) pairs
    entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class FusionConfig:
    w_relevance: float = 0.6
    w_importance: float = 0.2
    w_recency: float = 0.2
    halflife_s: float = 86400.0
    scope_weights: Mapping[str, float] = field(default_factory=lambda: {"user": 1.0, "session": 1.0, "agent": 1.0})


@dataclass(frozen=True)
class Hit:
    rid: str
    score: float
    relevance: float


def recall(mem: Mem0, query: Query, *, viewer: Viewer, config: FusionConfig = FusionConfig(), top_k: int = 5) -> list[Hit]:
    """The viewer's top_k memories for a query, fused across the three stores, best first.

    A record's relevance is the largest of what the stores give it:
      vector  cosine similarity between the token counts (memory.tokens) of query.text and of the record's text
      kv      KV_HIT if the viewer's KV store maps one of query.kv_keys to the record
      graph   the weight of an edge that holds now, has one of query.entities as its subject
              or its object, and was asserted by the record
    Candidates are the records some store finds (relevance above 0) that the viewer can see
    and whose scope is in config.scope_weights. Each one scores
      scope_weights[scope] * (w_relevance * relevance + w_importance * importance + w_recency * recency)
    with the weights used as given. recency = 0.5 ** (age / halflife_s), where age is the time
    since the record was last touched (a record from the future has age 0); halflife_s = 0
    turns recency off (1.0 for every record). Ties go to the lower rid.

    The records returned have been read: their last_read becomes now, once every score is in.
    """
    raise NotImplementedError
