"""A live debate: every round's model calls in flight together, one CSV record per round."""
from __future__ import annotations

import asyncio
import csv
import io
import time
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable

from .engine import Ask, Reads, Reply, check_reads

AsyncDebater = Callable[[Ask], Awaitable[Reply]]


async def live_debate(
    question: str,
    debaters: dict[str, AsyncDebater],
    reads: Reads,
    rounds: int,
    timeout_s: float,
) -> AsyncIterator[str]:
    """Run a debate round by round and report each round as soon as it ends.

    Round 0 asks every debater for an opening answer with no peers; rounds 1..rounds are
    synchronous critique rounds over reads, as in engine.debate (no forced disagreement, no
    aggregation). Within a round all debaters are asked at once, and the next round starts
    only after every call of this one has finished.

    A call that has not replied after timeout_s seconds is cancelled, and the cancellation
    has finished before the round is reported. That debater abstains for the round: next
    round its peers skip it (no op), and its own Ask.own is the last reply it did give.

    The first string yielded is the CSV header
        round,<one column per debater, roster order>,agree_ratio,ops,elapsed_ms
    and every later string is one CSV record (csv.writer quoting and line ending) per round:
    the answer in each debater's column (empty for an abstainer); agree_ratio, the share of
    the answering debaters holding the most common answer, with three decimals (abstainers
    are not counted; empty when nobody answered); ops, the peer replies read this round; and
    elapsed_ms, the round's wall-clock time in whole milliseconds.

    The debate ends after the first critique round in which every debater answered and all
    the answers are the same, or after round `rounds`.
    """
    names = list(debaters)
    check_reads(names, reads)
    yield _record(["round", *names, "agree_ratio", "ops", "elapsed_ms"])
    last: dict[str, Reply] = {}  # each debater's latest reply, kept across abstentions
    prior: dict[str, Reply] = {}  # replies of the round before, from those who answered
    for r in range(rounds + 1):
        asks: dict[str, Ask] = {}
        ops = 0
        for name in names:
            peers = tuple((peer, prior[peer]) for peer in reads[name] if peer in prior)
            ops += len(peers)
            asks[name] = Ask(question, r, last.get(name), peers)
        start = time.perf_counter()
        replies = await asyncio.gather(*(_ask(debaters[n], asks[n], timeout_s) for n in names))
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        current = {name: reply for name, reply in zip(names, replies) if reply is not None}
        last.update(current)
        answers = [reply.answer for reply in current.values()]
        ratio = f"{max(Counter(answers).values()) / len(answers):.3f}" if answers else ""
        cells = [current[name].answer if name in current else "" for name in names]
        yield _record([r, *cells, ratio, ops, elapsed_ms])
        if r >= 1 and len(current) == len(names) and len(set(answers)) == 1:
            return
        prior = current


async def _ask(debater: AsyncDebater, ask: Ask, timeout_s: float) -> Reply | None:
    try:
        return await asyncio.wait_for(debater(ask), timeout_s)
    except asyncio.TimeoutError:
        return None


def _record(row: list) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(row)
    return out.getvalue()
