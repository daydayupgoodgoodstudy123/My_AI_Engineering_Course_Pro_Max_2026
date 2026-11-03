"""The lesson's agent, with stand-ins for the model and the MCP server.

invoke_agent -> chat -> execute_tool -> mcp.call ... -> chat, all in one trace. The stand-ins sleep on
a shared clock instead of doing real work, so with a FakeClock every timestamp is predictable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .propagate import McpRequest, extract
from .tracer import Span, SpanContext, Tracer

MS = 1_000_000
LLM_NS = 50 * MS  # one model call
TOOL_NS = 30 * MS  # the agent's own work around a tool call
MCP_NS = 40 * MS  # the MCP server answering tools/call


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Reply:
    """One model response: either tool calls to make, or the final text."""

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "gpt-4o-2024-08-06"
    response_id: str = "resp_0"


class ScriptedLLM:
    """A stand-in model client that returns scripted replies, one per call."""

    provider = "openai"

    def __init__(self, clock, replies: list[Reply], latency_ns: int = LLM_NS) -> None:
        self.clock = clock
        self._replies = list(replies)
        self.latency_ns = latency_ns

    def complete(self, messages: list[dict]) -> Reply:
        self.clock.sleep(self.latency_ns)
        if not self._replies:
            raise RuntimeError("the script has no more replies")
        return self._replies.pop(0)


class WeatherServer:
    """A stand-in MCP server, another process in real life, with one tool: get_weather.

    With a tracer of its own it records a SERVER span for every tools/call, continuing the caller's
    trace when the request carries a traceparent. The first call waits cold_start_ns before the
    server can pick it up.
    """

    name = "weather"
    TEMPS = {"Bengaluru": 28, "Tokyo": 12, "Zurich": 4}

    def __init__(
        self,
        clock,
        *,
        transport: str = "stdio",
        tracer: Tracer | None = None,
        cold_start_ns: int = 0,
        call_ns: int = MCP_NS,
    ) -> None:
        self.clock = clock
        self.transport = transport
        self.tracer = tracer
        self.cold_start_ns = cold_start_ns
        self.call_ns = call_ns
        self.requests: list[McpRequest] = []

    def handle(self, request: McpRequest) -> dict:
        self.requests.append(request)
        if self.cold_start_ns:
            self.clock.sleep(self.cold_start_ns)
            self.cold_start_ns = 0
        span = None
        if self.tracer is not None:
            span = self.tracer.start_span(
                "mcp.server tools/call",
                "SERVER",
                parent=extract(request),
                attrs={"mcp.server": self.name, "mcp.transport": request.transport},
            )
        try:
            self.clock.sleep(self.call_ns)
            city = request.message["params"]["arguments"]["city"]
            text = f"{city}: {self.TEMPS.get(city, 20)} C"
            return {
                "jsonrpc": "2.0",
                "id": request.message["id"],
                "result": {"content": [{"type": "text", "text": text}]},
            }
        finally:
            if span is not None:
                self.tracer.finish(span)


def fake_llm_call(tracer: Tracer, parent: Span, llm: ScriptedLLM, model: str, messages: list[dict]) -> Reply:
    """One chat call. The model provider is another process, so the span is CLIENT."""
    span = tracer.start_span(
        "llm.chat",
        "CLIENT",
        parent=parent,
        attrs={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": llm.provider,
            "gen_ai.request.model": model,
        },
    )
    try:
        if tracer.capture_content:
            tracer.add_event(span, "gen_ai.content.prompt", {"content": json.dumps(messages)})
        reply = llm.complete(messages)
        span.attrs.update(
            {
                "gen_ai.response.id": reply.response_id,
                "gen_ai.response.model": reply.model,
                "gen_ai.usage.input_tokens": reply.input_tokens,
                "gen_ai.usage.output_tokens": reply.output_tokens,
            }
        )
        if tracer.capture_content:
            tracer.add_event(span, "gen_ai.content.completion", {"content": _completion(reply)})
        return reply
    finally:
        tracer.finish(span)


def fake_tool_execute(tracer: Tracer, parent: Span, server: WeatherServer, call: ToolCall) -> dict:
    """One tool call, run by the agent itself (INTERNAL); the tool lives on the MCP server."""
    span = tracer.start_span(
        "tool.execute",
        "INTERNAL",
        parent=parent,
        attrs={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": call.name,
            "gen_ai.tool.call.id": call.id,
        },
    )
    try:
        if tracer.capture_content:
            tracer.add_event(
                span,
                "gen_ai.content.tool_call",
                {"content": json.dumps({"name": call.name, "arguments": call.arguments})},
            )
        tracer.clock.sleep(TOOL_NS)
        return fake_mcp_call(tracer, span, server, call)
    finally:
        tracer.finish(span)


def fake_mcp_call(tracer: Tracer, parent: Span, server: WeatherServer, call: ToolCall) -> dict:
    """Send tools/call to the MCP server and return the result.

    The server is another process, so the span is CLIENT.
    """
    span = tracer.start_span(
        "mcp.call",
        "INTERNAL",
        parent=parent,
        attrs={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": call.name,
            "gen_ai.tool.call.id": call.id,
            "mcp.server": server.name,
            "mcp.transport": server.transport,
        },
    )
    try:
        request = McpRequest(
            server.transport,
            {
                "jsonrpc": "2.0",
                "id": call.id,
                "method": "tools/call",
                "params": {"name": call.name, "arguments": call.arguments},
            },
        )
        return server.handle(request)["result"]
    finally:
        tracer.finish(span)


def run_agent(
    tracer: Tracer,
    llm: ScriptedLLM,
    server: WeatherServer,
    prompt: str,
    *,
    parent: SpanContext | None = None,
    model: str = "gpt-4o",
    agent_name: str = "research-agent",
    agent_id: str = "agent_42",
    max_turns: int = 8,
) -> str:
    """Run the agent loop under one invoke_agent span and return the final answer.

    parent is the caller's SpanContext when another agent invoked this one from another process.
    """
    root = tracer.start_span(
        "agent.invoke_agent",
        "INTERNAL",
        parent=parent,
        attrs={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_name,
            "gen_ai.agent.id": agent_id,
        },
    )
    try:
        messages: list[dict] = [{"role": "user", "content": prompt}]
        for _ in range(max_turns):
            reply = fake_llm_call(tracer, root, llm, model, messages)
            if reply.text is not None:
                return reply.text
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": c.id, "name": c.name, "arguments": c.arguments} for c in reply.tool_calls
                    ],
                }
            )
            for call in reply.tool_calls:
                result = fake_tool_execute(tracer, root, server, call)
                messages.append({"role": "tool", "id": call.id, "content": result})
        raise RuntimeError(f"no final answer after {max_turns} turns")
    finally:
        tracer.finish(root)


def _completion(reply: Reply) -> str:
    if reply.text is not None:
        return reply.text
    return json.dumps([{"id": c.id, "name": c.name, "arguments": c.arguments} for c in reply.tool_calls])
