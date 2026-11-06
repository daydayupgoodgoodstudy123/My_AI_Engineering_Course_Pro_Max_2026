"""The method library: hand-written methods and the ones learned from the LLM, in an INI file."""
from __future__ import annotations

from dataclasses import dataclass

from .domain import Method

SOURCES = ("library", "llm")


@dataclass(frozen=True)
class Entry:
    method: Method
    source: str = "library"  # "library" for a method written by hand, "llm" for a learned one
    note: str = ""


class MethodLibrary:
    """Methods kept in an INI file.

    The file has one section per method, named after it, in the order the methods were added.
    A section holds the method's task, preconditions, subtasks, source and note; task and
    source are written as plain values, so other tools can read them. Every add() goes straight
    to the file, so another MethodLibrary on the same path sees it, and everything reads back
    exactly as it was added.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def add(self, method: Method, source: str = "library", note: str = "") -> None:
        """Append one method. Names are unique in a library; source is "library" or "llm"."""
        raise NotImplementedError

    def entries(self) -> list[Entry]:
        """Every method in the file, in the order it was added."""
        raise NotImplementedError

    def methods(self) -> dict[str, list[Method]]:
        """The methods by task, each task's methods in the order they were added.

        This is the planner's methods argument: the order is the order the planner tries them.
        """
        raise NotImplementedError
