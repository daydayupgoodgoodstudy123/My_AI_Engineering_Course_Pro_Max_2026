"""Worker leases, so that two instances sharing a directory never work on one task at once."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .task import check_task_id
from .wire import format_time, parse_time


class Leases:
    """Worker leases on tasks, one file per task: <taskId>.lease, next to the task files.

    A lease belongs to one holder until lease_ms have passed since it was taken, on the
    injected clock. acquire creates the lease file exclusively: it fails if the file is
    already there, so of two workers that try at once only one gets the lease. Once a
    lease has expired its holder is presumed dead, and any worker may take it over.
    """

    def __init__(
        self,
        directory: str | os.PathLike,
        *,
        clock: Callable[[], datetime],
        lease_ms: int = 30_000,
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lease_ms = lease_ms

    def acquire(self, task_id: str, holder: str) -> bool:
        """Take the task's lease for holder. False while another holder's lease is unexpired.

        A holder that already has the lease renews it.
        """
        path = self._path(task_id)
        lease = self._read(path)
        if lease is not None:
            if lease["holder"] != holder and not self._expired(lease):
                return False
            path.unlink(missing_ok=True)
        record = {
            "holder": holder,
            "expiresAt": format_time(self.clock() + timedelta(milliseconds=self.lease_ms)),
        }
        handle, temporary = tempfile.mkstemp(dir=self.directory, prefix=f".{task_id}.", suffix=".lease-tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(json.dumps(record))
            os.link(temporary, path)
        except FileExistsError:
            return False
        finally:
            os.unlink(temporary)
        return True

    def holds(self, task_id: str, holder: str) -> bool:
        """Whether holder has the task's lease and it has not expired."""
        lease = self._read(self._path(task_id))
        return lease is not None and lease["holder"] == holder and not self._expired(lease)

    def release(self, task_id: str, holder: str) -> None:
        """Give holder's lease back. A lease that now belongs to someone else stays."""
        path = self._path(task_id)
        lease = self._read(path)
        if lease is not None and lease["holder"] == holder:
            path.unlink(missing_ok=True)

    def _path(self, task_id: str) -> Path:
        return self.directory / f"{check_task_id(task_id)}.lease"

    def _read(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _expired(self, lease: dict[str, Any]) -> bool:
        return self.clock() >= parse_time(lease["expiresAt"])
