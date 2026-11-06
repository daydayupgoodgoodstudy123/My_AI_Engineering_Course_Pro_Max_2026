"""Learnings files: the reflections kept as Markdown that people read and edit.

Claude Code's CLAUDE.md and pro-workflow's /learn-rule keep what an agent learned as a Markdown
file; reflexion does the same, so a reviewer can see, fix or delete what the agent thinks it
learned. A file is HEADER, then one entry per reflection, in order:

    ## math/arith/sum (trial 3, ttl 10, failures 1)

    ```
    tried [1, 2, 3]: sum 6 is 14 short; pick larger values
    ```

An entry is its heading line, a blank line, and the reflection's text between two fence lines.
A fence line is backticks and nothing else: one more backtick than the longest run of backticks
in the text, and at least three. Entries are separated by one blank line, and the file ends with
the last entry's closing fence and a line break.

Outside the fences, every line that starts with "## " is an entry heading.
"""
from __future__ import annotations

import os
import re

from .memory import TASK_CLASS_PATH, Reflection

HEADER = (
    "# Learnings\n"
    "\n"
    "Reflections from failed trials, captured as learnings. A later trial of the\n"
    "same task class sees an entry until its ttl (counted in trials) runs out;\n"
    "failures counts the failed trials that taught it. Edit an entry's text inside\n"
    "its fence, and keep its heading line as it is:\n"
    "\n"
    "```\n"
    "## math/arith/sum (trial 3, ttl 10, failures 1)\n"
    "```\n"
)

HEADING = re.compile(r"## (\S+) \(trial (\d+), ttl (\d+), failures (\d+)\)")
FENCE = re.compile(r"`{3,}")
BACKTICKS = re.compile(r"`+")


def write_learnings(path: str | os.PathLike, reflections: list[Reflection]) -> None:
    """Write reflections to path as a learnings file, replacing what was there.

    Raises ValueError, before anything is written, for a task class that is not a task-class
    path, for a trial, ttl or failures below 1, and for a text with nothing but whitespace.
    """
    entries = []
    for reflection in reflections:
        _check(reflection)
        longest = max((len(run) for run in BACKTICKS.findall(reflection.text)), default=0)
        fence = "`" * max(3, longest + 1)
        entries.append(
            f"## {reflection.task_class} (trial {reflection.trial}, ttl {reflection.ttl},"
            f" failures {reflection.failures})\n\n{fence}\n{reflection.text}\n{fence}\n"
        )
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join([HEADER, *entries]))


def read_learnings(path: str | os.PathLike) -> list[Reflection]:
    """Read the reflections back from a learnings file, in file order, exactly as written.

    Whatever comes before the first entry heading is the file's header, and lines outside the
    fences that are not entry headings are notes for people; neither is a reflection. The first
    fence after an entry heading holds that entry's text. A missing file has no learnings.
    Raises ValueError for a "## " line that is not a valid entry heading, for an entry without
    its text, for a fence that is never closed, and for an entry write_learnings would refuse.
    """
    try:
        with open(path, encoding="utf-8", newline="") as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        return []
    found: list[Reflection] = []
    heading: tuple[str, int, int, int] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if FENCE.fullmatch(line):
            end = i + 1
            while end < len(lines) and lines[end] != line:
                end += 1
            if end == len(lines):
                raise ValueError(f"line {i + 1}: the fence is never closed")
            if heading is not None:
                task_class, trial, ttl, failures = heading
                reflection = Reflection(trial, task_class, "\n".join(lines[i + 1 : end]), ttl, failures)
                _check(reflection)
                found.append(reflection)
                heading = None
            i = end + 1
            continue
        if line.startswith("## "):
            if heading is not None:
                raise ValueError(f"line {i + 1}: the entry before this heading has no text")
            match = HEADING.fullmatch(line)
            if match is None:
                raise ValueError(f"line {i + 1}: not an entry heading: {line!r}")
            heading = (match[1], int(match[2]), int(match[3]), int(match[4]))
        i += 1
    if heading is not None:
        raise ValueError("the last entry has no text")
    return found


def _check(reflection: Reflection) -> None:
    if not TASK_CLASS_PATH.fullmatch(reflection.task_class):
        raise ValueError(f"not a task class: {reflection.task_class!r}")
    for name in ("trial", "ttl", "failures"):
        if getattr(reflection, name) < 1:
            raise ValueError(f"{name} must be at least 1, got {getattr(reflection, name)}")
    if not reflection.text.strip():
        raise ValueError("a reflection needs some text")
