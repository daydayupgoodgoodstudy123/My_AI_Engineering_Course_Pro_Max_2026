"""The research agent: an MCP client behind the gateway, and an A2A client of the writer agent."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .a2a import PEER, SKILL, Writer
from .protocol import request_meta, unwrap
from .trace import Span, Tracer


class Denied(Exception):
    """The gateway refused a request."""

    def __init__(self, response: dict) -> None:
        super().__init__(response)
        self.response = response


class TaskFailed(Exception):
    """A task ended without completing."""

    def __init__(self, task: dict) -> None:
        super().__init__(f"task {task.get('taskId')} ended {task.get('status')}")
        self.task = task


@dataclass
class Run:
    trace_id: str
    papers: list[dict]  # search hits: {"arxiv_id", "title", "year"}
    summaries: list[dict]  # {"arxiv_id", "text"}
    report: dict  # generate_report's final CallToolResult


class Agent:
    def __init__(
        self,
        gateway: object,
        token: str,
        writer: Writer,
        *,
        tracer: Tracer | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """sleep takes seconds, like asyncio.sleep; clock returns seconds, like time.monotonic."""
        self.gateway = gateway
        self.token = token
        self.writer = writer
        self.tracer = tracer if tracer is not None else Tracer()
        self.sleep = sleep
        self.clock = clock

    def request(self, method: str, params: dict) -> dict:
        """Send one request through the gateway and return the response as it came back.

        Every request carries fresh _meta. tools/call and the tasks/* methods declare the Tasks
        extension: the server decides which tools/call becomes a task, so the extension has to be
        declared in the request that may receive the handle. A refusal by the gateway raises Denied.
        """
        tasks = method.startswith("tasks/")
        request = {"method": method, "params": {**params, "_meta": request_meta(tasks=tasks)}}
        response = self.gateway.handle(self.token, request)
        if isinstance(response.get("error"), str):
            raise Denied(response)
        return response

    def discover(self, *, parent: Span) -> dict:
        """server/discover, in a "server/discover" span under parent."""
        span = self.tracer.start("server/discover", parent, kind="CLIENT")
        try:
            return unwrap(self.request("server/discover", {}))
        finally:
            self.tracer.finish(span)

    async def call_tool(self, name: str, arguments: dict, *, parent: Span) -> dict:
        """Call one tool and return its final CallToolResult.

        The call runs in a "tools/call <name>" span under parent. When the server answers with a
        task handle, call_tool polls tasks/get until the task is no longer working, waiting the
        server's current pollIntervalMs through self.sleep before each poll. Every poll gets its
        own "tasks/get" span under the tools/call span. A JSON-RPC error raises ProtocolError,
        and a task that ends without completing raises TaskFailed.
        """
        span = self.tracer.start(f"tools/call {name}", parent, kind="CLIENT", attrs={"gen_ai.tool.name": name})
        try:
            response = self.request("tools/call", {"name": name, "arguments": arguments})
            return await self._settle(response, parent)
        finally:
            self.tracer.finish(span)

    async def _settle(self, response: dict, parent: Span) -> dict:
        result = unwrap(response)
        if result.get("resultType") != "task":
            return result
        task = result
        while task["status"] == "working":
            time.sleep(task["pollIntervalMs"] / 1000)
            task = self.get_task(task["taskId"], parent=parent)
        if task["status"] != "completed":
            raise TaskFailed(task)
        return task["result"]

    def get_task(self, task_id: str, *, parent: Span) -> dict:
        """One tasks/get, in a "tasks/get" span under parent. Returns the task snapshot."""
        span = self.tracer.start("tasks/get", parent, kind="CLIENT", attrs={"mcp.task.id": task_id})
        try:
            return unwrap(self.request("tasks/get", {"taskId": task_id}))
        finally:
            self.tracer.finish(span)

    async def delegate(self, paper: dict, *, parent: Span) -> str:
        """Ask the writer agent for one summary over A2A (SendMessage).

        The writer stays opaque: one "a2a.SendMessage" span under parent is all the trace holds of it.
        """
        span = self.tracer.start(
            "a2a.SendMessage", parent, kind="CLIENT", attrs={"a2a.peer": PEER, "a2a.skill": SKILL}
        )
        try:
            return await self.writer.send_message(paper)
        finally:
            self.tracer.finish(span)

    async def research(self, query: str) -> Run:
        """One research run under a root span "agent.invoke_agent": discover the server, search,
        delegate one summary per hit, then generate the report."""
        root = self.tracer.start("agent.invoke_agent", None, attrs={"gen_ai.operation.name": "invoke_agent"})
        try:
            self.discover(parent=root)
            found = await self.call_tool("arxiv_search", {"query": query}, parent=root)
            papers = json.loads(found["content"][0]["text"])
            summaries = []
            for paper in papers:
                text = await self.delegate(paper, parent=root)
                summaries.append({"arxiv_id": paper["arxiv_id"], "text": text})
            report = await self.call_tool(
                "generate_report", {"query": query, "summaries": summaries}, parent=root
            )
            return Run(root.trace_id, papers, summaries, report)
        finally:
            self.tracer.finish(root)
