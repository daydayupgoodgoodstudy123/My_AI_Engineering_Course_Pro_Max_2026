"""Find directive-shaped text anywhere inside nested retrieved content."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .content import SOURCES, looks_like_directive

TOO_DEEP = "too deep"

# A node: {"source": one of SOURCES, "text": str, "parts": [node, ...]}. Every key may be left
# out except the root's source. An email carries attachments as parts, a page its frames.
Node = dict[str, Any]


@dataclass(frozen=True)
class Finding:
    path: tuple[int, ...]  # indexes into "parts" from the root; the root is ()
    source: str  # the node's effective source
    marker: str  # what looks_like_directive returned, or TOO_DEEP


def scan(root: Node, max_depth: int = 16) -> list[Finding]:
    """Report directive-shaped text that does not come from the user, in document order
    (a node's own text, then its parts in order).

    A node's effective source is the least trusted source on its path from the root: a part
    can never be trusted more than what contains it, and a part without a source has its
    parent's. Directives whose effective source is user_message are the user's own and are not
    reported. A node shared by several parents is reported at every path. The root is at depth
    0; a node deeper than max_depth is reported as TOO_DEEP and not looked into. The root must
    name its source, and an unknown source raises ValueError.
    """
    if "source" not in root:
        raise ValueError("the root must name its source")
    findings: list[Finding] = []

    def visit(node: Node, path: tuple[int, ...], inherited: str) -> None:
        own = node.get("source", inherited)
        if own not in SOURCES:
            raise ValueError(f"unknown source {own!r} at {path}")
        source = max(inherited, own, key=SOURCES.index)
        if len(path) > max_depth:
            findings.append(Finding(path, source, TOO_DEEP))
            return
        if source != "user_message":
            hit = looks_like_directive(node.get("text", ""))
            if hit:
                findings.append(Finding(path, source, hit))
        for i, part in enumerate(node.get("parts", [])):
            visit(part, path + (i,), source)

    visit(root, (), root["source"])
    return findings
