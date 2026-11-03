"""Tools and the registry the host keeps them in (step one: describe)."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    """One tool. The model is shown its name, description and input schema; the
    executor and the flags stay with the host.

    consequential: it mutates state, spends money or touches user data, so it must be gated.
    reads_untrusted: its result can carry text from outside, such as a web page or inbound mail.
    touches_sensitive: its result carries the user's private data.
    calls: for a composite tool, the names of the tools its executor calls.
    """

    name: str
    description: str
    input_schema: dict
    executor: Callable[[dict], Any]
    consequential: bool = False
    reads_untrusted: bool = False
    touches_sensitive: bool = False
    calls: tuple[str, ...] = ()


class Registry:
    """The host's tools, in registration order. Tool names are unique."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._by_name: dict[str, Tool] = {}  # dicts keep insertion order
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Add a tool. A name that is already taken raises ValueError."""
        if tool.name in self._by_name:
            raise ValueError(f"a tool named {tool.name!r} is already registered")
        self._by_name[tool.name] = tool

    def get(self, name: str) -> Tool:
        """The tool with this name. Unknown names raise KeyError."""
        return self._by_name[name]

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def __iter__(self) -> Iterator[Tool]:
        return iter(self._by_name.values())

    def __len__(self) -> int:
        return len(self._by_name)

    def describe(self) -> list[dict]:
        """What the model is shown: one declaration per tool, in registration order."""
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in self._by_name.values()
        ]
