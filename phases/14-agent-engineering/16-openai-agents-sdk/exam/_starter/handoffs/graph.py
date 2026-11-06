"""The handoff graph of an app: which agents a run can reach, and where its guardrails do not reach."""
from __future__ import annotations

from .agents import Agent


class HandoffGraph:
    """An edge from every agent to each of its handoff targets.

    agents are the agents the app defines; their handoff targets belong to the graph too. Two
    different agents with the same name raise ValueError, since the model could not tell their
    transfer_to_<name> tools apart. Unknown agent names raise KeyError.
    """

    def __init__(self, agents: list[Agent]) -> None:
        raise NotImplementedError

    def reachable(self, entry: str) -> list[str]:
        """The names of the agents a run that starts at entry can reach, entry included, sorted."""
        raise NotImplementedError

    def path_to_tool(self, entry: str, tool: str) -> list[str] | None:
        """The shortest handoff chain from entry to an agent that has tool (a function tool or a
        built-in tool), as the agent names from entry to that agent. Among chains of the same
        length, the one that comes first compared name by name wins. None when no agent that a run
        from entry can reach has the tool."""
        raise NotImplementedError

    def audit(self, entry: str) -> list[tuple[str, str, str]]:
        """Guardrail gaps among the agents a run from entry can reach, as sorted
        (agent, issue, detail) tuples:

            (agent, "no output guardrail", "")       any of them may give the final answer
            (agent, "input guardrail never runs", guardrail name)
                                                     on every agent but entry: only the first
                                                     agent's input guardrails run
            (agent, "built-in tool needs its own policy", tool name)
                                                     tool guardrails only run on function tools
        """
        raise NotImplementedError
