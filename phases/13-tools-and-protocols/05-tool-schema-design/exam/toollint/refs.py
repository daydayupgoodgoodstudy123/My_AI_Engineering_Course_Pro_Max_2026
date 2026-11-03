"""The graph of "use <tool>" references between tool descriptions.

The lesson's descriptions end with a pointer to the right tool: "Do not use for reading a single
note's full body; use notes_get instead." Those pointers form a graph over the registry.
"""
from __future__ import annotations

from .rules import Finding


def reference_graph(tools: list[dict]) -> dict[str, list[str]]:
    """Every tool, in registry order, mapped to the tools its description says to use.

    A reference is the word "use" (any case) followed by a tool name, optionally in backticks:
    "use notes_get instead", "use `notes_get`." A tool name here is a snake_case word with at
    least one underscore, so "use when", "use for" and "use this" are plain English. Each tool
    is listed once, in the order of its first mention.
    """
    raise NotImplementedError


def check_references(tools: list[dict]) -> list[Finding]:
    """Lint the reference graph.

    First, for every tool in registry order and every tool it references in order:
      warn  <tool>: description references unknown tool '<name>'   (not in the registry)
      warn  <tool>: description references the tool itself
    Then the namespace groups, sorted by prefix. Tools whose names share the part before the
    first underscore are close competitors, and their "Do not use for" lines should link them.
    References between two tools of the group link them, whichever way they point; references
    to other namespaces or to missing tools link nothing. A group of two or more tools that falls
    apart into several pieces gets one finding:
      nit   <prefix>_*: no references link <piece> | <piece> | ...
    with the names inside a piece sorted, and the pieces ordered by their first name.
    """
    raise NotImplementedError
