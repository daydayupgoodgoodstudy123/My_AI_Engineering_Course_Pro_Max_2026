"""What a communication topology lets a debate do, before any model is called."""
from __future__ import annotations

from dataclasses import dataclass

from .engine import Reads


@dataclass
class Analysis:
    ops_per_round: int  # critique ops one round costs
    reach: dict[str, int | None]  # rounds until this debater's opening answer reaches everyone
    rounds_needed: int | None  # rounds until every opening answer reaches everyone
    deaf: list[str]  # debaters that read no one else
    camps: list[list[str]]  # groups of debaters whose answers all reach one another


def analyze(reads: Reads) -> Analysis:
    """Analyze a read graph: {debater: the peers it reads}.

    Topologies written by hand may list a debater reading itself, or the same peer twice;
    both are ignored. A peer that is not a debater raises ValueError naming it.

    Information flows from the peer to the reader: when a reads b, b's answer from round
    r - 1 is in front of a in round r, and a can pass it on in round r + 1.

    ops_per_round   distinct (reader, other debater) pairs.
    reach[x]        the smallest number of critique rounds after which x's opening answer
                    has reached every debater, directly or passed along (0 when x is alone);
                    None when some debater can never get it.
    rounds_needed   the largest reach, or None when any reach is None.
    deaf            debaters that read no other debater, in roster order (the order of reads).
    camps           every debater in exactly one camp: the debaters x and y share a camp when
                    x's answer can reach y and y's can reach x. Members in roster order, camps
                    ordered by their first member.
    """
    raise NotImplementedError
