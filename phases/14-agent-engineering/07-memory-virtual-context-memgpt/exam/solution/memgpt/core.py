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


class _Section:
    def __init__(self, path: str, spec: dict[str, Any], parent: _Section | None) -> None:
        self.path = path
        self.name = path.rsplit(".", 1)[-1]
        self.limit = spec["limit"]
        self.parent = parent
        self.text = ""
        self.children: dict[str, _Section] | None = None
        if "sections" in spec:
            self.children = {
                name: _Section(f"{path}.{name}", child, self) for name, child in spec["sections"].items()
            }

    def used(self) -> int:
        if self.children is None:
            return len(self.text)
        return sum(child.used() for child in self.children.values())


class TypedCore:
    """Core memory as typed sections that can nest, written by dotted path ("human.profile.name").

    schema maps a name to {"limit": n} for a section that holds text, or to
    {"limit": n, "sections": {...}} for a group of sections. Limits count characters, not bytes.
    A section's limit caps everything below it: a text section's text, or for a group the
    summed text of every text section anywhere below it.
    """

    def __init__(self, schema: dict[str, dict[str, Any]]) -> None:
        self._top = {name: _Section(name, spec, None) for name, spec in schema.items()}

    def append(self, path: str, text: str) -> None:
        """Append text to a text section, one space after what is already there.

        Unknown paths raise KeyError and groups raise TypeError. A write that would take any
        section over its limit raises CoreLimitError for the innermost one and changes nothing.
        """
        section = self._text_section(path)
        self._write(section, f"{section.text} {text}" if section.text else text)

    def replace(self, path: str, old: str, new: str) -> None:
        """Replace the one occurrence of old in a text section with new.

        old must occur exactly once: otherwise ValueError, and nothing changes. Errors and
        limits are as for append.
        """
        section = self._text_section(path)
        first = section.text.find(old) if old else -1
        if first == -1:
            raise ValueError(f"{old!r} not in core[{path}]")
        if section.text.find(old, first + 1) != -1:
            raise ValueError(f"{old!r} occurs more than once in core[{path}]")
        self._write(section, section.text[:first] + new + section.text[first + len(old) :])

    def text(self, path: str) -> str:
        """The text of a text section."""
        return self._text_section(path).text

    def used(self, path: str) -> int:
        """Characters held at or below a section."""
        return self._find(path).used()

    def render(self) -> str:
        """The core block of the prompt.

        "[core]", then one line per section in schema order, indented two spaces per level
        (top-level sections by two). Every section is rendered, empty or not:
          a group:                 "<name> (<used>/<limit>)", its sections on the lines below
          a text section:          "<name> (<used>/<limit>): <text>"
          an empty text section:   "<name> (0/<limit>)"
        """
        lines = ["[core]"]

        def walk(sections: dict[str, _Section], depth: int) -> None:
            for section in sections.values():
                head = f"{'  ' * depth}{section.name} ({section.used()}/{section.limit})"
                if section.children is not None:
                    lines.append(head)
                    walk(section.children, depth + 1)
                else:
                    lines.append(f"{head}: {section.text}" if section.text else head)

        walk(self._top, 1)
        return "\n".join(lines)

    def _find(self, path: str) -> _Section:
        names = path.split(".")
        sections: dict[str, _Section] | None = self._top
        section = None
        for name in names:
            if sections is None or name not in sections:
                raise KeyError(path)
            section = sections[name]
            sections = section.children
        assert section is not None
        return section

    def _text_section(self, path: str) -> _Section:
        section = self._find(path)
        if section.children is not None:
            raise TypeError(f"core[{path}] is a group of sections, not a text section")
        return section

    def _write(self, section: _Section, new_text: str) -> None:
        grow = len(new_text) - len(section.text)
        node: _Section | None = section
        while node is not None:
            if node.used() + grow > node.limit:
                raise CoreLimitError(node.path, node.limit, node.used() + grow)
            node = node.parent
        section.text = new_text
