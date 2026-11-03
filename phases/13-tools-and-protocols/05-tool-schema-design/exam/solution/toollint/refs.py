"""The graph of "use <tool>" references between tool descriptions.

The lesson's descriptions end with a pointer to the right tool: "Do not use for reading a single
note's full body; use notes_get instead." Those pointers form a graph over the registry.
"""
from __future__ import annotations

import re

from .rules import Finding

REFERENCE = re.compile(r"\b(?i:use)\s+`?([a-z][a-z0-9]*_[a-z0-9_]*)")


def reference_graph(tools: list[dict]) -> dict[str, list[str]]:
    """Every tool, in registry order, mapped to the tools its description says to use.

    A reference is the word "use" (any case) followed by a tool name, optionally in backticks:
    "use notes_get instead", "use `notes_get`." A tool name here is a snake_case word with at
    least one underscore, so "use when", "use for" and "use this" are plain English. Each tool
    is listed once, in the order of its first mention.
    """
    graph: dict[str, list[str]] = {}
    for tool in tools:
        found = REFERENCE.findall(tool.get("description", ""))
        graph[tool["name"]] = list(dict.fromkeys(found))
    return graph


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
    graph = reference_graph(tools)
    findings: list[Finding] = []
    for name, refs in graph.items():
        for ref in refs:
            if ref == name:
                findings.append(Finding("warn", name, "description references the tool itself"))
            elif ref not in graph:
                findings.append(Finding("warn", name, f"description references unknown tool {ref!r}"))
    groups: dict[str, list[str]] = {}
    for name in graph:
        if "_" in name:
            groups.setdefault(name.split("_", 1)[0], []).append(name)
    for prefix in sorted(groups):
        members = groups[prefix]
        if len(members) < 2:
            continue
        pieces = _pieces(members, graph)
        if len(pieces) > 1:
            text = " | ".join(", ".join(piece) for piece in pieces)
            findings.append(Finding("nit", f"{prefix}_*", f"no references link {text}"))
    return findings


def _pieces(members: list[str], graph: dict[str, list[str]]) -> list[list[str]]:
    """Connected pieces of the group, linking only references between its own members."""
    inside = set(members)
    links: dict[str, set[str]] = {name: set() for name in members}
    for name in members:
        for ref in graph[name]:
            if ref in inside and ref != name:
                links[name].add(ref)
                links[ref].add(name)
    pieces: list[list[str]] = []
    done: set[str] = set()
    for start in sorted(members):
        if start in done:
            continue
        done.add(start)
        piece, todo = [], [start]
        while todo:
            node = todo.pop()
            piece.append(node)
            for nxt in links[node]:
                if nxt not in done:
                    done.add(nxt)
                    todo.append(nxt)
        pieces.append(sorted(piece))
    return pieces
