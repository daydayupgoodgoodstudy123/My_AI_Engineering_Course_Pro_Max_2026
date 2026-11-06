"""The handoff graph of an app: which agents a run can reach, and where its guardrails do not reach."""
from __future__ import annotations

from .agents import Agent, BuiltinTool


class HandoffGraph:
    """An edge from every agent to each of its handoff targets.

    agents are the agents the app defines; their handoff targets belong to the graph too. Two
    different agents with the same name raise ValueError, since the model could not tell their
    transfer_to_<name> tools apart. Unknown agent names raise KeyError.
    """

    def __init__(self, agents: list[Agent]) -> None:
        self._agents: dict[str, Agent] = {}
        pending = list(agents)
        while pending:
            agent = pending.pop()
            known = self._agents.get(agent.name)
            if known is not None:
                if known is not agent:
                    raise ValueError(f"two different agents are named {agent.name!r}")
                continue
            self._agents[agent.name] = agent
            pending.extend(handoff.target for handoff in agent.handoffs)

    def reachable(self, entry: str) -> list[str]:
        """The names of the agents a run that starts at entry can reach, entry included, sorted."""
        seen = {self._agent(entry).name}
        pending = [entry]
        while pending:
            for handoff in self._agents[pending.pop()].handoffs:
                if handoff.target.name not in seen:
                    seen.add(handoff.target.name)
                    pending.append(handoff.target.name)
        return sorted(seen)

    def path_to_tool(self, entry: str, tool: str) -> list[str] | None:
        """The shortest handoff chain from entry to an agent that has tool (a function tool or a
        built-in tool), as the agent names from entry to that agent. Among chains of the same
        length, the one that comes first compared name by name wins. None when no agent that a run
        from entry can reach has the tool."""
        best = {self._agent(entry).name: [entry]}
        frontier = [entry]
        while frontier:
            hits = [best[name] for name in frontier if any(t.name == tool for t in self._agents[name].tools)]
            if hits:
                return min(hits)
            following: dict[str, list[str]] = {}
            for name in frontier:
                for handoff in self._agents[name].handoffs:
                    target = handoff.target.name
                    if target in best:
                        continue
                    chain = best[name] + [target]
                    if target not in following or chain < following[target]:
                        following[target] = chain
            best.update(following)
            frontier = list(following)
        return None

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
        findings = []
        for name in self.reachable(entry):
            agent = self._agents[name]
            if not agent.output_guardrails:
                findings.append((name, "no output guardrail", ""))
            if name != entry:
                findings.extend((name, "input guardrail never runs", g.name) for g in agent.input_guardrails)
            findings.extend(
                (name, "built-in tool needs its own policy", t.name) for t in agent.tools if isinstance(t, BuiltinTool)
            )
        return sorted(findings)

    def _agent(self, name: str) -> Agent:
        try:
            return self._agents[name]
        except KeyError:
            raise KeyError(f"no agent named {name!r}") from None
