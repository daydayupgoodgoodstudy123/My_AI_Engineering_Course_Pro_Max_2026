"""Run a turn's tool calls at the same time and answer each one under its own id."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .calllog import CallLog, call_from, done
from .calls import ToolCall, tool_message
from .stream import StreamAccumulator

# tool name -> async executor, called with the call's parsed arguments as keyword arguments
Executors = dict[str, Callable[..., Awaitable[Any]]]


async def answer(call: ToolCall, executors: Executors) -> dict:
    """Run one call and return the tool message that answers it.

    An executor that raises is answered with an error message (tool_message's error=...).
    One failing tool never takes the rest of the turn down.
    """
    try:
        result = await executors[call.name](**call.arguments)
    except Exception as error:
        return tool_message(call.id, error=error)
    return tool_message(call.id, result)


async def run_parallel(calls: list[ToolCall], executors: Executors) -> list[dict]:
    """Answer every call of a turn at the same time.

    The turn takes as long as its slowest call, not the sum of all of them. Returns one tool
    message per call, in completion order: the model matches results by tool_call_id.
    """
    tasks = [asyncio.create_task(answer(call, executors)) for call in calls]
    return [await task for task in asyncio.as_completed(tasks)]


async def replay_and_execute(events: AsyncIterator[dict], executors: Executors) -> list[dict]:
    """Read a streamed turn and run each call as soon as its arguments are complete.

    A call starts when its call_stop arrives, while the rest of the stream is still being
    read, and nothing is parsed or run before that. Returns one tool message per call, in
    completion order. Failures are answered as in answer().
    """
    acc = StreamAccumulator()
    tasks: list[asyncio.Task] = []
    async for event in events:
        for buf in acc.on_event(event):
            tasks.append(asyncio.create_task(answer(buf.to_call(), executors)))
    return [await task for task in asyncio.as_completed(tasks)]


async def resume(log: CallLog, executors: Executors) -> list[dict]:
    """Run again the calls that were in flight when the host stopped.

    Only calls with a started record and no done record run, once each. Every answer is
    logged as a done record whose payload is the message's content. Returns the messages.
    """
    calls = [call_from(record) for record in log.in_flight()]
    messages = await run_parallel(calls, executors)
    for message in messages:
        log.append(done(message["tool_call_id"], message["content"]))
    return messages
