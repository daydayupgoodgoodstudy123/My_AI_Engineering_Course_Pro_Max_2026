"""Render a canonical conversation as one provider's request body."""
from __future__ import annotations

from .canonical import Tool, ToolChoice, Turn


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
    raise NotImplementedError
