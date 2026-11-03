"""Edge translators: canonical tools and tool choices go out, provider replies come back as calls."""
from __future__ import annotations

import json
from typing import Any

from .canonical import Call, Tool, ToolChoice


def to_openai(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "strict": tool.strict,
        },
    }


def to_anthropic(tool: Tool) -> dict:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}


def to_gemini(tool: Tool) -> dict:
    return {
        "functionDeclarations": [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": _gemini_schema(tool.input_schema),
            }
        ]
    }


def _gemini_schema(node: Any) -> Any:
    """Rewrite a JSON Schema node in the OpenAPI 3.0 subset that Gemini reads.

    type is one upper-case name ("STRING", "OBJECT", ...). A nullable type such as
    ["string", "null"] is written as that one name plus nullable: true; a union of two real types
    has no such form and raises ValueError. additionalProperties is dropped: Gemini does not
    support it.
    """
    if isinstance(node, list):
        return [_gemini_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    out: dict = {}
    for k, v in node.items():
        if k == "additionalProperties":
            continue
        if k == "type":
            names = [v] if isinstance(v, str) else list(v)
            real = [name for name in names if name != "null"]
            if len(real) != 1:
                raise ValueError(f"Gemini cannot express the type {v!r}")
            out["type"] = real[0].upper()
            if "null" in names:
                out["nullable"] = True
        elif k == "properties":
            # property names are not keywords: a property may be called "type"
            out[k] = {name: _gemini_schema(sub) for name, sub in v.items()}
        else:
            out[k] = _gemini_schema(v)
    return out


def tool_choice_openai(tc: ToolChoice) -> Any:
    """OpenAI's tool_choice: "auto", "none", "required", or {"type": "function", "function": {"name": ...}}."""
    if tc.mode in ("auto", "none", "required"):
        return tc.mode
    if tc.mode == "force":
        return {"type": "function", "function": {"name": tc.tool_name}}
    raise ValueError(f"unknown tool_choice mode {tc.mode!r}")


def tool_choice_anthropic(tc: ToolChoice) -> dict:
    """Anthropic's tool_choice: {"type": "auto"}, {"type": "any"} (must call a tool), {"type": "none"},
    or {"type": "tool", "name": ...}."""
    if tc.mode in ("auto", "none"):
        return {"type": tc.mode}
    if tc.mode == "required":
        return {"type": "any"}
    if tc.mode == "force":
        return {"type": "tool", "name": tc.tool_name}
    raise ValueError(f"unknown tool_choice mode {tc.mode!r}")


def tool_choice_gemini(tc: ToolChoice) -> dict:
    """Gemini's tool_config: function_calling_config.mode is AUTO, NONE or ANY; forcing one tool is ANY
    limited to it by allowed_function_names."""
    modes = {"auto": "AUTO", "none": "NONE", "required": "ANY"}
    if tc.mode in modes:
        return {"function_calling_config": {"mode": modes[tc.mode]}}
    if tc.mode == "force":
        return {"function_calling_config": {"mode": "ANY", "allowed_function_names": [tc.tool_name]}}
    raise ValueError(f"unknown tool_choice mode {tc.mode!r}")


def tool_fields(provider: str, tools: list[Tool], choice: ToolChoice) -> dict:
    """The tool declarations and the tool choice of a request, under the provider's field names.

    Gemini takes every declaration in one tool object, and its choice as tool_config.
    """
    if provider == "openai":
        return {"tools": [to_openai(t) for t in tools], "tool_choice": tool_choice_openai(choice)}
    if provider == "anthropic":
        return {"tools": [to_anthropic(t) for t in tools], "tool_choice": tool_choice_anthropic(choice)}
    if provider == "gemini":
        declarations = [d for t in tools for d in to_gemini(t)["functionDeclarations"]]
        return {"tools": [{"functionDeclarations": declarations}], "tool_config": tool_choice_gemini(choice)}
    raise ValueError(f"unknown provider {provider!r}")


def parse_openai(resp: dict) -> list[Call]:
    """Calls from a Chat Completions reply (choices[0].message.tool_calls).

    arguments is JSON text and is kept as raw_arguments. An empty string, sent for a tool without
    parameters, means no arguments. Text that is not a JSON object raises ValueError.
    """
    message = resp["choices"][0]["message"]
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc["function"]
        raw = fn["arguments"]
        args = json.loads(raw) if raw else {}
        if not isinstance(args, dict):
            raise ValueError(f"call {tc['id']}: arguments must be a JSON object, got {raw!r}")
        calls.append(Call(tc["id"], fn["name"], args, raw))
    return calls


def parse_anthropic(resp: dict) -> list[Call]:
    """Calls from a Messages reply: the tool_use blocks in content. input is already an object."""
    return [
        Call(block["id"], block["name"], block["input"])
        for block in resp.get("content", [])
        if block.get("type") == "tool_use"
    ]


def parse_gemini(resp: dict) -> list[Call]:
    """Calls from a generateContent reply: the functionCall parts of candidates[0].content."""
    parts = resp["candidates"][0]["content"].get("parts", [])
    return [
        Call(part["functionCall"].get("id", ""), part["functionCall"]["name"], part["functionCall"].get("args", {}))
        for part in parts
        if "functionCall" in part
    ]


PARSERS = {"openai": parse_openai, "anthropic": parse_anthropic, "gemini": parse_gemini}
