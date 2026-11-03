"""The four-step loop as a live trace, for a terminal or a log viewer."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from .loop import MAX_TURNS
from .tools import Registry

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
    raise NotImplementedError
