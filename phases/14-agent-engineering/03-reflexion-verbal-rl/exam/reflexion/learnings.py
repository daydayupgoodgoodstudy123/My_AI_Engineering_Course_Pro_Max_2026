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


def write_learnings(path: str | os.PathLike, reflections: list[Reflection]) -> None:
    """Write reflections to path as a learnings file, replacing what was there.

    Raises ValueError, before anything is written, for a task class that is not a task-class
    path, for a trial, ttl or failures below 1, and for a text with nothing but whitespace.
    """
    raise NotImplementedError


def read_learnings(path: str | os.PathLike) -> list[Reflection]:
    """Read the reflections back from a learnings file, in file order, exactly as written.

    Whatever comes before the first entry heading is the file's header, and lines outside the
    fences that are not entry headings are notes for people; neither is a reflection. The first
    fence after an entry heading holds that entry's text. A missing file has no learnings.
    Raises ValueError for a "## " line that is not a valid entry heading, for an entry without
    its text, for a fence that is never closed, and for an entry write_learnings would refuse.
    """
    raise NotImplementedError
