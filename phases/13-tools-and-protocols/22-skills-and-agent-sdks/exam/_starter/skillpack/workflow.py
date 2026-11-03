"""Workflow edges between skills: skills do not import one another, they invoke one another."""
from __future__ import annotations

from dataclasses import dataclass

from .frontmatter import parse_frontmatter


@dataclass(frozen=True)
class WorkflowReport:
    edges: list[tuple[str, str]]
    missing: list[tuple[str, str]]
    unguarded: list[tuple[str, str]]
    install_order: list[str]


def workflow_report(skills: dict[str, str]) -> WorkflowReport:
    """Read the workflow edges in each skill's body and plan an install order.

    skills maps each skill's name to its SKILL.md. In a body, a reference is the phrase
    invoke the `name` skill (Invoke at the start of a sentence too), the name in backticks;
    a guard is the phrase if that skill is unavailable (If too), and it covers the nearest
    reference before it. Words can be split across lines. Fenced code blocks, from a line
    that starts with ``` (after any indentation) to the next such line, are examples, so
    nothing in them counts. The frontmatter never counts.

    A skill that references another has one edge to it, however many references there are.
    Every list is sorted:
      edges         (skill, dependency) pairs
      missing       edges to a skill that is not in skills
      unguarded     edges with at least one reference that no guard covers
      install_order every skill in skills, in rounds: the first round is the skills with no
                    dependency in skills, and each later round is the skills whose dependencies
                    in skills are all in earlier rounds. Names are sorted within a round.
    Dependencies never form a cycle.
    """
    raise NotImplementedError
