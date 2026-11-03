"""Render a canonical conversation as one provider's request body."""
from __future__ import annotations

from .canonical import AssistantTurn, Call, Tool, ToolChoice, ToolResult, Turn, UserTurn, json_text
from .limits import LIMITS, LimitError, check_depth
from .translate import tool_fields


def render(provider: str, tools: list[Tool], conversation: list[Turn], choice: ToolChoice) -> dict:
    """The request body that continues this conversation on one provider.

    The body is tool_fields(provider, tools, choice) plus the conversation, as "messages" for OpenAI
    and Anthropic and as "contents" for Gemini:

    - A user turn is {"role": "user", "content": text}; Gemini: {"role": "user", "parts": [{"text": text}]}.
    - An assistant turn is {"role": "assistant", "content": text, "tool_calls": [...]} for OpenAI, with
      no tool_calls key when there are no calls. Anthropic: {"role": "assistant", "content": [blocks]},
      a {"type": "text"} block if there is text, then a {"type": "tool_use", "id", "name", "input"} block
      per call. Gemini: {"role": "model", "parts": [...]}, a {"text"} part if there is text, then a
      {"functionCall": {"id", "name", "args"}} part per call.
    - Tool results: OpenAI takes one {"role": "tool", "tool_call_id", "content": json_text(content)}
      message per result. Anthropic and Gemini take the results that answer one assistant turn
      together, in one user message: {"type": "tool_result", "tool_use_id", "content":
      json_text(content)} blocks (with "is_error": True on a failed result), or {"functionResponse":
      {"id", "name", "response": content}} parts.

    OpenAI's arguments are JSON text: a call that came from OpenAI goes back with its raw_arguments
    unchanged, any other call as json_text(args). Anthropic's input and Gemini's args are the object.

    Raises LimitError, naming the provider, when the request breaks the provider's LIMITS: more tools
    than max_tools, a schema deeper than max_depth, or an arguments text longer than
    max_argument_bytes in UTF-8.
    """
    limits = LIMITS[provider]
    if len(tools) > limits.max_tools:
        raise LimitError(f"{provider}: {len(tools)} tools in one request; the limit is {limits.max_tools}")
    check_depth(provider, tools)
    body = tool_fields(provider, tools, choice)
    if provider == "openai":
        body["messages"] = _openai_messages(conversation, limits.max_argument_bytes)
    elif provider == "anthropic":
        body["messages"] = _anthropic_messages(conversation)
    else:
        body["contents"] = _gemini_contents(conversation)
    return body


def _grouped(conversation: list[Turn]) -> list:
    """The turns, with every run of consecutive tool results gathered into one list."""
    out: list = []
    for turn in conversation:
        if isinstance(turn, ToolResult):
            if out and isinstance(out[-1], list):
                out[-1].append(turn)
            else:
                out.append([turn])
        else:
            out.append(turn)
    return out


def _openai_messages(conversation: list[Turn], max_bytes: int | None) -> list[dict]:
    messages: list[dict] = []
    for turn in conversation:
        if isinstance(turn, UserTurn):
            messages.append({"role": "user", "content": turn.text})
        elif isinstance(turn, AssistantTurn):
            message: dict = {"role": "assistant", "content": turn.text}
            if turn.calls:
                message["tool_calls"] = [_openai_call(call, max_bytes) for call in turn.calls]
            messages.append(message)
        else:
            messages.append({"role": "tool", "tool_call_id": turn.call_id, "content": json_text(turn.content)})
    return messages


def _openai_call(call: Call, max_bytes: int | None) -> dict:
    arguments = call.raw_arguments if call.raw_arguments is not None else json_text(call.args)
    size = len(arguments.encode("utf-8"))
    if max_bytes is not None and size > max_bytes:
        raise LimitError(f"openai: the arguments of call {call.id} are {size} bytes; the limit is {max_bytes}")
    return {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": arguments}}


def _anthropic_messages(conversation: list[Turn]) -> list[dict]:
    messages: list[dict] = []
    for item in _grouped(conversation):
        if isinstance(item, list):
            blocks = []
            for result in item:
                block = {"type": "tool_result", "tool_use_id": result.call_id, "content": json_text(result.content)}
                if result.is_error:
                    block["is_error"] = True
                blocks.append(block)
            messages.append({"role": "user", "content": blocks})
        elif isinstance(item, UserTurn):
            messages.append({"role": "user", "content": item.text})
        else:
            content = [{"type": "text", "text": item.text}] if item.text else []
            content += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.args} for c in item.calls]
            messages.append({"role": "assistant", "content": content})
    return messages


def _gemini_contents(conversation: list[Turn]) -> list[dict]:
    contents: list[dict] = []
    for item in _grouped(conversation):
        if isinstance(item, list):
            parts = [{"functionResponse": {"id": r.call_id, "name": r.name, "response": r.content}} for r in item]
            contents.append({"role": "user", "parts": parts})
        elif isinstance(item, UserTurn):
            contents.append({"role": "user", "parts": [{"text": item.text}]})
        else:
            parts = [{"text": item.text}] if item.text else []
            parts += [{"functionCall": {"id": c.id, "name": c.name, "args": c.args}} for c in item.calls]
            contents.append({"role": "model", "parts": parts})
    return contents
