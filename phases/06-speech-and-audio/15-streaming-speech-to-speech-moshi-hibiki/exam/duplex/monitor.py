"""Watch a live duplex session: its uplink and downlink, merged frame by frame."""
from __future__ import annotations

from collections.abc import AsyncIterator


async def timeline(
    uplink: AsyncIterator[list[dict]],
    downlink: AsyncIterator[list[dict]],
) -> AsyncIterator[str]:
    """Merge the two directions of a session into one NDJSON line per frame, as packets arrive.

    Each direction delivers bursts (lists) of packets {"frame": t, "voiced": bool}. The model
    sends a packet every 80 ms like the user does, silent frames included. Within a direction
    frame numbers only go up (ValueError otherwise), but a frame can be missing: a lost packet.

    The line for frame t is {"frame": t, "ms": t * 80, "user": ..., "model": ..., "overlap": ...,
    "barge_in": ...}. user and model are that side's voiced flag, or null if it never delivered
    frame t. overlap means both are voiced; barge_in means an overlap the user started: the user
    was not voiced in frame t - 1 (null counts as not voiced). Lines run from frame 0 to the last
    frame either side delivered, and frame t's line goes out as soon as each side has delivered
    frame t, moved past it, or ended.
    """
    raise NotImplementedError
