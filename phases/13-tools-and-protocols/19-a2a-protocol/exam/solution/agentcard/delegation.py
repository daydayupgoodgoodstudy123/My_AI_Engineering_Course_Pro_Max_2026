"""What each caller can see of a multi-hop delegation.

A delegation plan is a tree of tasks. Each node is one task, run by one agent:

  {"task": its id,
   "agent": the agent that runs it,
   "required": whether its caller needs it to complete (default true),
   "forward": whether its caller passes on what it returns as the caller's own artifacts (default false),
   "fails": whether the agent's own work fails (default false),
   "steps": the agent's internal steps, such as tool calls and notes (default []),
   "artifacts": what it returns when it completes, each {"name", "mimeType", "parts", ...} (default []),
   "delegates": the tasks it delegates, in order (default [])}

Every task has its own id, even when one agent runs several tasks of the plan.
"""
from __future__ import annotations

import copy

DEFAULTS = {"required": True, "forward": False, "fails": False}


def caller_views(plan: dict, max_hops: int) -> dict[str, list[dict]]:
    """Run a delegation plan and return what each caller sees of the tasks it delegated.

    The client's own delegation, the root of the plan, is hop 1, and each delegation below it adds a
    hop. A task more than max_hops hops from the client is rejected: it never runs, so it returns
    nothing and delegates nothing.

    A task that runs first runs all of its delegates, in order. It then fails if its own work fails or
    if a delegate it requires did not complete, and completes otherwise. A completed task returns its
    own artifacts, then everything returned by each delegate it forwards, in delegate order (only a
    completed task returns anything). A failed or rejected task returns nothing.

    The result maps "client" to the client's view of the root task, and the id of every task that ran
    and delegated something to its views of those delegates, in order. A view is {"task", "agent",
    "state", "artifacts"} and nothing else, and each artifact in it keeps only "name", "mimeType" and
    "parts": a caller never learns about deeper delegations or anyone's internal steps. The plan is left
    as it was.

    Raises ValueError for max_hops below 1 or a task id used twice in the plan.
    """
    if max_hops < 1:
        raise ValueError("max_hops must be at least 1")
    _check_ids(plan, set())
    views: dict[str, list[dict]] = {}

    def run(node: dict, hop: int) -> dict:
        if hop > max_hops:
            return _view(node, "rejected", [])
        delegates = node.get("delegates", [])
        seen = [run(child, hop + 1) for child in delegates]
        if seen:
            views[node["task"]] = seen
        missing = any(
            _flag(child, "required") and view["state"] != "completed"
            for child, view in zip(delegates, seen)
        )
        if _flag(node, "fails") or missing:
            return _view(node, "failed", [])
        returned = [_public(artifact) for artifact in node.get("artifacts", [])]
        for child, view in zip(delegates, seen):
            if _flag(child, "forward"):
                returned += copy.deepcopy(view["artifacts"])
        return _view(node, "completed", returned)

    views["client"] = [run(plan, 1)]
    return views


def _flag(node: dict, name: str) -> bool:
    return node.get(name, DEFAULTS[name])


def _view(node: dict, state: str, artifacts: list[dict]) -> dict:
    return {"task": node["task"], "agent": node["agent"], "state": state, "artifacts": artifacts}


def _public(artifact: dict) -> dict:
    return {key: copy.deepcopy(artifact[key]) for key in ("name", "mimeType", "parts")}


def _check_ids(node: dict, seen: set[str]) -> None:
    if node["task"] in seen:
        raise ValueError(f"task id {node['task']!r} is used twice")
    seen.add(node["task"])
    for child in node.get("delegates", []):
        _check_ids(child, seen)
