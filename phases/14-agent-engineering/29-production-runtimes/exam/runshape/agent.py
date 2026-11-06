"""The agent that every runtime shape wraps. The shells differ; the agent logic does not."""
from __future__ import annotations


def agent_steps(task: str) -> list[str]:
    """The five steps of one run, as in the lesson's demo agent."""
    return [
        f"parse: {task[:40]}",
        "plan: 3-step plan",
        "step 1: search",
        "step 2: read",
        f"final: answered {task[:20]}",
    ]


def answer(task: str) -> str:
    """Request-response: the caller waits for the whole run and gets the final step."""
    return agent_steps(task)[-1]
