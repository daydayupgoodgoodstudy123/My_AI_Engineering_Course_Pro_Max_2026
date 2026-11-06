"""A metrics observer: frames per pipeline stage, exposed in the Prometheus text format."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .frames import DOWNSTREAM


@dataclass(frozen=True)
class FrameEvent:
    t_ms: int  # call clock, never goes back
    stage: str  # name of the processor that saw the frame
    direction: str = DOWNSTREAM  # the way the frame was flowing: DOWNSTREAM or UPSTREAM


async def expose_metrics(
    events: AsyncIterator[FrameEvent], stages: list[str], window_ms: int = 1000
) -> AsyncIterator[str]:
    """Count frames per stage in fixed windows of the call clock and yield one
    Prometheus text exposition per window.

    Only DOWNSTREAM frames are counted, in both families: they are the data path,
    audio in and speech out, where latency builds up. UPSTREAM frames are control
    (a barge-in's cancel, metrics) and are not counted, but like every event they
    tell the time on the call clock.

    The windows are [0, window_ms), [window_ms, 2 * window_ms), ... and every one of
    them is yielded, with zeros if no frame arrived in it. A window is yielded as
    soon as an event at or after its end arrives; the window holding the last event
    is yielded when the events end.

    An exposition has two metric families, in this order: voice_frames_total (a
    counter of frames since the call started) and voice_window_frames (a gauge of
    frames in this window). Each family has a # HELP line, a # TYPE line and then one
    sample per stage, labelled stage="<name>" with the name escaped by _escape, in
    the order of `stages`.

    An event for a stage that is not in `stages` raises ValueError.
    """
    raise NotImplementedError


def _escape(value: str) -> str:
    r"""A label value in the Prometheus text format: \ becomes \\, " becomes \" and a
    line feed becomes \n. The backslash goes first, so the backslashes that the other
    two escapes add are not escaped again."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
