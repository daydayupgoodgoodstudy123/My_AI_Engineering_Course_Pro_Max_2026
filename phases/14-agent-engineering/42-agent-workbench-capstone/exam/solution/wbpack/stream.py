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
    done = []
    try:
        for op in operations:
            if not dry_run and op.kind != "skip":
                path = root / op.path
                before = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.exists() else None
                if before_write is not None:
                    before_write(op)
                if op.kind == "remove":
                    path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(op.data)
                done.append((op.path, before))
            yield _line(op)
    except Exception:
        for rel, before in reversed(done):
            path = root / rel
            if before is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before[0])
                path.chmod(before[1])
            yield f"rollback {rel}\n"
        raise
