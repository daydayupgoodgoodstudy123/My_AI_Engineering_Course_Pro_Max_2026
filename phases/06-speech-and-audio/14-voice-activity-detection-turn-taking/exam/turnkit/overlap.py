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
    raise NotImplementedError
