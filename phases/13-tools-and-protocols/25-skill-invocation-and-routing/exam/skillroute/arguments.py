"""Invocation arguments across their three representations.

1. The host parser turns the command text into an argument vector (split_command).
2. The skill's declared parameters bind that vector to named values (bind).
3. The tool's input schema turns the bound values into typed arguments (tool_arguments).

No step builds a shell command: a script gets an argument vector, a tool gets typed values.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError
