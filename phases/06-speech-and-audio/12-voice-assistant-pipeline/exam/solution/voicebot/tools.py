"""Tools the assistant can call, and the dispatcher that runs the LLM's tool calls."""
from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

JSON_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


class ToolError(Exception):
    """A tool call that cannot run as asked. The message goes back to the LLM."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema of the arguments object
    fn: Callable[..., Any]  # a plain function or a coroutine function


def parse_arguments(raw: dict | str | None) -> dict:
    """The arguments of one tool call as a dict.

    Anthropic-style providers send the object itself. OpenAI-style providers send it as JSON text,
    which is "" for a tool without parameters. Text that is not a JSON object raises ToolError.
    """
    args = raw if raw not in (None, "") else {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError as exc:
            raise ToolError(f"arguments are not valid JSON: {exc}") from None
    if not isinstance(args, dict):
        raise ToolError("arguments must be a JSON object")
    return args


def check_arguments(parameters: dict, args: dict) -> list[str]:
    """Problems with a call's arguments, as messages for the LLM; [] means the call is valid.

    Reports missing required parameters, parameters the tool does not take, and values of the
    wrong JSON type: "300" is not an integer.
    """
    properties = parameters.get("properties", {})
    problems = [
        f"missing required parameter {name!r}"
        for name in parameters.get("required", [])
        if name not in args
    ]
    for name, value in args.items():
        if name not in properties:
            problems.append(f"unknown parameter {name!r}; expected one of: {', '.join(properties)}")
            continue
        kind = properties[name].get("type")
        if not _has_type(value, kind):
            problems.append(f"parameter {name!r} must be {kind}, got {value!r}")
    return problems


def _has_type(value: Any, kind: str | None) -> bool:
    if kind not in JSON_TYPES:
        return True
    if isinstance(value, bool):
        return kind == "boolean"
    return isinstance(value, JSON_TYPES[kind])


class ToolBox:
    """The tools offered to the LLM, and the dispatcher for its tool calls."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[dict]:
        """Tool definitions for the LLM request."""
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
        ]

    async def dispatch(self, call: dict) -> dict:
        """Run one tool call from the LLM and return the tool message that answers it.

        call is {"id": ..., "name": ..., "arguments": a dict or JSON text}. The answer is
        {"role": "tool", "tool_call_id": call["id"], "content": JSON text}, and the content is
        {"ok": true, "result": ...} or {"ok": false, "error": "..."}.

        dispatch never raises for a bad call or a failing tool. An unknown tool, bad arguments and
        any exception from the tool come back as an error result, so the LLM can correct itself and
        the turn goes on. Plain-function tools run in a worker thread: a slow tool must not block the
        event loop, which also runs the microphone, VAD and barge-in detection.
        """
        try:
            tool = self._lookup(call["name"])
            args = parse_arguments(call.get("arguments"))
        except ToolError as exc:
            return answer(call, error=str(exc))
        problems = check_arguments(tool.parameters, args)
        if problems:
            return answer(call, error="; ".join(problems))
        try:
            if inspect.iscoroutinefunction(tool.fn):
                value = await tool.fn(**args)
            else:
                value = await asyncio.to_thread(tool.fn, **args)
        except Exception as exc:
            return answer(call, error=f"{type(exc).__name__}: {exc}")
        return answer(call, result=value)

    def _lookup(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"unknown tool {name!r}; available tools: {', '.join(sorted(self._tools))}")
        return self._tools[name]


def answer(call: dict, *, result: Any = None, error: str | None = None) -> dict:
    """The tool message that answers one call."""
    content = {"ok": False, "error": error} if error is not None else {"ok": True, "result": result}
    return {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(content)}


class Timers:
    """Countdown timers. clock() returns the current time in seconds."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._timers: list[dict] = []

    def set_timer(self, seconds: int, label: str = "") -> dict:
        """Start a timer that rings `seconds` seconds from now."""
        timer = {
            "timer_id": f"t{len(self._timers) + 1}",
            "label": label,
            "fires_at": self._clock() + seconds,
        }
        self._timers.append(timer)
        return dict(timer)

    def pending(self) -> list[dict]:
        """Timers that have not rung yet, soonest first."""
        now = self._clock()
        return sorted(
            (dict(t) for t in self._timers if t["fires_at"] > now), key=lambda t: t["fires_at"]
        )


def timer_tool(timers: Timers) -> Tool:
    return Tool(
        name="set_timer",
        description="Start a countdown timer.",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "How long, in seconds."},
                "label": {"type": "string", "description": "What the timer is for."},
            },
            "required": ["seconds"],
        },
        fn=timers.set_timer,
    )


def weather_tool(fetch: Callable[[str], dict]) -> Tool:
    """get_weather on top of a blocking HTTP client: fetch(city) -> {"temp_c": ..., "summary": ...}."""

    def get_weather(city: str) -> dict:
        return {"city": city, **fetch(city)}

    return Tool(
        name="get_weather",
        description="Current weather in a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        fn=get_weather,
    )


def calendar_tool(fetch: Callable[[], Awaitable[dict]]) -> Tool:
    """next_event on top of an async calendar client."""

    async def next_event() -> dict:
        return await fetch()

    return Tool(
        name="next_event",
        description="The user's next calendar event.",
        parameters={"type": "object", "properties": {}},
        fn=next_event,
    )
