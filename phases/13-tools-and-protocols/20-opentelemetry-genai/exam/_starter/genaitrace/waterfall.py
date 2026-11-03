"""Where the time went: self time and the heaviest chain of a linked trace."""
from __future__ import annotations

from .traces import Trace
from .tracer import Span


def self_times(trace: Trace) -> dict[str, int]:
    """Self time of every span in the trace, in nanoseconds, keyed by span id.

    A span's self time is its duration minus the part of it that its children cover. Children can run
    at the same time, so the covered part is the length of the union of their intervals, not the sum
    of their durations. Each child's interval is first clipped to the parent's [start_ns, end_ns]: a
    child that starts before its parent or ends after it (clock skew between processes, work left
    running) covers only the part inside the parent, and a child entirely outside covers nothing.
    """
    raise NotImplementedError


def critical_path(trace: Trace, root: Span) -> list[Span]:
    """The heaviest chain from root down to a leaf: the chain whose self times add up to the most.

    root is where the chain starts, usually one of trace.roots. From each span the chain goes on into
    the child whose own heaviest chain is heaviest; when children tie, into the one with the smaller
    span id. The chain ends at a span with no children.
    """
    raise NotImplementedError
