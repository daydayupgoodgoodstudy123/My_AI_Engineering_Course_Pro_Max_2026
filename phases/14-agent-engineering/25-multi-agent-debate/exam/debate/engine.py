"""Debate over any communication topology, with forced disagreement and
confidence-weighted aggregation."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

Reads = dict[str, list[str]]  # {debater: the peers it reads, in reading order}


@dataclass(frozen=True)
class Reply:
    answer: str
    confidence: float  # in [0, 1]


@dataclass(frozen=True)
class Ask:
    """What one debater is shown in one round."""

    question: str
    round: int  # 0 for the opening proposals, then 1..rounds
    own: Reply | None  # this debater's reply from the round before (None in round 0)
    peers: tuple[tuple[str, Reply], ...]  # (peer, its reply from the round before), in reads order
    taken: tuple[str, ...] = ()  # round 0 only: answers already proposed, first proposal first


Debater = Callable[[Ask], Reply]


@dataclass
class Outcome:
    answer: str
    weights: dict[str, float]  # total confidence per answer in the last round played
    history: list[dict[str, Reply]]  # history[r]: every debater's reply in round r
    ops: list[int]  # ops[r]: critique ops spent in round r (ops[0] == 0)
    converged_round: int | None


def check_reads(names: list[str], reads: Reads) -> None:
    """reads must have one entry per debater, and name only other debaters, each once."""
    if set(reads) != set(names):
        raise ValueError("reads needs exactly one entry per debater")
    for name, peers in reads.items():
        if len(set(peers)) != len(peers):
            raise ValueError(f"{name} reads a peer twice")
        for peer in peers:
            if peer == name:
                raise ValueError(f"{name} cannot read itself")
            if peer not in reads:
                raise ValueError(f"{name} reads unknown debater {peer!r}")


def debate(
    question: str,
    debaters: dict[str, Debater],
    reads: Reads,
    rounds: int,
    min_rounds: int = 1,
) -> Outcome:
    """Run one debate and aggregate the final round.

    Round 0, opening proposals: debaters are asked one at a time, in roster order (the order
    of `debaters`). Each Ask carries `taken`, the distinct answers proposed so far in this
    round, so the debater can pick a different one (forced disagreement). A debater that
    repeats a taken answer anyway keeps it: nobody is asked twice in a round.

    Rounds 1..rounds, critique: synchronous. In round r every debater sees only round r - 1:
    its own reply and the replies of the peers in reads[name], in that order. Each peer read
    is one critique op.

    The debate stops after the first critique round r >= min_rounds in which every debater
    gives the same answer (converged_round = r); otherwise all rounds are played and
    converged_round is None.

    The answer is the one with the largest total confidence in the last round played. A tie
    goes to the answer with more supporters, then to the answer whose first supporter comes
    first in roster order.

    reads is checked with check_reads(). A reply with a confidence outside [0, 1] raises
    ValueError naming the debater.
    """
    raise NotImplementedError
