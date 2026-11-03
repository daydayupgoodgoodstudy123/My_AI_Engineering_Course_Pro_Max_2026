"""The four-step loop: describe, decide, execute, observe."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .schema import validate
from .tools import Registry, Tool

MAX_TURNS = 5

# model(history, tools) returns {"content": answer} or {"tool_calls": [{"id", "name", "arguments"}, ...]}
Model = Callable[[list[dict], list[dict]], dict]


@dataclass
class Outcome:
    answer: str | None  # the final answer; None when the circuit breaker stopped the loop
    stop: str  # "final" or "max_turns"
    turns: int  # model turns used
    history: list[dict]


def rejection(registry: Registry, call: dict) -> dict | None:
    """The error result for a call that must not run, or None if it may run.

    A call must not run if it names an unknown tool or its arguments break the
    tool's input schema.
    """
    if call["name"] not in registry:
        return {"error": f"unknown tool {call['name']}"}
    errors = validate(registry.get(call["name"]).input_schema, call["arguments"])
    if errors:
        return {"error": "invalid arguments", "details": errors}
    return None


def execute(tool: Tool, arguments: dict) -> Any:
    """Step three: run the executor. An exception becomes an error result, so one
    failing tool cannot take the host down."""
    try:
        return tool.executor(arguments)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def tool_message(call: dict, result: Any) -> dict:
    """Step four, observe: the result as a tool message carrying the call's id."""
    return {"role": "tool", "id": call["id"], "name": call["name"], "content": result}


def run_loop(model: Model, registry: Registry, user_message: str, *, max_turns: int = MAX_TURNS) -> Outcome:
    """Run one user request, from the user's message to the final answer.

    Each turn the model sees the history and the tool declarations, and either
    answers, which ends the request, or asks for tool calls. Every call is answered
    with a tool message: its result, or the error that kept it from running. The
    model reads them on its next turn.

    The circuit breaker allows at most max_turns model turns. Calls asked for on the
    last turn still run; then the loop stops with stop="max_turns".
    """
    tools = registry.describe()
    history: list[dict] = [{"role": "user", "content": user_message}]
    for turn in range(1, max_turns + 1):
        decision = model(history, tools)
        if "content" in decision:
            history.append({"role": "assistant", "content": decision["content"]})
            return Outcome(decision["content"], "final", turn, history)
        history.append({"role": "assistant", "tool_calls": decision["tool_calls"]})
        for call in decision["tool_calls"]:
            error = rejection(registry, call)
            result = error if error is not None else execute(registry.get(call["name"]), call["arguments"])
            history.append(tool_message(call, result))
    return Outcome(None, "max_turns", max_turns, history)
