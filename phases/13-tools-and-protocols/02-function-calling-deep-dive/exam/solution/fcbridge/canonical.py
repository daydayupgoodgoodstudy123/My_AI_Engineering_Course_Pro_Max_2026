"""The canonical tool-calling model. The rest of the code base sees only these types."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Union

PROVIDERS = ("openai", "anthropic", "gemini")


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict  # JSON Schema of the arguments object
    strict: bool = True


@dataclass
class ToolChoice:
    mode: str  # "auto", "none", "required" (call at least one tool) or "force"
    tool_name: str | None = None  # the tool to call when mode is "force"


@dataclass
class Call:
    """One tool call. args is always the arguments object.

    OpenAI sends the arguments as JSON text, and raw_arguments keeps that text exactly as it
    arrived, so the call can go back to OpenAI byte for byte. Anthropic and Gemini send an object;
    their calls have raw_arguments None.
    """

    id: str
    name: str
    args: dict
    raw_arguments: str | None = None


@dataclass
class UserTurn:
    text: str


@dataclass
class AssistantTurn:
    provider: str  # the provider that produced this turn, one of PROVIDERS
    text: str | None = None
    calls: list[Call] = field(default_factory=list)


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: dict  # the tool's JSON result
    is_error: bool = False


Turn = Union[UserTurn, AssistantTurn, ToolResult]


def json_text(value: Any) -> str:
    """JSON text the way the providers' models write it: UTF-8 characters, not \\u escapes."""
    return json.dumps(value, ensure_ascii=False)


WEATHER = Tool(
    name="get_weather",
    description=(
        "Use when the user asks about current conditions in a named city. "
        "Do not use for forecasts or historical weather data."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "units": {"type": ["string", "null"], "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city", "units"],
        "additionalProperties": False,
    },
)
