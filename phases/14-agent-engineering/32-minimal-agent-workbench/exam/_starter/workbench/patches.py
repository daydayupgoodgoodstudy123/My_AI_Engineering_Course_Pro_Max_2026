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
    raise NotImplementedError


def turn_patches(root: Path, run: Runner, turns: int) -> Iterator[str]:
    """Run take_turn on the workbench in root, turns times, and yield one line per turn as it ends.

    A line is json.dumps(patch) + "\\n", where patch is the diff from the workbench_document the
    watcher has (the one the previous line left it with, or the files as the stream started) to
    the files after this turn. Edits that people make to the files between turns therefore reach
    the watcher with the next line. A turn that changes nothing still yields "[]\\n", so the
    watcher gets exactly one line per turn.
    """
    raise NotImplementedError
