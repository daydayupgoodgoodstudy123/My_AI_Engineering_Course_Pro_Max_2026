"""Worker leases, so that two instances sharing a directory never work on one task at once."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

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
        raise NotImplementedError

    def holds(self, task_id: str, holder: str) -> bool:
        """Whether holder has the task's lease and it has not expired."""
        raise NotImplementedError

    def release(self, task_id: str, holder: str) -> None:
        """Give holder's lease back. A lease that now belongs to someone else stays."""
        raise NotImplementedError
