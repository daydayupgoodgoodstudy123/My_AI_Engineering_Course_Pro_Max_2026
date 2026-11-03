"""Ask every provider the same question at once and report, as CSV, whether they agree."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .bridge import Bridge
from .canonical import Tool, ToolChoice

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
    raise NotImplementedError
