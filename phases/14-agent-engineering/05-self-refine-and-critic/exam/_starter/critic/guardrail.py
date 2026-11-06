"""Stream a draft to a client through an output guardrail, as server-sent events."""
from __future__ import annotations

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
    raise NotImplementedError
