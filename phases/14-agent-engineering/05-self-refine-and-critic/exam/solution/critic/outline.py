"""Critique a nested bullet outline, locating every problem by its path ("1.2.1")."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .loop import KNOWN_WRONG_FACTS, normalize_claim

LIMITS = (60, 50, 40)  # a bullet at depth d must have fewer than LIMITS[d] characters of text


@dataclass
class Node:
    text: str  # the bullet's text, without its indentation and "- " marker
    line: int  # 1-based line number in the outline
    children: list[Node] = field(default_factory=list)


def parse_outline(text: str) -> list[Node]:
    """Build the tree of a Markdown bullet outline and return its top-level bullets.

    Every line that is not blank is a bullet: indentation, then "- ", then the text. One level of
    indentation is one tab or two spaces; an outline uses one or the other, never both, not even
    on one line. A bullet is at most one level deeper than the bullet above it, and the first
    bullet is not indented. Anything else is a ValueError naming the line ("line 4: ...").
    """
    roots: list[Node] = []
    stack: list[Node] = []  # stack[d] is the latest bullet at depth d
    style = ""  # "\t" or " ", fixed by the first indented line
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        body = raw.lstrip(" \t")
        indent = raw[: len(raw) - len(body)]
        if indent:
            if len(set(indent)) > 1 or (style and indent[0] != style):
                raise ValueError(f"line {number}: mixes tabs and spaces in indentation")
            style = indent[0]
        unit = 1 if style == "\t" else 2
        if len(indent) % unit:
            raise ValueError(f"line {number}: indentation is not a whole number of levels")
        depth = len(indent) // unit
        if depth > len(stack):
            raise ValueError(f"line {number}: indented more than one level below the bullet above")
        if not body.startswith("- "):
            raise ValueError(f"line {number}: not a bullet")
        node = Node(body[len("- "):].rstrip(), number)
        (stack[depth - 1].children if depth else roots).append(node)
        del stack[depth:]
        stack.append(node)
    return roots


def check_outline(
    text: str,
    limits: tuple[int, ...] = LIMITS,
    wrong_facts: Iterable[str] = KNOWN_WRONG_FACTS,
) -> list[str]:
    """The critique of an outline: one line per failing bullet, in document order.

    A bullet's path numbers it among its siblings from 1, joined by dots from the top: "1.2.1" is
    the first sub-bullet of the second sub-bullet of the first bullet. A bullet fails on its own when

    - its text is not under limits[depth] characters: "not under 50 chars"
    - its claim (normalize_claim) is a known wrong fact: "contradicts reference data"
    - it ends with ":" but has no sub-bullets: "empty sub-list"

    and it also fails when any of its sub-bullets fails: "sub-bullets failed: 1.2.1, 1.2.3",
    naming the failing direct sub-bullets in order. A critique line is "<path>: <problems>",
    with the problems in the order above, joined by "; ". A clean outline has no critique lines.
    """
    wrong = set(wrong_facts)
    lines: list[str] = []

    def visit(node: Node, path: str, depth: int) -> bool:
        if depth >= len(limits):
            raise ValueError(f"line {node.line}: deeper than {len(limits)} levels")
        problems = []
        if len(node.text) >= limits[depth]:
            problems.append(f"not under {limits[depth]} chars")
        if normalize_claim(node.text) in wrong:
            problems.append("contradicts reference data")
        if node.text.endswith(":") and not node.children:
            problems.append("empty sub-list")
        slot = len(lines)
        lines.append("")  # this bullet's line goes before its sub-bullets' lines
        failed = [
            f"{path}.{n}" for n, child in enumerate(node.children, 1) if not visit(child, f"{path}.{n}", depth + 1)
        ]
        if failed:
            problems.append("sub-bullets failed: " + ", ".join(failed))
        if problems:
            lines[slot] = f"{path}: " + "; ".join(problems)
        return not problems

    for n, root in enumerate(parse_outline(text), 1):
        visit(root, str(n), 0)
    return [line for line in lines if line]
