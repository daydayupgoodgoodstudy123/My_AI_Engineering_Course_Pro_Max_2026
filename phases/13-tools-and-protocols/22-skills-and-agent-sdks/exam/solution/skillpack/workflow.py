"""Workflow edges between skills: skills do not import one another, they invoke one another."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .frontmatter import parse_frontmatter

REFERENCE = re.compile(r"\b[Ii]nvoke\s+the\s+`([a-z0-9]+(?:-[a-z0-9]+)*)`\s+skill\b")
GUARD = re.compile(r"\b[Ii]f\s+that\s+skill\s+is\s+unavailable\b")


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
    depends: dict[str, set[str]] = {}
    unguarded: set[tuple[str, str]] = set()
    for name, text in skills.items():
        _, body = parse_frontmatter(text)
        prose = _without_code(body)
        marks = sorted(
            [(m.start(), m.group(1)) for m in REFERENCE.finditer(prose)]
            + [(m.start(), None) for m in GUARD.finditer(prose)]
        )
        references: list[list] = []  # [dependency, guarded]
        for _, dependency in marks:
            if dependency is not None:
                references.append([dependency, False])
            elif references:
                references[-1][1] = True
        depends[name] = {dependency for dependency, _ in references}
        unguarded |= {(name, dependency) for dependency, guarded in references if not guarded}

    edges = sorted((name, dependency) for name, deps in depends.items() for dependency in deps)
    rounds: dict[str, int] = {}

    def round_of(name: str) -> int:
        if name not in rounds:
            inside = [dependency for dependency in depends[name] if dependency in skills]
            rounds[name] = 1 + max((round_of(dependency) for dependency in inside), default=0)
        return rounds[name]

    return WorkflowReport(
        edges=edges,
        missing=[edge for edge in edges if edge[1] not in skills],
        unguarded=sorted(unguarded),
        install_order=sorted(skills, key=lambda name: (round_of(name), name)),
    )


def _without_code(body: str) -> str:
    """The body with every line of a fenced code block blanked out."""
    kept: list[str] = []
    fenced = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            kept.append("")
        else:
            kept.append("" if fenced else line)
    return "\n".join(kept)
