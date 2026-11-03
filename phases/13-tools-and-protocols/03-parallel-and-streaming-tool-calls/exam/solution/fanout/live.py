"""Stream tool results while the model is still writing the turn.

The stream carries the events of fanout/stream.py and two more:

    {"type": "call_cancel", "index": 1}             the model abandoned call 1 mid-stream
    {"type": "finish", "finish_reason": "length"}   the turn is over; "length" means the
                                                    model ran into its output limit

A call runs the moment its call_stop arrives, and its line goes out as soon as it is known.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .calls import describe
from .host import Executors
from .stream import CallBuffer, StreamAccumulator


async def stream_results(events: AsyncIterator[dict], executors: Executors) -> AsyncIterator[str]:
    """Run each call at its call_stop and stream one NDJSON line per call.

    Lines go out in the order they become known, while the stream is still being read:

      {"tool_call_id": ..., "name": ..., "status": "ok", "content": <what the executor returned>}
      {"tool_call_id": ..., "name": ..., "status": "error", "error": describe(exception)}
      {"tool_call_id": ..., "name": ..., "status": "cancelled"}    when its call_cancel arrives
      {"tool_call_id": ..., "name": ..., "status": "incomplete"}   at finish, in index order, for
                                                                   every call without a call_stop
    A cancelled or incomplete call never runs, and a failing executor affects no other call.
    The stream of lines ends once every call that started has answered.
    """
    acc = StreamAccumulator()
    lines: asyncio.Queue[dict | None] = asyncio.Queue()
    running: list[asyncio.Task] = []

    async def run(buf: CallBuffer) -> None:
        line = _line(buf, "ok")
        try:
            call = buf.to_call()
            line["content"] = await executors[call.name](**call.arguments)
        except Exception as error:
            line = _line(buf, "error")
            line["error"] = describe(error)
        lines.put_nowait(line)

    async def read() -> None:
        try:
            async for event in events:
                if event["type"] == "call_cancel":
                    lines.put_nowait(_line(acc.buffers.pop(event["index"]), "cancelled"))
                elif event["type"] == "finish":
                    break
                else:
                    for buf in acc.on_event(event):
                        running.append(asyncio.create_task(run(buf)))
            for buf in sorted(acc.buffers.values(), key=lambda b: b.index):
                if not buf.done:
                    lines.put_nowait(_line(buf, "incomplete"))
            await asyncio.gather(*running)
        finally:
            lines.put_nowait(None)

    reader = asyncio.create_task(read())
    try:
        while (line := await lines.get()) is not None:
            yield json.dumps(line) + "\n"
        await reader
    finally:
        reader.cancel()
        for task in running:
            task.cancel()


def _line(buf: CallBuffer, status: str) -> dict:
    return {"tool_call_id": buf.id, "name": buf.name, "status": status}
