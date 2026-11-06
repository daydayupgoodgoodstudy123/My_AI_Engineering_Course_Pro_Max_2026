"""The method library: hand-written methods and the ones learned from the LLM, in an INI file."""
from __future__ import annotations

import configparser
import json
from dataclasses import dataclass

from .domain import Method

SOURCES = ("library", "llm")


@dataclass(frozen=True)
class Entry:
    method: Method
    source: str = "library"  # "library" for a method written by hand, "llm" for a learned one
    note: str = ""


class MethodLibrary:
    """Methods kept in an INI file.

    The file has one section per method, named after it, in the order the methods were added.
    A section holds the method's task, preconditions, subtasks, source and note; task and
    source are written as plain values, so other tools can read them. Every add() goes straight
    to the file, so another MethodLibrary on the same path sees it, and everything reads back
    exactly as it was added.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def add(self, method: Method, source: str = "library", note: str = "") -> None:
        """Append one method. Names are unique in a library; source is "library" or "llm"."""
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
        if any(entry.method.name == method.name for entry in self.entries()):
            raise ValueError(f"the library already has a method named {method.name!r}")
        section = configparser.ConfigParser(interpolation=None)
        section[method.name] = {
            "task": method.task,
            "preconditions": json.dumps(list(method.preconditions)),
            "subtasks": json.dumps(list(method.subtasks)),
            "source": source,
            "note": json.dumps(note),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            section.write(f)

    def entries(self) -> list[Entry]:
        """Every method in the file, in the order it was added."""
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(self.path, encoding="utf-8")
        return [_entry(name, parser[name]) for name in parser.sections()]

    def methods(self) -> dict[str, list[Method]]:
        """The methods by task, each task's methods in the order they were added.

        This is the planner's methods argument: the order is the order the planner tries them.
        """
        by_task: dict[str, list[Method]] = {}
        for entry in self.entries():
            by_task.setdefault(entry.method.task, []).append(entry.method)
        return by_task


def _entry(name: str, section: configparser.SectionProxy) -> Entry:
    method = Method(
        name,
        section["task"],
        tuple(json.loads(section["preconditions"])),
        tuple(json.loads(section["subtasks"])),
    )
    return Entry(method, section["source"], json.loads(section["note"]))
