"""Rebuild every public call from the gateway's flat audit events."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .wire import TASK_METHODS


@dataclass
class Node:
    event: dict[str, Any]
    children: list[Node] = field(default_factory=list)


@dataclass
class Forest:
    calls: list[Node]
    orphans: list[Node]


def reconstruct(events: Iterable[dict[str, Any]]) -> Forest:
    """Put every audit event back into the public call it belongs to.

    The events are as the gateway records them (see Gateway._audit_decision and
    Gateway._audit_result), each with its log `seq`. A request is identified by
    (issuer, principal, trace_id, request_id): one "decision" event, and, when it
    was answered, one "result" event with the same identity. Request ids come from
    clients, so only the whole identity is unique.

    A request hangs under an earlier request of the same (issuer, principal) when
      - it is an MRTR retry: its decision's state_in is the state_out of that
        request's result; or
      - it is a task request (tasks/get, tasks/update, tasks/cancel): its decision's
        task_id is the task_id of that request's result, whose result is "task".
    A request with neither link starts a call.

    Every call is a Node for its first request. A request's node holds its result
    event as a leaf, and the requests that hang under it. Children, calls and orphans
    are each ordered by (ts, seq). Orphans are the events that belong to no call: a
    result whose decision is missing (a leaf), and a retry or task request whose link
    is not found (with everything under it).
    """
    raise NotImplementedError
