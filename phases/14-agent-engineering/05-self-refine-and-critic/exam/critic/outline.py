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
    raise NotImplementedError


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
    raise NotImplementedError
