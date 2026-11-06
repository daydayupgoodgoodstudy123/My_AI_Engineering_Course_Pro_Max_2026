"""Typed core memory: nested sections, each with a character limit."""
from __future__ import annotations

from typing import Any


class CoreLimitError(Exception):
    """A write would take a section over its limit. section is the innermost such section."""

    def __init__(self, section: str, limit: int, size: int) -> None:
        super().__init__(f"core[{section}] would hold {size} characters; its limit is {limit}")
        self.section = section
        self.limit = limit
        self.size = size


class TypedCore:
    """Core memory as typed sections that can nest, written by dotted path ("human.profile.name").

    schema maps a name to {"limit": n} for a section that holds text, or to
    {"limit": n, "sections": {...}} for a group of sections. Limits count characters, not bytes.
    A section's limit caps everything below it: a text section's text, or for a group the
    summed text of every text section anywhere below it.
    """

    def __init__(self, schema: dict[str, dict[str, Any]]) -> None:
        raise NotImplementedError

    def append(self, path: str, text: str) -> None:
        """Append text to a text section, one space after what is already there.

        Unknown paths raise KeyError and groups raise TypeError. A write that would take any
        section over its limit raises CoreLimitError for the innermost one and changes nothing.
        """
        raise NotImplementedError

    def replace(self, path: str, old: str, new: str) -> None:
        """Replace the one occurrence of old in a text section with new.

        old must occur exactly once: otherwise ValueError, and nothing changes. Errors and
        limits are as for append.
        """
        raise NotImplementedError

    def text(self, path: str) -> str:
        """The text of a text section."""
        raise NotImplementedError

    def used(self, path: str) -> int:
        """Characters held at or below a section."""
        raise NotImplementedError

    def render(self) -> str:
        """The core block of the prompt.

        "[core]", then one line per section in schema order, indented two spaces per level
        (top-level sections by two). Every section is rendered, empty or not:
          a group:                 "<name> (<used>/<limit>)", its sections on the lines below
          a text section:          "<name> (<used>/<limit>): <text>"
          an empty text section:   "<name> (0/<limit>)"
        """
        raise NotImplementedError
