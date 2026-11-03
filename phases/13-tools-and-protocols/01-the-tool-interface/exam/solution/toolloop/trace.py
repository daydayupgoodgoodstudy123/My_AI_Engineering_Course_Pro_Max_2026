"""The four-step loop as a live trace, for a terminal or a log viewer."""
from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .loop import MAX_TURNS, rejection, tool_message
from .tools import Registry, Tool

# await model(history, tools) returns a decision, as in run_loop.
AsyncModel = Callable[[list[dict], list[dict]], Awaitable[dict]]


async def trace_loop(
    model: AsyncModel, registry: Registry, user_message: str, *, max_turns: int = MAX_TURNS
) -> AsyncIterator[str]:
    """Run one user request like run_loop, yielding a trace line for each step as it happens.

    The model is async. An executor may be a plain function or a coroutine function.
    The history, the tool messages and the circuit breaker are the same as run_loop's.

    Lines, each ending in "\\n":

        USER : <user message>
        TURN <n> DECIDE : call <tool name> id=<call id>
                   args = <arguments>
        TURN <n> EXECUTE: <tool name> -> <result>
                   ERROR : <error result>      (instead of EXECUTE, for a call that must not run)
        TURN <n> OBSERVE: history length = <messages in the history>
        TURN <n> DECIDE : final answer
        MODEL : <answer>
        LOOP TERMINATED : hit MAX_TURNS circuit breaker

    The user message, arguments, results and answer are written as compact JSON (no
    space after "," or ":"), with non-ASCII characters as they are. There are no
    timings: the same request always gives the same trace.
    """
    yield f"USER : {_json(user_message)}\n"
    tools = registry.describe()
    history: list[dict] = [{"role": "user", "content": user_message}]
    for turn in range(1, max_turns + 1):
        decision = await model(history, tools)
        if "content" in decision:
            history.append({"role": "assistant", "content": decision["content"]})
            yield f"TURN {turn} DECIDE : final answer\n"
            yield f"MODEL : {_json(decision['content'])}\n"
            return
        history.append({"role": "assistant", "tool_calls": decision["tool_calls"]})
        for call in decision["tool_calls"]:
            yield f"TURN {turn} DECIDE : call {call['name']} id={call['id']}\n"
            yield f"           args = {_json(call['arguments'])}\n"
            result = rejection(registry, call)
            if result is not None:
                yield f"           ERROR : {_json(result)}\n"
            else:
                result = await _execute(registry.get(call["name"]), call["arguments"])
                yield f"TURN {turn} EXECUTE: {call['name']} -> {_json(result)}\n"
            history.append(tool_message(call, result))
        yield f"TURN {turn} OBSERVE: history length = {len(history)}\n"
    yield "LOOP TERMINATED : hit MAX_TURNS circuit breaker\n"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


async def _execute(tool: Tool, arguments: dict) -> Any:
    try:
        result = tool.executor(arguments)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return result
