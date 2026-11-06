"""The overlap structure of a conversation: who holds the floor, and who talks inside whose turn."""
from __future__ import annotations


def overlap_tree(
    spurts: list[tuple[str, int, int]], sample_rate: int, backchannel_ms: int = 1000
) -> list[dict]:
    """Nest talk spurts by time.

    spurts are (speaker, start, end) half-open sample ranges, in any order. A spurt that lies
    within another speaker's spurt (starts at or after its start and ends at or before its end)
    goes inside it, inside the last such spurt in time order when several qualify. Every other
    spurt is a turn.

    Each node is {"speaker", "start", "end", "kind", "inside"}. kind is "turn" at the top level;
    a nested spurt is a "backchannel" when it is shorter than backchannel_ms, else an "overlap".
    "inside" lists the spurts nested in it. Lists are in time order, and when two spurts start
    together the longer one comes first.

    An empty spurt, or two spurts of one speaker that overlap (merge them first), raises ValueError.
    """
    order = sorted(spurts, key=lambda s: (s[1], -s[2]))
    roots: list[dict] = []
    running: list[dict] = []  # spurts not yet over, in time order
    busy_until: dict[str, int] = {}
    for speaker, start, end in order:
        if not start < end:
            raise ValueError(f"empty spurt {speaker!r} [{start}, {end})")
        if start < busy_until.get(speaker, start):
            raise ValueError(f"{speaker!r} overlaps their own speech at sample {start}")
        busy_until[speaker] = end
        running = [n for n in running if n["end"] > start]
        node = {"speaker": speaker, "start": start, "end": end, "kind": "turn", "inside": []}
        parent = next(
            (n for n in reversed(running) if n["end"] >= end and n["speaker"] != speaker), None
        )
        if parent is None:
            roots.append(node)
        else:
            short = (end - start) * 1000 < backchannel_ms * sample_rate
            node["kind"] = "backchannel" if short else "overlap"
            parent["inside"].append(node)
        running.append(node)
    return roots
