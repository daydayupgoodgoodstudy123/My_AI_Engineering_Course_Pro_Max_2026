"""Where tasks are kept. Both stores have the same interface, so TaskService takes either."""
from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .task import TASK_ID, Task, check_task_id
from .wire import format_time, parse_time


class MemoryStore:
    """Tasks kept in this process's memory, for tests and single-process demos.

    Nothing survives a restart and no other instance sees these tasks. get returns a
    copy, so a change to a task is stored only when it is saved.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create(self, task: Task) -> None:
        """Store a new task. ValueError if its id is malformed or already taken."""
        if check_task_id(task.task_id) in self._tasks:
            raise ValueError(f"task {task.task_id} already exists")
        self._tasks[task.task_id] = copy.deepcopy(task)

    def get(self, task_id: str) -> Task | None:
        """The stored task, or None if there is none. ValueError for a malformed id."""
        task = self._tasks.get(check_task_id(task_id))
        return copy.deepcopy(task) if task is not None else None

    def save(self, task: Task) -> None:
        """Store this version of the task, replacing the previous one."""
        self._tasks[check_task_id(task.task_id)] = copy.deepcopy(task)

    def delete(self, task_id: str) -> None:
        """Remove the task. Removing a task that is not there is not an error."""
        self._tasks.pop(check_task_id(task_id), None)

    def task_ids(self) -> list[str]:
        """Every stored task id, sorted."""
        return sorted(self._tasks)


class TaskStore:
    """Tasks shared through a directory, one JSON file per task: <taskId>.json.

    Every instance that opens the same directory sees the same tasks, at once: a write
    by one instance is what the next get on any other instance returns. Only files named
    <taskId>.json are tasks; anything else in the directory (a temporary file a crashed
    writer left behind, a lease) is not a task and is ignored.

    The file holds one JSON object, dataclasses.asdict(task), with created_at and
    last_updated_at written as wire timestamps (wire.format_time), for example
    "2026-08-21T10:30:00Z". Every instance reads and writes this same format. Everything
    else in a task is plain JSON data, and save raises TypeError for a task that holds
    anything JSON cannot. A write goes to a temporary file in the same directory, which
    is then renamed over <taskId>.json: a reader sees the old record or the new one,
    never part of one, and a write that fails leaves the old record in place.

    Task ids come from clients and end up in file names, so every method checks them
    first (task.check_task_id) and raises ValueError for a malformed one.
    """

    def __init__(self, directory: str | os.PathLike) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def create(self, task: Task) -> None:
        """Store a new task. ValueError if its id is malformed or already taken."""
        path = self._path(task.task_id)
        if path.exists():
            raise ValueError(f"task {task.task_id} already exists")
        self._write(path, task)

    def get(self, task_id: str) -> Task | None:
        """The stored task, or None if there is none. ValueError for a malformed id."""
        try:
            text = self._path(task_id).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return _decode(text)

    def save(self, task: Task) -> None:
        """Store this version of the task, replacing the previous one."""
        self._write(self._path(task.task_id), task)

    def delete(self, task_id: str) -> None:
        """Remove the task. Removing a task that is not there is not an error."""
        self._path(task_id).unlink(missing_ok=True)

    def task_ids(self) -> list[str]:
        """Every stored task id, sorted."""
        return sorted(
            path.stem for path in self.directory.glob("*.json") if TASK_ID.fullmatch(path.stem)
        )

    def _path(self, task_id: str) -> Path:
        return self.directory / f"{check_task_id(task_id)}.json"

    def _write(self, path: Path, task: Task) -> None:
        text = _encode(task)
        handle, temporary = tempfile.mkstemp(dir=self.directory, prefix=f".{task.task_id}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise


def _encode(task: Task) -> str:
    record = asdict(task)
    record["created_at"] = format_time(task.created_at)
    record["last_updated_at"] = format_time(task.last_updated_at)
    return json.dumps(record, indent=2, sort_keys=True)


def _decode(text: str) -> Task:
    record = json.loads(text)
    record["created_at"] = parse_time(record["created_at"])
    record["last_updated_at"] = parse_time(record["last_updated_at"])
    return Task(**record)
