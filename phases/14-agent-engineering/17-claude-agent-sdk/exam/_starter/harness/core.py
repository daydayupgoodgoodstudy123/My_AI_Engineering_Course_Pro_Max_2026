"""The harness: tools, lifecycle hooks, the agent loop and subagents.

Tool calls are scripted by the caller instead of chosen by a model, and a
token is a whitespace-separated word, as in the lesson's code.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from harness.store import SessionStore, Turn


def count_tokens(text: str) -> int:
    """Whitespace word count, the lesson's stand-in for a tokenizer."""
    return len(text.split())


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., str]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)


@dataclass(frozen=True)
class Deny:
    """Returned by a PreToolUse hook to block a tool call."""

    reason: str


# PreToolUse: (session_id, tool_name, args) -> None to allow, or Deny(reason).
PreHook = Callable[[str, str, dict], Optional[Deny]]
# PostToolUse: (session_id, tool_name, result). The return value is ignored.
PostHook = Callable[[str, str, str], None]


@dataclass
class Hooks:
    pre_tool_use: list[PreHook] = field(default_factory=list)
    post_tool_use: list[PostHook] = field(default_factory=list)
    session_start: list[Callable[[str], None]] = field(default_factory=list)
    session_end: list[Callable[[str], None]] = field(default_factory=list)


@dataclass
class AgentRun:
    """One run of an agent.

    context_tokens is the size of the session's context: every turn in the
    session so far, including turns from earlier runs of the same session.
    """

    session_id: str
    context_tokens: int = 0
    tool_calls: list[tuple[str, dict, str]] = field(default_factory=list)
    output: str = ""


Script = list[tuple[str, dict]]


class Harness:
    def __init__(self, tools: ToolRegistry, hooks: Hooks, store: SessionStore,
                 clock: Callable[[], float] = time.time) -> None:
        self.tools = tools
        self.hooks = hooks
        self.store = store
        self.clock = clock
        self._sub_counter = 0

    def _context_tokens(self, session_id: str) -> int:
        return sum(count_tokens(turn.content) for turn in self.store.load(session_id))

    def _record(self, run: AgentRun, role: str, content: str) -> None:
        self.store.append(run.session_id, Turn(role, content, self.clock()))
        run.context_tokens = self._context_tokens(run.session_id)

    def _dispatch(self, session_id: str, tool_name: str, args: dict[str, Any]) -> str:
        """Run one tool call through the hooks and return its result.

        PreToolUse hooks run in registration order. A hook returns None to let
        the call through, or Deny(reason) to block it: the tool does not run,
        the remaining PreToolUse hooks are skipped, and the result is
        "denied: <reason>". An unknown tool gives "error: unknown tool 'name'",
        and a tool that raises gives "error: <ExceptionType>: <message>".
        Every PostToolUse hook sees every result: tool output, error or denial.
        """
        for hook in self.hooks.pre_tool_use:
            hook(session_id, tool_name, args)
        tool = self.tools.get(tool_name)
        if tool is None:
            result = f"error: unknown tool {tool_name!r}"
        else:
            try:
                result = tool.fn(**args)
            except Exception as exc:
                return f"error: {type(exc).__name__}: {exc}"
        for hook in self.hooks.post_tool_use:
            hook(session_id, tool_name, result)
        return result

    def run_agent(self, session_id: str, prompt: str, tool_calls: Script,
                  parent_session: Optional[str] = None) -> AgentRun:
        """Run the scripted tool calls in session_id and record every turn.

        The prompt is a "user" turn, each call a "tool" turn
        "<tool_name>: <result>", and the closing output an "assistant" turn.
        """
        for hook in self.hooks.session_start:
            hook(session_id)
        if parent_session is not None:
            self.store.link_sub(parent_session, session_id)

        run = AgentRun(session_id=session_id)
        self._record(run, "user", prompt)
        for tool_name, args in tool_calls:
            result = self._dispatch(session_id, tool_name, args)
            run.tool_calls.append((tool_name, args, result))
            self._record(run, "tool", f"{tool_name}: {result}")

        run.output = f"processed {len(tool_calls)} tools; session={session_id}"
        self._record(run, "assistant", run.output)

        for hook in self.hooks.session_end:
            hook(session_id)
        return run

    def spawn_subagents(self, parent: AgentRun, tasks: list[tuple[str, Script]]) -> list[AgentRun]:
        """Run each task as a subagent of parent, one after another.

        A subagent runs in its own session, "<parent>.subNN", numbered across
        the harness's lifetime, and keeps its own context. Only its output
        returns to the orchestrator, as one "subagent" turn in the parent's
        session, so parent.context_tokens grows by the outputs alone.
        """
        runs: list[AgentRun] = []
        for prompt, tool_calls in tasks:
            self._sub_counter += 1
            sub_session = f"{parent.session_id}.sub{self._sub_counter:02d}"
            run = self.run_agent(sub_session, prompt, tool_calls, parent_session=parent.session_id)
            self._record(parent, "subagent", self.store.load(sub_session))
            runs.append(run)
        return runs
