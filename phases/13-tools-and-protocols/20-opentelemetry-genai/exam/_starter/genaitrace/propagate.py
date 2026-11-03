"""W3C trace context across MCP: the traceparent header over Streamable HTTP, params._meta over stdio."""
from __future__ import annotations

from dataclasses import dataclass, field

from .tracer import Span, SpanContext


@dataclass
class McpRequest:
    """One JSON-RPC request on its way to an MCP server.

    transport is "stdio" or "http". Over stdio there is only the message. Over Streamable HTTP the
    message is the POST body and headers are the HTTP headers, names in lowercase.
    """

    transport: str
    message: dict
    headers: dict[str, str] = field(default_factory=dict)


def format_traceparent(span: Span) -> str:
    """The traceparent that makes span the parent of the receiver's work: version 00, the trace id,
    this span's id, and flags 01 (sampled)."""
    return f"00-{span.trace_id}-{span.span_id}-01"


def parse_traceparent(value: object) -> SpanContext | None:
    """The SpanContext a traceparent value carries, or None when it carries no usable one.

    A usable value is exactly "00-<trace id>-<parent id>-<flags>" and nothing more: a 32-character
    trace id and a 16-character parent id in lowercase hex, neither of them all zeros, and two
    lowercase hex characters of flags. Anything else gives None (a missing value, a value that is not
    a string, upper case, wrong lengths, another version, extra characters), so the receiver starts a
    new trace instead of failing the request.
    """
    raise NotImplementedError


def inject(request: McpRequest, span: Span) -> McpRequest:
    """A copy of request that carries span's trace context to the server.

    Over HTTP the traceparent goes in the "traceparent" header and the message is not touched. Over
    stdio, which has no headers, it goes in the message as params._meta.traceparent, next to whatever
    else _meta already holds (a request without params gets them). The request passed in is left as
    it was.
    """
    raise NotImplementedError


def extract(request: McpRequest) -> SpanContext | None:
    """The caller's SpanContext: from the traceparent header over HTTP, from params._meta.traceparent
    over stdio. None when the request carries no usable traceparent."""
    if request.transport == "http":
        return parse_traceparent(request.headers.get("traceparent"))
    params = request.message.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    return parse_traceparent(meta.get("traceparent") if isinstance(meta, dict) else None)
