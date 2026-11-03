"""A research job under hard limits (Target architecture; Exercise 4)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .agent import Agent


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
    raise NotImplementedError
