"""The GenAI semantic conventions this service holds its spans to, and the content they may not carry."""
from __future__ import annotations

from collections.abc import Iterable

from .tracer import Span

# Required attributes per gen_ai.operation.name, in the order problems are reported.
REQUIRED = {
    "chat": (
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.response.id",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
    ),
    "execute_tool": ("gen_ai.tool.name", "gen_ai.tool.call.id"),
    "invoke_agent": ("gen_ai.agent.name", "gen_ai.agent.id"),
}

# Span kinds allowed per operation. A model provider is another process. A tool runs in the agent
# (INTERNAL) or behind an MCP server (CLIENT).
ALLOWED_KINDS = {
    "chat": ("CLIENT",),
    "execute_tool": ("INTERNAL", "CLIENT"),
    "invoke_agent": ("INTERNAL",),
}

CONTENT_EVENTS = ("gen_ai.content.prompt", "gen_ai.content.completion", "gen_ai.content.tool_call")


def check(spans: Iterable[Span]) -> list[tuple[str, str]]:
    """(span id, problem) for every way a GenAI span breaks the rules above, spans in the order given.

    A span without gen_ai.operation.name is not a GenAI span and is not checked. For the others, a
    span's problems come in this order:

        "unknown operation <op>"            op has no entry in REQUIRED; nothing else is checked
        "kind <kind> not allowed for <op>"  the span kind is not in ALLOWED_KINDS[op]
        "missing <attribute>"               each attribute of REQUIRED[op] that is absent or an empty
                                            string, in REQUIRED order (0 is a value, not a gap)

    The model that served a call (gen_ai.response.model) may differ from the one requested; that is
    not a problem.
    """
    raise NotImplementedError


def scrub(spans: Iterable[Span], capture_content: bool) -> list[Span]:
    """The spans as they may leave the process.

    With content capture off, the content events (CONTENT_EVENTS) are dropped and every other event
    stays, in order. With it on, the spans come back as they are. The spans passed in are not changed.
    """
    raise NotImplementedError
