"""Stream a session to a UI as server-sent events, one event per checkpoint."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .graph import State, Update
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
    raise NotImplementedError
