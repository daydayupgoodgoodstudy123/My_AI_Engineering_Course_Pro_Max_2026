"""The memory write path as a stream: extract facts, gate graph writes, refresh hot embeddings,
and audit every decision as a CSV row."""
from __future__ import annotations

import csv
import io
from collections import Counter
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
    uses: Counter[str] = Counter()
    lookups = 0
    async for event in events:
        if isinstance(event, Message):
            candidates = await extract(event.text)
            rid = mem.add(event.text, user_id=event.user_id, session_id=event.session_id)
            at = mem.record(rid).ts
            passing = [i for i, c in enumerate(candidates) if c.confidence >= policy.min_confidence]
            kept = set(sorted(passing, key=lambda i: -candidates[i].confidence)[: policy.max_edges])
            for i, c in enumerate(candidates):
                if c.confidence < policy.min_confidence:
                    yield _row(event.seq, "edge", c.subject, c.relation, c.obj, "drop", "low_confidence")
                elif i not in kept:
                    yield _row(event.seq, "edge", c.subject, c.relation, c.obj, "drop", "over_cap")
                else:
                    old = mem.graph.current(c.subject, c.relation)
                    if old is not None and old.obj == c.obj:
                        yield _row(event.seq, "edge", c.subject, c.relation, c.obj, "skip", "restated")
                        continue
                    mem.graph.add_edge(c.subject, c.relation, c.obj, rid=rid, at=at, weight=c.confidence)
                    yield _row(event.seq, "edge", c.subject, c.relation, c.obj, "write", "new" if old is None else "conflict")
                    if old is not None:
                        yield _row(event.seq, "edge", old.subject, old.relation, old.obj, "invalidate", "superseded")
        elif isinstance(event, Lookup):
            viewer = Viewer(event.user_id, event.session_id)
            for _, record in mem.search(event.text, viewer=viewer, top_k=policy.top_k):
                uses[record.rid] += 1
            lookups += 1
            if lookups % policy.reembed_every == 0:
                hot = sorted((rid for rid, n in uses.items() if n > 0), key=lambda rid: (-uses[rid], rid))
                for rid in hot[: policy.reembed_top]:
                    await reembed(mem.record(rid))
                    yield _row(event.seq, "record", rid, "", "", "reembed", f"uses={uses[rid]}")
                    uses[rid] = 0
        else:
            raise TypeError(f"unknown event {event!r}")


def _row(*fields: object) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(fields)
    return buf.getvalue()
