"""A research job under hard limits (Target architecture; Exercise 4)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from .a2a import DelegationFailed
from .agent import Agent
from .protocol import unwrap
from .trace import Span


@dataclass(frozen=True)
class Budget:
    tool_calls: int  # tools/call requests, retries included
    delegations: int  # A2A SendMessage calls
    wait_ms: int  # total time spent waiting between tasks/get polls


@dataclass
class Job:
    status: str  # "completed", "over_budget", "expired" or "failed"
    papers: list[str] = field(default_factory=list)  # arXiv ids the search found, in search order
    missing: list[str] = field(default_factory=list)  # found papers without a summary, in search order
    report: dict | None = None  # the report's final CallToolResult, once completed
    tool_calls: int = 0
    polls: int = 0


async def run_job(agent: Agent, query: str, budget: Budget) -> Job:
    """Run one research job within budget, through the agent's gateway, writer, sleep and clock.

    Discover the server; search with arxiv_search; delegate one summary per hit to the writer
    agent, all in flight at once; call generate_report with {"query", "summaries", "missing"};
    poll the report task with tasks/get until it is no longer working.

    - Every tools/call counts against budget.tool_calls, retries included. A result with
      isError: true is retried once; if it fails again the job ends "failed". A tools/call that
      would go over the budget is never sent: the job ends "over_budget".
    - Only the first budget.delegations hits are delegated. A hit that is not delegated, or
      whose delegation raises DelegationFailed, is missing, and the report is still generated.
      summaries ([{"arxiv_id", "text"}]) and missing keep search order.
    - Before each wait the job checks the clock. Once the task's ttlMs have passed since its
      handle arrived, it ends "expired". If waiting pollIntervalMs would take its total waiting
      past budget.wait_ms, it ends "over_budget". Otherwise it waits through agent.sleep and polls.
    - The completed task carries the final result; there is no tasks/result. A task that ends
      any other way than completed ends the job "failed".
    """
    job = Job("completed")
    root = agent.tracer.start("agent.invoke_agent", None, attrs={"gen_ai.operation.name": "invoke_agent"})
    try:
        agent.discover(parent=root)
        search = agent.tracer.start("tools/call arxiv_search", root, kind="CLIENT")
        try:
            found = _call(agent, job, budget, "arxiv_search", {"query": query})
        finally:
            agent.tracer.finish(search)
        if found is None:
            return job
        hits = json.loads(found["content"][0]["text"])
        job.papers = [hit["arxiv_id"] for hit in hits]

        chosen = hits[: max(budget.delegations, 0)]
        texts = await asyncio.gather(*(_summarize(agent, hit, root) for hit in chosen))
        summaries = [
            {"arxiv_id": hit["arxiv_id"], "text": text} for hit, text in zip(chosen, texts) if text is not None
        ]
        summarized = {summary["arxiv_id"] for summary in summaries}
        job.missing = [arxiv_id for arxiv_id in job.papers if arxiv_id not in summarized]

        report = agent.tracer.start("tools/call generate_report", root, kind="CLIENT")
        try:
            arguments = {"query": query, "summaries": summaries, "missing": list(job.missing)}
            handle = _call(agent, job, budget, "generate_report", arguments)
            if handle is not None:
                await _follow(agent, job, budget, handle, report)
        finally:
            agent.tracer.finish(report)
        return job
    finally:
        agent.tracer.finish(root)


def _call(agent: Agent, job: Job, budget: Budget, name: str, arguments: dict) -> dict | None:
    """One tools/call, retried once on isError. None, with job.status set, when the job stops."""
    for _ in range(2):
        if job.tool_calls >= budget.tool_calls:
            job.status = "over_budget"
            return None
        job.tool_calls += 1
        result = unwrap(agent.request("tools/call", {"name": name, "arguments": arguments}))
        if not result.get("isError"):
            return result
    job.status = "failed"
    return None


async def _summarize(agent: Agent, hit: dict, parent: Span) -> str | None:
    try:
        return await agent.delegate(hit, parent=parent)
    except DelegationFailed:
        return None


async def _follow(agent: Agent, job: Job, budget: Budget, handle: dict, parent: Span) -> None:
    if handle.get("resultType") != "task":
        job.report = handle
        return
    arrived = agent.clock()
    waited_ms = 0
    task = handle
    while task["status"] == "working":
        ttl = task.get("ttlMs")
        if ttl is not None and (agent.clock() - arrived) * 1000 >= ttl:
            job.status = "expired"
            return
        interval = task["pollIntervalMs"]
        if waited_ms + interval > budget.wait_ms:
            job.status = "over_budget"
            return
        await agent.sleep(interval / 1000)
        waited_ms += interval
        task = agent.get_task(task["taskId"], parent=parent)
        job.polls += 1
    if task["status"] == "completed":
        job.report = task["result"]
    else:
        job.status = "failed"
