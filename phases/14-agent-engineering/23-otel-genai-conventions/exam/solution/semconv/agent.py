"""A small in-process ReAct agent that emits GenAI spans. The model and the tools are supplied by the caller."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .tracer import Tracer


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    response_model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


Model = Callable[[list[dict[str, Any]]], Awaitable[ModelReply]]
Tool = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass
class Agent:
    """What an agent is: its name, provider, model, tools and the data source behind a tool.

    create_agent builds one and records its create_agent span. An Agent built directly
    records nothing.
    """

    name: str | None
    provider: str
    model: str
    tools: dict[str, Tool] = field(default_factory=dict)
    data_sources: dict[str, str] = field(default_factory=dict)


class TurnLimitExceeded(RuntimeError):
    pass


def agent_span_name(operation: str, agent_name: str | None) -> str:
    """'invoke_agent research_bot' for a named agent; just 'invoke_agent' for an unnamed one."""
    return f"{operation} {agent_name}" if agent_name else operation


def agent_attributes(operation: str, agent: Agent) -> dict[str, Any]:
    """Attributes of an agent span (create_agent or invoke_agent).

    The operation, the provider and the requested model; gen_ai.agent.name is set only for
    a named agent.
    """
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": operation,
        "gen_ai.provider.name": agent.provider,
        "gen_ai.request.model": agent.model,
    }
    if agent.name:
        attributes["gen_ai.agent.name"] = agent.name
    return attributes


def create_agent(
    tracer: Tracer,
    name: str | None,
    provider: str,
    model: str,
    *,
    tools: dict[str, Tool] | None = None,
    data_sources: dict[str, str] | None = None,
) -> Agent:
    """Build an agent and record its create_agent span.

    An agent is created once and then runs any number of times, on this tracer or another.
    Its create_agent span is recorded here, when the agent is built, and ends at once. Like
    any span it is a child of the current span, so an agent built outside any run gets a
    root span of its own. Runs record invoke_agent spans, never create_agent.
    """
    agent = Agent(
        name,
        provider,
        model,
        tools={} if tools is None else dict(tools),
        data_sources={} if data_sources is None else dict(data_sources),
    )
    created = tracer.start_span(
        agent_span_name("create_agent", agent.name),
        attributes=agent_attributes("create_agent", agent),
    )
    tracer.end_span(created)
    return agent


async def run_agent(
    tracer: Tracer, agent: Agent, model: Model, prompt: str, max_turns: int = 8
) -> str:
    """Run the agent in-process under one invoke_agent INTERNAL span and return its answer.

    Every model call is a chat span. The tool calls of one reply run concurrently, one
    tool_call span each, all children of the invoke_agent span. A tool that raises gets
    error.type on its span and the model sees the error as that tool's result.
    """
    span_name = agent_span_name("invoke_agent", agent.name)
    with tracer.span(span_name, attributes=agent_attributes("invoke_agent", agent)):
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        for _ in range(max_turns):
            reply = await _chat(tracer, agent, model, messages)
            if not reply.tool_calls:
                return reply.text
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [{"name": c.name, "arguments": c.arguments} for c in reply.tool_calls],
                }
            )
            results = await asyncio.gather(*(_call_tool(tracer, agent, c) for c in reply.tool_calls))
            messages.extend(
                {"role": "tool", "name": c.name, "content": r} for c, r in zip(reply.tool_calls, results)
            )
        raise TurnLimitExceeded(f"no answer after {max_turns} turns")


async def _chat(tracer: Tracer, agent: Agent, model: Model, messages: list[dict[str, Any]]) -> ModelReply:
    with tracer.span(
        "chat",
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": agent.provider,
            "gen_ai.request.model": agent.model,
        },
    ) as span:
        tracer.add_content(span, "gen_ai.input.messages", messages)
        reply = await model(list(messages))
        if reply.response_model:
            span.set_attribute("gen_ai.response.model", reply.response_model)
        span.set_attribute("gen_ai.usage.input_tokens", reply.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", reply.output_tokens)
        output = {"role": "assistant", "content": reply.text}
        if reply.tool_calls:
            output["tool_calls"] = [{"name": c.name, "arguments": c.arguments} for c in reply.tool_calls]
        tracer.add_content(span, "gen_ai.output.messages", [output])
        return reply


async def _call_tool(tracer: Tracer, agent: Agent, call: ToolCall) -> str:
    attributes = {"gen_ai.operation.name": "tool_call", "gen_ai.tool.name": call.name}
    if call.name in agent.data_sources:
        attributes["gen_ai.data_source.id"] = agent.data_sources[call.name]
    span = tracer.start_span(f"tool_call {call.name}", attributes=attributes)
    try:
        result = await agent.tools[call.name](call.arguments)
    except Exception as exc:
        tracer.end_span(span, exc)
        return f"error: {type(exc).__name__}: {exc}"
    except BaseException as exc:
        tracer.end_span(span, exc)
        raise
    tracer.add_content(span, "gen_ai.tool.result", result)
    tracer.end_span(span)
    return result


def agent_tool(tracer: Tracer, agent: Agent, model: Model) -> Tool:
    """Expose a sub-agent as a tool: {"task": ...} runs it and returns its answer."""

    async def call(arguments: dict[str, Any]) -> str:
        return await run_agent(tracer, agent, model, arguments["task"])

    return call
