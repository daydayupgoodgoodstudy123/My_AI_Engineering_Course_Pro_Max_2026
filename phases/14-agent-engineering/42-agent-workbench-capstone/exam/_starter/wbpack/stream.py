"""Incremental, reversible installation operations."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
import stat


@dataclass(frozen=True)
class Operation:
    kind: str
    path: str
    data: bytes = b""


def _line(op: Operation) -> str:
    codes = {"add": ">f+++++++++", "update": ">f.st......", "remove": "*deleting", "skip": "skip"}
    suffix = " (locally modified)" if op.kind == "skip" else ""
    return f"{codes[op.kind]} {op.path}{suffix}\n"


def stream_install(root: Path, operations: Iterable[Operation], dry_run: bool = False,
                   before_write: Callable[[Operation], None] | None = None) -> Iterator[str]:
    """Apply one operation, then immediately yield one complete itemize-style line.

    This exercise defines four codes in _line; these are not an rsync protocol.
    Paths can contain spaces. Dry-run emits the same forward lines, makes no
    writes and calls no before_write hook. On an execution error restore every
    completed non-skip operation, in reverse execution order, yielding
    'rollback <path>\n' after each restoration, then re-raise the original error.
    The hook runs before a non-skip operation changes disk. Restoring includes
    original bytes and permission bits; an added file must become absent again.
    """
    raise NotImplementedError
