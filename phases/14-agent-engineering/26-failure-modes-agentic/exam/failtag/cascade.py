"""Cascade radius: how far each root-cause failure spread through a trace."""
from __future__ import annotations

from dataclasses import dataclass

from .trace import Trace, references


@dataclass(frozen=True)
class Cascade:
    step: int  # index of the root-cause failure
    radius: int  # steps it affected downstream
    depth: int  # hops along the longest chain of affected steps
    systems: list[str]  # systems those affected tool calls touched, sorted


def system_of(tool: str) -> str:
    """The system a tool belongs to: the part of its name before the first dot."""
    return tool.split(".", 1)[0]


def cascade_report(trace: Trace) -> list[Cascade]:
    """One Cascade per root-cause failure in the trace, in step order.

    Steps form a data-dependency DAG: step j depends on step i when references() of step j
    names i. A failure is a tool call with status "error". A step is affected by a failure
    when it depends on it directly or through other steps. A root cause is a failure that
    no other failure affects; failures that a root affects count in its radius, and a step
    affected by two roots counts for both.

    radius counts each affected step once, messages included. depth is the number of hops
    on the longest dependency chain from the root to an affected step. systems lists the
    system_of() of the affected tool calls, each once. A step that references itself, a
    later step or a step that does not exist makes the trace malformed: ValueError.
    """
    raise NotImplementedError
