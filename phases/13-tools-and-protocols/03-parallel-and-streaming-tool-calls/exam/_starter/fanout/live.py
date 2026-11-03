"""Stream tool results while the model is still writing the turn.

The stream carries the events of fanout/stream.py and two more:

    {"type": "call_cancel", "index": 1}             the model abandoned call 1 mid-stream
    {"type": "finish", "finish_reason": "length"}   the turn is over; "length" means the
                                                    model ran into its output limit

A call runs the moment its call_stop arrives, and its line goes out as soon as it is known.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from .host import Executors


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
    raise NotImplementedError
