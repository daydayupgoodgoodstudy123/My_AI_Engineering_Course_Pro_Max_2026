"""Prompt-Validator-Executor: a cheap check runs on every tool call before the call runs."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .content import Content, looks_like_directive

REFUSAL = "that action was refused; try a different approach."


@dataclass(frozen=True)
class ToolCall:
    """A tool call the main model wants to make, and the user intent it claims to serve."""

    name: str
    args: dict[str, Any]
    intent: str


@dataclass(frozen=True)
class Verdict:
    action: str  # "allow", "refuse" or "confirm"
    reason: str


@dataclass
class Validator:
    allowed_tools: tuple[str, ...]
    sensitive_tools: tuple[str, ...] = ()

    def assess(self, call: ToolCall, history: list[Content]) -> Verdict:
        """Decide one candidate call against the history so far.

        Refuse a tool outside allowed_tools, a string argument that looks like a directive, and
        any call while a tainted content in the history looks like one. A call that passes all
        three and goes to a sensitive tool needs a human: "confirm". Everything else is "allow".
        """
        if call.name not in self.allowed_tools:
            return Verdict("refuse", f"tool {call.name!r} not in allowlist")
        for key, value in call.args.items():
            if not isinstance(value, str):
                continue
            hit = looks_like_directive(value)
            if hit:
                return Verdict("refuse", f"arg {key!r} contains injection marker {hit!r}")
        for content in history:
            if not content.tainted:
                continue
            hit = looks_like_directive(content.text)
            if hit:
                return Verdict("refuse", f"{content.source} content contains injection marker {hit!r}")
        if call.name in self.sensitive_tools:
            return Verdict("confirm", f"{call.name!r} is a sensitive tool")
        return Verdict("allow", "ok")


class Executor:
    """Runs a tool call. It trusts that the call was validated."""

    def __init__(self, tools: dict[str, Callable[..., str]]) -> None:
        self.tools = dict(tools)

    def run(self, call: ToolCall) -> str:
        fn = self.tools.get(call.name)
        if fn is None:
            return f"error: no tool {call.name!r}"
        return fn(**call.args)


class Session:
    """One agent session. Each step is validated, then executed, and its observation joins the history.

    The model sees the tool's output, or REFUSAL and nothing else when the call is refused; the
    reason goes to audit, which the model never reads. A "confirm" verdict asks confirm(call),
    and the call runs only when the human says True.
    """

    def __init__(
        self,
        validator: Validator,
        executor: Executor,
        confirm: Callable[[ToolCall], bool],
        history: list[Content] | None = None,
    ) -> None:
        self.validator = validator
        self.executor = executor
        self.confirm = confirm
        self.history: list[Content] = list(history or [])
        self.audit: list[tuple[ToolCall, Verdict]] = []

    def step(self, call: ToolCall) -> str:
        """Validate and maybe run one call; return the observation the model gets."""
        verdict = self.validator.assess(call, self.history)
        if verdict.action == "confirm":
            if self.confirm(call):
                verdict = Verdict("allow", f"confirmed: {verdict.reason}")
            else:
                verdict = Verdict("refuse", f"declined: {verdict.reason}")
        self.audit.append((call, verdict))
        if verdict.action == "allow":
            observation = self.executor.run(call)
        else:
            observation = REFUSAL
        self.history.append(Content(observation, "tool_output"))
        return observation
