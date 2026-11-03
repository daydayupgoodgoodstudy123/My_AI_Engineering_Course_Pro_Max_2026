"""Ask every provider the same question at once and report, as CSV, whether they agree."""
from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator

from .bridge import Bridge
from .canonical import Call, Tool, ToolChoice, json_text

HEADER = ("provider", "call_id", "name", "arguments_json", "status")


async def equivalence_probe(
    bridge: Bridge,
    tools: list[Tool],
    prompt: str,
    choice: ToolChoice,
    timeout_s: float = 10.0,
) -> AsyncIterator[str]:
    """Send the same prompt to every provider of the bridge at once, and stream a CSV report.

    Each yielded string is one CSV record. The first is the header. Then comes one record per
    provider, in the order the replies arrive:
      ok       the reply holds exactly one call: its id, name and arguments as JSON;
      error    the provider failed, the arguments are not a JSON object, or the reply holds no call
               or several;
      timeout  no reply within timeout_s of asking. The request is cancelled.
    error and timeout records leave call_id, name and arguments_json empty. A slow provider must not
    hold up the others.

    The last record is the summary: provider "equivalence", every other field empty but status.
    "different" when two providers called different tools or passed different arguments (compared
    as parsed objects, not as text), "same" when every provider answered and all agree, and
    "incomplete" otherwise.
    """
    yield _record(HEADER)
    providers = list(bridge.providers)

    async def answer(provider: str) -> tuple[str, Call | None, str]:
        try:
            calls = await asyncio.wait_for(bridge.ask(provider, tools, prompt, choice), timeout_s)
        except asyncio.TimeoutError:
            return provider, None, "timeout"
        except Exception:
            return provider, None, "error"
        if len(calls) != 1:
            return provider, None, "error"
        return provider, calls[0], "ok"

    answers: list[Call] = []
    for arrival in asyncio.as_completed([answer(p) for p in providers]):
        provider, call, status = await arrival
        if call is None:
            yield _record((provider, "", "", "", status))
        else:
            answers.append(call)
            yield _record((provider, call.id, call.name, json_text(call.args), status))
    yield _record(("equivalence", "", "", "", _verdict(answers, len(providers))))


def _verdict(answers: list[Call], asked: int) -> str:
    # ids differ by design (call_..., toolu_..., UUIDs); only the tool and its arguments must agree
    if any((c.name, c.args) != (answers[0].name, answers[0].args) for c in answers[1:]):
        return "different"
    return "same" if len(answers) == asked else "incomplete"


def _record(fields: tuple) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(fields)
    return buffer.getvalue()
