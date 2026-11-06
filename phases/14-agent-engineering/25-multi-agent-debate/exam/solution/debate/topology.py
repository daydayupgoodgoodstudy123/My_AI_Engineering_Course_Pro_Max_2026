"""What a communication topology lets a debate do, before any model is called."""
from __future__ import annotations

from collections import deque
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
    names = list(reads)
    known = set(names)
    peers: dict[str, list[str]] = {}
    for name, listed in reads.items():
        unknown = [p for p in listed if p not in known]
        if unknown:
            raise ValueError(f"{name} reads unknown debaters {unknown}")
        peers[name] = list(dict.fromkeys(p for p in listed if p != name))
    listeners: dict[str, list[str]] = {name: [] for name in names}
    for reader in names:
        for peer in peers[reader]:
            listeners[peer].append(reader)

    rounds_to: dict[str, dict[str, int]] = {}
    for source in names:
        dist = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for reader in listeners[node]:
                if reader not in dist:
                    dist[reader] = dist[node] + 1
                    queue.append(reader)
        rounds_to[source] = dist

    reach = {
        name: max(dist.values()) if len(dist) == len(names) else None
        for name, dist in rounds_to.items()
    }
    values = list(reach.values())
    rounds_needed = None if None in values or not values else max(values)

    camps: list[list[str]] = []
    placed: set[str] = set()
    for name in names:
        if name in placed:
            continue
        camp = [other for other in names if other in rounds_to[name] and name in rounds_to[other]]
        placed.update(camp)
        camps.append(camp)

    return Analysis(
        ops_per_round=sum(len(p) for p in peers.values()),
        reach=reach,
        rounds_needed=rounds_needed,
        deaf=[name for name in names if not peers[name]],
        camps=camps,
    )
