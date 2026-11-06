"""Stream a draft to a client through an output guardrail, as server-sent events."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable


class OutputGuardrailTripwireTriggered(Exception):
    """Raised by a guardrail to reject output (the exception name the OpenAI Agents SDK uses)."""


# A guardrail looks at one line of output and raises OutputGuardrailTripwireTriggered to reject it.
Guardrail = Callable[[str], None]


async def guard_stream(tokens: AsyncIterator[str], guardrail: Guardrail) -> AsyncIterator[str]:
    r"""Relay a model's token stream as SSE, holding each line back until the guardrail passes it.

    A line is the text up to and including "\n"; the last line may end without one when the
    stream ends. As soon as a line is complete the guardrail checks it, once, without its line
    break ("\n" or "\r\n"). A line that passes is sent at once as a delta event whose data is
    {"text": <the line, line break included>}. A guardrail that raises
    OutputGuardrailTripwireTriggered rejects the line: send a tripwire event with data
    {"line": <1-based line number>, "reason": <the exception's message>}, then stop: pull no
    more tokens, close the token stream, send nothing else. A stream that ends without a tripwire
    finishes with a done event, data {"lines": <lines sent>}.

    Each event is one frame: "event: <name>\ndata: <JSON>\n\n". The token stream is closed
    however the relay ends. Other exceptions from the guardrail propagate.
    """
    buffer = ""
    sent = 0
    try:
        async for token in tokens:
            buffer += token
            while "\n" in buffer:
                end = buffer.index("\n") + 1
                line, buffer = buffer[:end], buffer[end:]
                reason = _check(guardrail, line)
                if reason is not None:
                    yield _frame("tripwire", {"line": sent + 1, "reason": reason})
                    return
                sent += 1
                yield _frame("delta", {"text": line})
        if buffer:
            reason = _check(guardrail, buffer)
            if reason is not None:
                yield _frame("tripwire", {"line": sent + 1, "reason": reason})
                return
            sent += 1
            yield _frame("delta", {"text": buffer})
        yield _frame("done", {"lines": sent})
    finally:
        aclose = getattr(tokens, "aclose", None)
        if aclose is not None:
            await aclose()


def _check(guardrail: Guardrail, line: str) -> str | None:
    """None when the guardrail passes the line, else the tripwire's reason."""
    if line.endswith("\r\n"):
        text = line[:-2]
    elif line.endswith("\n"):
        text = line[:-1]
    else:
        text = line
    try:
        guardrail(text)
    except OutputGuardrailTripwireTriggered as exc:
        return str(exc)
    return None


def _frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
