"""Agents, their tools and handoffs, and the errors a run can raise."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union

from .items import Item


class AgentsError(Exception):
    """Base class for the errors a run raises."""


class GuardrailTripwireTriggered(AgentsError):
    """A guardrail refused. guardrail is its name and reason is what it said."""

    def __init__(self, guardrail: str, reason: str) -> None:
        super().__init__(f"{guardrail}: {reason}")
        self.guardrail = guardrail
        self.reason = reason


class InputGuardrailTripwireTriggered(GuardrailTripwireTriggered):
    """An input guardrail of the first agent refused the user input."""


class OutputGuardrailTripwireTriggered(GuardrailTripwireTriggered):
    """An output guardrail of the last agent refused the final answer."""


class ToolGuardrailTripwireTriggered(GuardrailTripwireTriggered):
    """A tool guardrail refused a function tool call, so the tool did not run."""


class HandoffLimitExceeded(AgentsError):
    """The run asked for more handoffs than Runner.max_handoffs allows."""


class MaxTurnsExceeded(AgentsError):
    """The run used Runner.max_turns model calls without a final answer."""


@dataclass
class ModelRequest:
    """What one model call sees: the agent's instructions, the conversation and the tools it may call."""

    instructions: str
    conversation: list[Item]
    tools: list[str]


# A model answers with {"text": answer} or calls one tool with {"tool": name, "args": {...}}.
Model = Callable[[ModelRequest], dict]


@dataclass
class FunctionTool:
    """A tool the runner runs itself. Each of its guardrails checks a call before the tool runs:
    guardrail.check(tool_name, args) -> (ok, reason)."""

    name: str
    fn: Callable[..., Any]
    guardrails: list = field(default_factory=list)


@dataclass
class BuiltinTool:
    """A tool the model provider runs, such as a web fetch or a file reader. Its calls never reach
    the runner, so no tool guardrail sees them."""

    name: str


@dataclass
class Handoff:
    """Lets the agent that owns it hand the conversation to target. The model sees it as a tool."""

    target: Agent

    @property
    def tool_name(self) -> str:
        return f"transfer_to_{self.target.name}"


@dataclass(eq=False, repr=False)
class Agent:
    """An LLM with instructions, tools, handoffs and guardrails.

    Guardrails are objects with a name and check(text) -> (ok, reason). An agent's input guardrails
    only run when it is the first agent of a run, its output guardrails only when it gives the final
    answer.
    """

    name: str
    instructions: str
    model: Model
    tools: list[Union[FunctionTool, BuiltinTool]] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    input_guardrails: list = field(default_factory=list)
    output_guardrails: list = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Agent({self.name!r})"

    def tool_names(self) -> list[str]:
        """The tools the model sees: the agent's own, then transfer_to_<agent> for each handoff."""
        return [tool.name for tool in self.tools] + [handoff.tool_name for handoff in self.handoffs]

    def handoff_for(self, tool_name: str) -> Handoff | None:
        return next((h for h in self.handoffs if h.tool_name == tool_name), None)

    def function_tool(self, tool_name: str) -> FunctionTool:
        for tool in self.tools:
            if isinstance(tool, FunctionTool) and tool.name == tool_name:
                return tool
        raise AgentsError(f"{self.name} has no function tool {tool_name!r}")
