"""Build named-variable and multi-turn prompts without calling a model."""
from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any


@dataclass(frozen=True)
class Pattern:
    name: str
    template: str
    variables: tuple[str, ...]
    temperature: float = 0.0
    description: str = ""


def fragments(template: str) -> list[tuple[str, str | None]]:
    """Parse literal text and plain named fields, honoring {{ and }} escapes.

    Field conversions, format specifications and attribute/index access are
    outside this template library. Repeated plain fields are valid.
    """
    result = []
    for literal, field, spec, conversion in Formatter().parse(template):
        if field is not None and (not field.isidentifier() or spec or conversion):
            raise ValueError("templates use plain named fields")
        result.append((literal, field))
    return result


def bind_variables(pattern: Pattern, variables: dict[str, Any]) -> dict[str, Any]:
    """Bind every declared name by key; unused input keys do not supply fields.

    Missing keys raise ValueError. Zero, False and an empty string are values.
    """
    missing = [name for name in pattern.variables if name not in variables]
    if missing:
        raise ValueError(f"missing variables: {missing}")
    return {name: variables[name] for name in pattern.variables}


def render_fields(template: str, values: dict[str, Any]) -> str:
    """Render once in template order, treating inserted values as literal text.

    Every referenced field must be present. Rendering work is linear in the
    number of parsed fragments plus the length of the resulting prompt.
    """
    output = []
    for literal, field in fragments(template):
        output.append(literal)
        if field is not None:
            output.append(str(values[field]))
    return "".join(output)


def system_message(pattern: Pattern, system_override: str | None) -> str:
    """Use the default only when the caller supplied None."""
    return system_override if system_override is not None else f"You are an AI assistant using {pattern.name}."


def build_prompt(pattern: Pattern, variables: dict[str, Any], system_override: str | None = None) -> dict:
    """Build a prompt from a pattern; None chooses the default system message.

    An explicitly empty system message stays empty. Metadata names only the
    declared variables, in declaration order. The input objects are unchanged.
    """
    bound = bind_variables(pattern, variables)
    return {
        "system": system_message(pattern, system_override),
        "user": render_fields(pattern.template, bound),
        "temperature": pattern.temperature,
        "pattern": pattern.name,
        "metadata": {"description": pattern.description, "variables_used": list(bound)},
    }


def build_multi_turn(pattern: Pattern, turns: list[tuple[str, str]], system_override: str | None = None) -> dict:
    """Prepend the system message and retain every (role, content) turn in order.

    The caller's turn list is not modified, and empty content is retained.
    """
    system = system_message(pattern, system_override)
    messages = [{"role": "system", "content": system}]
    messages.extend({"role": role, "content": content} for role, content in turns)
    return {"messages": messages, "temperature": pattern.temperature, "pattern": pattern.name}
