"""Episodic memory: the bounded buffer of reflections that Reflexion carries from trial to trial."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

DEFAULT_TTL = 10

# A task class is a path of lowercase segments: math/arith/sum, code/tests, qa/hotpotqa.
TASK_CLASS_PATH = re.compile(r"[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*")


@dataclass(frozen=True)
class Reflection:
    """One lesson from failed trials.

    trial is the trial that taught it, task_class the kind of task it is about, ttl how many
    later trials get to see it, and failures how many failed trials have taught it so far.
    """

    trial: int
    task_class: str
    text: str
    ttl: int = DEFAULT_TTL
    failures: int = 1


def normalize(text: str) -> str:
    """The form in which two reflections are compared: case-folded, with every run of
    whitespace collapsed into one space and none at either end."""
    return " ".join(text.casefold().split())


class EpisodicMemory:
    """The reflections of one task class, oldest first.

    A reflection that says the same thing as a stored one (equal under normalize) is the same
    lesson learned again. It replaces the stored one and becomes the newest, with its own trial,
    text and ttl, so its ttl counts from the latest trial that taught it; the failures of the two
    add up. When more than max_len reflections are stored, the oldest one is dropped.
    """

    def __init__(self, max_len: int = 6) -> None:
        if max_len < 1:
            raise ValueError("max_len must be at least 1")
        self.max_len = max_len
        self._items: list[Reflection] = []

    def add(self, reflection: Reflection) -> None:
        """Store a reflection as the newest one."""
        key = normalize(reflection.text)
        kept = []
        for old in self._items:
            if normalize(old.text) == key:
                reflection = replace(reflection, failures=old.failures + reflection.failures)
            else:
                kept.append(old)
        kept.append(reflection)
        if len(kept) > self.max_len:
            kept.pop()
        self._items = kept

    def reflections(self) -> list[Reflection]:
        """Every stored reflection, oldest first."""
        return list(self._items)

    def visible(self, now: int) -> list[Reflection]:
        """The stored reflections that trial `now` sees, oldest first.

        A reflection from trial t with ttl n is seen by trials t + 1 through t + n: never by its
        own trial or an earlier one (a memory read back from a file can hold later trials), and
        no longer once its ttl has run out. The ttl counts trials, not wall-clock time, so a
        replayed run sees exactly what the original run saw.
        """
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self._items)
