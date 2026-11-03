"""The GenAI metrics, as explicit-bucket histograms aggregated from finished spans."""
from __future__ import annotations

import bisect
from collections.abc import Iterable
from dataclasses import dataclass, field

from .tracer import Span

DURATION_BOUNDS_S = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0)
TOKEN_BOUNDS = (1, 4, 16, 64, 256, 1024, 4096, 16384, 65536)


@dataclass
class Histogram:
    """An explicit-bucket histogram.

    bounds are increasing upper bounds, and counts has one more slot than bounds: counts[0] counts the
    values v <= bounds[0], counts[i] those with bounds[i-1] < v <= bounds[i], and counts[-1] those above
    bounds[-1]. A value equal to a bound belongs to the bucket that bound closes. count and sum cover
    every recorded value.
    """

    bounds: tuple[float, ...]
    counts: list[int] = field(default_factory=list)
    count: int = 0
    sum: float = 0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0] * (len(self.bounds) + 1)

    def record(self, value: float) -> None:
        self.counts[bisect.bisect_left(self.bounds, value)] += 1
        self.count += 1
        self.sum += value


def metrics(spans: Iterable[Span]) -> dict[str, dict[str, Histogram]]:
    """The lesson's three GenAI histograms, from finished spans.

    "gen_ai.client.token.usage", keyed by token type, "input" and "output": each chat span adds its
        gen_ai.usage.input_tokens to "input" and its gen_ai.usage.output_tokens to "output"
        (TOKEN_BOUNDS).
    "gen_ai.client.operation.duration", keyed by gen_ai.request.model: each chat span adds its
        duration in seconds (DURATION_BOUNDS_S).
    "gen_ai.tool.execution.duration", keyed by gen_ai.tool.name: each INTERNAL execute_tool span
        adds its duration in seconds (DURATION_BOUNDS_S). That span covers the whole tool call; the
        CLIENT span of an MCP round trip inside it is part of the same call and adds nothing.

    A chat span is one whose gen_ai.operation.name is "chat", whatever its kind. A span that lacks
    the attribute a sample needs (a token count, the model, the tool name) does not add that sample.
    Durations are (end_ns - start_ns) / 1e9.
    """
    tokens: dict[str, Histogram] = {}
    durations: dict[str, Histogram] = {}
    tools: dict[str, Histogram] = {}
    for span in spans:
        op = span.attrs.get("gen_ai.operation.name")
        seconds = (span.end_ns - span.start_ns) / 1e9
        if op == "chat":
            for token_type in ("input", "output"):
                value = span.attrs.get(f"gen_ai.usage.{token_type}_tokens")
                if value is not None:
                    tokens.setdefault(token_type, Histogram(TOKEN_BOUNDS)).record(value)
            model = span.attrs.get("gen_ai.request.model")
            if model is not None:
                durations.setdefault(model, Histogram(DURATION_BOUNDS_S)).record(seconds)
        elif op == "execute_tool" and span.kind == "INTERNAL":
            tool = span.attrs.get("gen_ai.tool.name")
            if tool is not None:
                tools.setdefault(tool, Histogram(DURATION_BOUNDS_S)).record(seconds)
    return {
        "gen_ai.client.token.usage": tokens,
        "gen_ai.client.operation.duration": durations,
        "gen_ai.tool.execution.duration": tools,
    }
