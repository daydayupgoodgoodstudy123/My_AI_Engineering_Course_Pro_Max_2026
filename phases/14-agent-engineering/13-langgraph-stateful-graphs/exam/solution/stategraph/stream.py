"""Stream a session to a UI as server-sent events, one event per checkpoint."""
from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator

from .effects import NodeContext
from .graph import END, HUMAN, PAUSE, START, State, StateGraph, Update
from .runner import Runner


async def stream_updates(
    runner: Runner, session: str, inputs: State | None = None, patch: Update | None = None
) -> AsyncIterator[str]:
    """Run a session (inputs given) or resume it (with patch as the human edit), as SSE.

    Every checkpoint the stream writes, START, a HUMAN edit or a node, goes out as soon as
    it is written:

        id: <step>
        event: updates
        data: {"node": <node>, "update": <what the step wrote>}

    A pause sends, after its step's updates event,

        event: interrupt
        data: {"node": <node>, "step": <step>, "reason": <reason>}

    and ends the stream. Reaching END sends

        event: end
        data: {"step": <latest step>}

    Each item is one event: its lines end in "\\n", data is JSON on one line, and a blank
    line closes the event. A node may be a coroutine function, and is awaited. Steps are
    checkpointed exactly as Runner.run and Runner.resume checkpoint them; a node that raises
    leaves no checkpoint, and its error ends the stream.
    """
    graph = runner.graph
    inner = None
    if inputs is not None:
        state, step, node = runner._begin(session, graph, inputs)
        yield _event("updates", {"node": START, "update": inputs}, step)
    else:
        latest = runner.checkpointer.records(session)[-1:]
        state, step, node, inner = runner._position(session, graph, patch)
        if latest and step > latest[0].step:
            yield _event("updates", {"node": HUMAN, "update": patch}, step)
    while node != END:
        step += 1
        target = graph.nodes[node]
        if isinstance(target, StateGraph):
            update, calls = runner._subgraph(session, node, step, target, state, inner), ()
        else:
            ctx = NodeContext(runner.world)
            update = target(state, ctx)
            if inspect.isawaitable(update):
                update = await update
            calls = ctx.calls
        inner = None
        update = dict(update or {})
        reason = update.pop(PAUSE, None)
        state = runner._commit(session, graph, step, node, state, update, calls)
        yield _event("updates", {"node": node, "update": update}, step)
        if reason:
            yield _event("interrupt", {"node": node, "step": step, "reason": reason})
            return
        node = graph.next_node(node, state)
    yield _event("end", {"step": step})


def _event(kind: str, data: dict, step: int | None = None) -> str:
    head = f"id: {step}\n" if step is not None else ""
    return f"{head}event: {kind}\ndata: {json.dumps(data)}\n\n"
