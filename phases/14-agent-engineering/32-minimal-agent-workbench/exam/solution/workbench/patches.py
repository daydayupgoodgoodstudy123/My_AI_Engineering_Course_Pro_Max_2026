"""Tell a watcher what each turn changed: one JSON Patch (RFC 6902) per turn, one per line."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .files import BOARD_FILE, STATE_FILE
from .turn import Runner, take_turn


def workbench_document(root: Path) -> dict[str, Any]:
    """The files a watcher mirrors, parsed: {"agent_state.json": ..., "task_board.json": ...}."""
    return {name: json.loads((root / name).read_text(encoding="utf-8")) for name in (STATE_FILE, BOARD_FILE)}


def diff(before: Any, after: Any) -> list[dict[str, Any]]:
    """The JSON Patch that turns before into after, using only add, replace and remove.

    Paths are JSON Pointers (RFC 6901): "/" before every reference token, with "~" written as
    "~0" and "/" written as "~1" inside a token. Objects are compared key by key: walking
    before's keys in order, a key that after lacks is removed and a key both have is compared;
    then the keys only after has are added, in after's order. Lists are compared position by
    position: the positions both have, in order, then after's extra items added at their own
    index, in order, or the items after lacks removed from the last one back. Any other
    difference, null included, is one replace. Equal values give no operations.
    """
    ops: list[dict[str, Any]] = []
    _compare(before, after, "", ops)
    return ops


def _compare(before: Any, after: Any, path: str, ops: list[dict[str, Any]]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key, value in before.items():
            child = f"{path}/{_token(key)}"
            if key in after:
                _compare(value, after[key], child, ops)
            else:
                ops.append({"op": "remove", "path": child})
        for key, value in after.items():
            if key not in before:
                ops.append({"op": "add", "path": f"{path}/{_token(key)}", "value": value})
    elif isinstance(before, list) and isinstance(after, list):
        shared = min(len(before), len(after))
        for index in range(shared):
            _compare(before[index], after[index], f"{path}/{index}", ops)
        for index in range(shared, len(after)):
            ops.append({"op": "add", "path": f"{path}/{index}", "value": after[index]})
        for index in range(len(before) - 1, shared - 1, -1):
            ops.append({"op": "remove", "path": f"{path}/{index}"})
    elif type(before) is not type(after) or before != after:
        ops.append({"op": "replace", "path": path, "value": after})


def _token(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def turn_patches(root: Path, run: Runner, turns: int) -> Iterator[str]:
    """Run take_turn on the workbench in root, turns times, and yield one line per turn as it ends.

    A line is json.dumps(patch) + "\\n", where patch is the diff from the workbench_document the
    watcher has (the one the previous line left it with, or the files as the stream started) to
    the files after this turn. Edits that people make to the files between turns therefore reach
    the watcher with the next line. A turn that changes nothing still yields "[]\\n", so the
    watcher gets exactly one line per turn.
    """
    sent = workbench_document(root)
    for _ in range(turns):
        take_turn(root, run)
        current = workbench_document(root)
        yield json.dumps(diff(sent, current)) + "\n"
        sent = current
