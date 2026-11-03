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
    result: dict[str, int] = {}
    for span in trace.spans:
        pieces = sorted(
            (max(child.start_ns, span.start_ns), min(child.end_ns, span.end_ns))
            for child in trace.children_of(span)
        )
        covered = 0
        run_start = run_end = None
        for start, end in pieces:
            if end <= start:
                continue
            if run_end is None or start > run_end:
                if run_end is not None:
                    covered += run_end - run_start
                run_start, run_end = start, end
            else:
                run_end = max(run_end, end)
        if run_end is not None:
            covered += run_end - run_start
        result[span.span_id] = span.end_ns - span.start_ns - covered
    return result


def critical_path(trace: Trace, root: Span) -> list[Span]:
    """The heaviest chain from root down to a leaf: the chain whose self times add up to the most.

    root is where the chain starts, usually one of trace.roots. From each span the chain goes on into
    the child whose own heaviest chain is heaviest; when children tie, into the one with the smaller
    span id. The chain ends at a span with no children.
    """
    own = self_times(trace)
    heaviest: dict[str, int] = {}

    def weight(span: Span) -> int:
        if span.span_id not in heaviest:
            below = max((weight(child) for child in trace.children_of(span)), default=0)
            heaviest[span.span_id] = own[span.span_id] + below
        return heaviest[span.span_id]

    path = [root]
    while trace.children_of(path[-1]):
        path.append(min(trace.children_of(path[-1]), key=lambda child: (-weight(child), child.span_id)))
    return path
