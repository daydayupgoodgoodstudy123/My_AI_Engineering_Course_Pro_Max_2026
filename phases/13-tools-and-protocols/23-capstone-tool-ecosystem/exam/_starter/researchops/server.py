"""The research MCP server, simulated in process (the lesson's server_discover, tools and tasks_get).

It answers server/discover, tools/call for arxiv_search and generate_report, tasks/get and
tasks/cancel. It opens no transport and searches nothing real: arxiv_search filters a static
list of papers, and generate_report always becomes a task that moves one step per tasks/get, as
a ReportPlan scripts it. Task ids are sequential so runs are reproducible; a real server issues
unguessable ids.
"""
from __future__ import annotations

import html
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .catalog import Paper
from .protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PROTOCOL_VERSION,
    SERVER_INFO_KEY,
    TASKS,
    check_meta,
    error,
)

SERVER_INFO = {"name": "research-simulator", "version": "1.0.0"}
EPOCH = datetime(2026, 7, 28, tzinfo=timezone.utc)
TASK_FIELDS = ("taskId", "status", "createdAt", "lastUpdatedAt", "ttlMs", "pollIntervalMs", "result")


@dataclass
class ReportPlan:
    """How generate_report tasks behave.

    intervals[0] is the pollIntervalMs on the task handle and intervals[i] the one on the i-th
    tasks/get snapshot. The task completes on tasks/get number len(intervals). With
    finishes=False it never does, and the last interval repeats.
    """

    intervals: list[int] = field(default_factory=lambda: [1000])
    finishes: bool = True
    ttl_ms: int = 900_000


class ResearchServer:
    def __init__(
        self,
        papers: list[Paper],
        *,
        plan: ReportPlan | None = None,
        failing_searches: int = 0,
        clock: Callable[[], float] = lambda: 0.0,
    ) -> None:
        """failing_searches: how many arxiv_search calls answer isError: true before searches work.
        clock: seconds, used only for the task timestamps."""
        self.papers = list(papers)
        self.plan = plan or ReportPlan()
        self.failing_searches = failing_searches
        self.clock = clock
        self.tasks: dict[str, dict] = {}

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        params = request.get("params", {})
        meta = params.get("_meta")
        if method == "server/discover":
            return self._discover(meta)
        if method == "tools/call":
            return self._call(params, meta)
        if method == "tasks/get":
            return self._get(params, meta)
        if method == "tasks/cancel":
            return self._cancel(params, meta)
        return error(METHOD_NOT_FOUND, "Method not found", {"method": method})

    def _discover(self, meta: object) -> dict:
        invalid = check_meta(meta)
        if invalid:
            return invalid
        return self._complete(
            supportedVersions=[PROTOCOL_VERSION],
            capabilities={"tools": {"listChanged": False}, "extensions": {TASKS: {}}},
            ttlMs=3_600_000,
            cacheScope="public",
        )

    def _call(self, params: dict, meta: object) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {})
        invalid = check_meta(meta, require_tasks=name == "generate_report")
        if invalid:
            return invalid
        if name == "arxiv_search":
            return self._search(arguments)
        if name == "generate_report":
            return self._start_report(arguments)
        return error(INVALID_PARAMS, f"Unknown tool: {name}")

    def _search(self, arguments: dict) -> dict:
        if self.failing_searches:
            self.failing_searches -= 1
            return self._complete(
                content=[{"type": "text", "text": "search backend unavailable"}], isError=True
            )
        query = str(arguments.get("query", "")).lower()
        hits = [
            {"arxiv_id": p.arxiv_id, "title": p.title, "year": p.year}
            for p in self.papers
            if query in p.title.lower()
        ]
        return self._complete(content=[{"type": "text", "text": json.dumps(hits)}], isError=False)

    def _start_report(self, arguments: dict) -> dict:
        task_id = f"tsk_{len(self.tasks) + 1:04d}"
        now = self._now()
        self.tasks[task_id] = {
            "taskId": task_id,
            "status": "working",
            "createdAt": now,
            "lastUpdatedAt": now,
            "ttlMs": self.plan.ttl_ms,
            "pollIntervalMs": self.plan.intervals[0],
            "arguments": deepcopy(arguments),
            "polls": 0,
        }
        return {"resultType": "task", **self._public(self.tasks[task_id]), "_meta": self._server_meta()}

    def _get(self, params: dict, meta: object) -> dict:
        invalid = check_meta(meta, require_tasks=True)
        if invalid:
            return invalid
        task_id = params.get("taskId")
        if not isinstance(task_id, str) or task_id not in self.tasks:
            return error(INVALID_PARAMS, "Unknown taskId")
        task = self.tasks[task_id]
        if task["status"] == "working":
            task["polls"] += 1
            task["lastUpdatedAt"] = self._now()
            intervals = self.plan.intervals
            if self.plan.finishes and task["polls"] >= len(intervals):
                task["status"] = "completed"
                task["result"] = self._report(task_id, task["arguments"])
                del task["pollIntervalMs"]
            else:
                task["pollIntervalMs"] = intervals[min(task["polls"], len(intervals) - 1)]
        return self._complete(**self._public(task))

    def _cancel(self, params: dict, meta: object) -> dict:
        invalid = check_meta(meta, require_tasks=True)
        if invalid:
            return invalid
        task_id = params.get("taskId")
        if not isinstance(task_id, str) or task_id not in self.tasks:
            return error(INVALID_PARAMS, "Unknown taskId")
        task = self.tasks[task_id]
        if task["status"] == "working":
            task["status"] = "cancelled"
            task["lastUpdatedAt"] = self._now()
            del task["pollIntervalMs"]
        return self._complete()

    def _report(self, task_id: str, arguments: dict) -> dict:
        summaries = arguments.get("summaries", [])
        missing = arguments.get("missing", [])
        uri = f"ui://report/{task_id}"
        items = "".join(
            f"<li>{html.escape(s['arxiv_id'])}: {html.escape(s['text'])}</li>" for s in summaries
        )
        return self._complete(
            content=[
                {
                    "type": "text",
                    "text": f"Report on {arguments.get('query', '')!r}: "
                    f"{len(summaries)} summaries, {len(missing)} missing.",
                },
                {"type": "ui_resource", "uri": uri},
            ],
            ui={"resourceUri": uri, "csp": {"default-src": "'self'"}, "permissions": []},
            html=f"<!doctype html><html><body><h1>Research report</h1><ul>{items}</ul></body></html>",
            isError=False,
        )

    def _public(self, task: dict) -> dict:
        return {key: deepcopy(task[key]) for key in TASK_FIELDS if key in task}

    def _complete(self, **fields: object) -> dict:
        return {"resultType": "complete", **fields, "_meta": self._server_meta()}

    def _server_meta(self) -> dict:
        return {SERVER_INFO_KEY: dict(SERVER_INFO)}

    def _now(self) -> str:
        moment = EPOCH + timedelta(seconds=self.clock())
        return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")
