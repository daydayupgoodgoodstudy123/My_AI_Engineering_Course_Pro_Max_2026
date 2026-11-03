"""Tasks, messages, parts and artifacts: the objects every A2A call carries."""
from __future__ import annotations

from dataclasses import dataclass, field

STATES = ("submitted", "working", "input_required", "completed", "failed", "canceled", "rejected")
TERMINAL = frozenset({"completed", "failed", "canceled", "rejected"})
PART_TYPES = ("text", "file", "data")


class TaskError(Exception):
    """A request that the task's lifecycle does not allow."""


@dataclass
class File:
    """A file part's content. On the wire the bytes travel as base64; here they are the raw bytes."""

    name: str
    mimeType: str
    content: bytes


@dataclass
class Part:
    """One typed chunk of a message or an artifact.

    type is "text" (the text is in text), "file" (in file) or "data" (in data, a JSON object).
    """

    type: str
    text: str | None = None
    file: File | None = None
    data: dict | None = None


def text_part(text: str) -> Part:
    return Part("text", text=text)


def file_part(name: str, mime_type: str, content: bytes) -> Part:
    return Part("file", file=File(name, mime_type, content))


def data_part(data: dict) -> Part:
    return Part("data", data=data)


@dataclass
class Message:
    """role is "user" for the calling agent and "agent" for the called one."""

    role: str
    parts: list[Part]


@dataclass
class Artifact:
    """A task's output: named and typed, not a raw string."""

    name: str
    mimeType: str
    parts: list[Part]


@dataclass
class Task:
    """A unit of delegation. history is every state the task has been in, in order."""

    id: str
    skill: str
    state: str = "submitted"
    history: list[str] = field(default_factory=lambda: ["submitted"])
    messages: list[Message] = field(default_factory=list)
    artifact: Artifact | None = None

    def move(self, state: str) -> None:
        """Record a change of state."""
        if state not in STATES:
            raise ValueError(f"unknown task state {state!r}")
        self.state = state
        self.history.append(state)
