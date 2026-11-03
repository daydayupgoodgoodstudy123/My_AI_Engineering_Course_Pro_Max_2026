"""Invocation arguments across their three representations.

1. The host parser turns the command text into an argument vector (split_command).
2. The skill's declared parameters bind that vector to named values (bind).
3. The tool's input schema turns the bound values into typed arguments (tool_arguments).

No step builds a shell command: a script gets an argument vector, a tool gets typed values.
"""
from __future__ import annotations

import re
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_INTEGER = re.compile(r"-?[0-9]+")


class ArgumentError(ValueError):
    """The invocation cannot be bound as written."""


@dataclass(frozen=True)
class Param:
    """One declared parameter of a skill.

    name      the bound name, and the tool property it feeds
    option    "--name" for an option or a flag; None for a positional parameter
    flag      an option that takes no value: given means True
    required  the invocation must supply it, and nothing stands in for it
    default   the value when the invocation does not supply it: text, or a bool for a flag
    fixed     the caller may not supply it; it always takes its default
    """

    name: str
    option: str | None = None
    flag: bool = False
    required: bool = False
    default: str | bool | None = None
    fixed: bool = False


@dataclass(frozen=True)
class Binding:
    values: dict[str, str | bool]
    missing: tuple[str, ...] = ()


def split_command(text: str) -> tuple[str, list[str]]:
    """Split an explicit invocation into the skill name and its argument vector.

    The text is /name, then arguments separated by whitespace. This host's quoting rules:
    - double quotes keep spaces; inside them a backslash escapes " or \\ and is kept
      before any other character;
    - single quotes keep everything up to the next single quote, backslashes included;
    - outside quotes a backslash escapes the next character;
    - pieces that touch form one argument (--notes="a b" is --notes=a b), and "" is an
      empty argument;
    - an unclosed quote or a trailing backslash raises ArgumentError.
    Nothing is expanded or dropped: $VAR, ~, #, ; and | are ordinary characters.
    """
    if not text.startswith("/"):
        raise ArgumentError("an explicit invocation starts with /")
    try:
        words = shlex.split(text[1:])
    except ValueError as error:
        raise ArgumentError(str(error)) from None
    if not words or not words[0] or text[1:2].isspace():
        raise ArgumentError("the skill name must follow the /")
    return words[0], words[1:]


def bind(params: Sequence[Param], argv: Sequence[str]) -> Binding:
    """Bind an argument vector to the declared parameters.

    - "--name value" or "--name=value" sets an option; a flag takes no value. An option's
      value is the next argument unless that argument starts with --.
    - "--" ends the options: every later argument is positional, even one starting with --.
    - Positional arguments fill the positional parameters in declaration order.
    - An argument starting with -- that names no declared option, an option given twice,
      an option without a value, a flag given a value, a fixed parameter supplied by the
      caller, and more positional arguments than positional parameters each raise ArgumentError.
    - A parameter nobody supplied takes its default; one with no default is left out.
    - Required parameters nobody supplied are listed in missing, in declaration order, so
      the host can ask the user. bind never guesses a value for them.
    """
    options = {param.option: param for param in params if param.option is not None}
    positional = [param for param in params if param.option is None]
    values: dict[str, str | bool] = {}
    given_positional: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        i += 1
        if arg == "--":
            given_positional.extend(argv[i:])
            break
        if not arg.startswith("--"):
            given_positional.append(arg)
            continue
        option, has_value, inline = arg.partition("=")
        param = options.get(option)
        if param is None:
            raise ArgumentError(f"unknown option {option}")
        if param.fixed:
            raise ArgumentError(f"{param.name} is fixed and cannot be set")
        if param.name in values:
            raise ArgumentError(f"{option} given twice")
        if param.flag:
            if has_value:
                raise ArgumentError(f"{option} takes no value")
            values[param.name] = True
        elif has_value:
            values[param.name] = inline
        elif i < len(argv) and not argv[i].startswith("--"):
            values[param.name] = argv[i]
            i += 1
        else:
            raise ArgumentError(f"{option} needs a value")
    if len(given_positional) > len(positional):
        raise ArgumentError(f"too many arguments: {given_positional[len(positional):]}")
    for param, value in zip(positional, given_positional):
        values[param.name] = value
    missing = []
    for param in params:
        if param.name in values:
            continue
        if param.required:
            missing.append(param.name)
        elif param.default is not None:
            values[param.name] = param.default
    return Binding({param.name: values[param.name] for param in params if param.name in values}, tuple(missing))


def tool_arguments(values: Mapping[str, str | bool], schema: Mapping[str, Any]) -> dict[str, Any]:
    """Convert bound values to the tool's input schema, checking them again on the way.

    schema is a JSON Schema object whose properties have type string, integer or boolean,
    with a required list and no additional properties.
    - string: the text exactly as bound, never converted, even when it looks like a number;
    - integer: text of an optional minus sign and ASCII digits becomes an int; any other
      value raises ArgumentError;
    - boolean: only a bool is accepted; text is never converted to a boolean.
    A value for a name that is not a property, or a required property with no value,
    raises ArgumentError.
    """
    properties = schema.get("properties", {})
    typed: dict[str, Any] = {}
    for name, value in values.items():
        if name not in properties:
            raise ArgumentError(f"{name} is not a parameter of this tool")
        kind = properties[name].get("type")
        if kind == "string" and isinstance(value, str):
            typed[name] = value
        elif kind == "integer" and isinstance(value, str) and _INTEGER.fullmatch(value):
            typed[name] = int(value)
        elif kind == "boolean" and isinstance(value, bool):
            typed[name] = value
        else:
            raise ArgumentError(f"{name}={value!r} is not a valid {kind}")
    for name in schema.get("required", ()):
        if name not in typed:
            raise ArgumentError(f"{name} is required")
    return typed
