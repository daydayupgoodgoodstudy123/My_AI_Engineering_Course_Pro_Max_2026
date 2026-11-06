"""The memory write path as a stream: extract facts, gate graph writes, refresh hot embeddings,
and audit every decision as a CSV row."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from .memory import Mem0, Record, Viewer


@dataclass(frozen=True)
class Message:
    """A chat message to remember."""

    seq: int
    user_id: str
    session_id: str
    text: str


@dataclass(frozen=True)
class Lookup:
    """A memory search the agent ran."""

    seq: int
    user_id: str
    session_id: str
    text: str


@dataclass(frozen=True)
class Candidate:
    """An edge the extractor proposes, with its confidence."""

    subject: str
    relation: str
    obj: str
    confidence: float


@dataclass(frozen=True)
class WritePolicy:
    max_edges: int = 5  # candidate edges kept per message
    min_confidence: float = 0.5
    reembed_every: int = 100  # lookups between re-embedding rounds
    reembed_top: int = 10  # records re-embedded per round
    top_k: int = 5  # results per lookup


async def ingest(
    events: AsyncIterator[Message | Lookup],
    mem: Mem0,
    *,
    extract: Callable[[str], Awaitable[list[Candidate]]],
    reembed: Callable[[Record], Awaitable[None]],
    policy: WritePolicy = WritePolicy(),
) -> AsyncIterator[str]:
    """Run the write path over a stream of events, yielding each audit row as soon as it is decided.

    A Message becomes a record (mem.add), and the extractor proposes edges for it. A candidate
    below min_confidence is dropped (low_confidence). Of the rest, the max_edges most confident
    are kept, ties going to the one the extractor listed first; the others are dropped
    (over_cap). A kept candidate whose object already holds is skipped (restated); otherwise
    it is written to the graph, asserted by the new record, with its confidence as the weight
    (new, or conflict when it closes the current edge). The edge it closes gets its own row
    straight after (invalidate, superseded).

    A Lookup runs mem.search for its user and session (policy.top_k results), and every record
    returned counts as one use. After every reembed_every-th lookup, the reembed_top records
    with the most uses (at least one; ties to the lower rid) are re-embedded, in that order,
    and their count starts again from zero.

    Each yielded string is one CSV row, line break included, with no header:
        seq, kind, subject, relation, object, decision, reason
    kind is edge for graph decisions (decision write / skip / drop / invalidate), and record
    for re-embedding, with the rid as subject, empty relation and object, decision reembed and
    reason uses=<count>. seq is the seq of the event that led to the row. Rows come in the
    extractor's order.
    """
    raise NotImplementedError
