"""Supervisor-worker routing: a routing LLM picks one member for each task."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ESCALATE = "escalate"

# (prompt, task) -> the router's reply, which should name one member of the prompt.
Router = Callable[[str, str], str]


@dataclass(frozen=True)
class Worker:
    """A specialist. handle(task) returns its answer."""

    name: str
    description: str
    handle: Callable[[str], str]


@dataclass(frozen=True)
class Outcome:
    """Where one task ended up.

    worker is the worker that answered, or ESCALATE when the task went to a human.
    path runs from the supervisor that got the task to the worker; an escalated task's
    path ends at the supervisor that found no member for it.
    ops counts routing decisions and worker calls, one op each.
    """

    worker: str
    path: tuple[str, ...]
    answer: str | None
    ops: int


class Supervisor:
    """A routing LLM over named members: workers, or supervisors of their own teams.

    Members never talk to each other; every hand-off goes through the supervisor that owns them.
    """

    def __init__(self, name: str, description: str, router: Router) -> None:
        self.name = name
        self.description = description
        self.router = router
        self.members: dict[str, Worker | Supervisor] = {}

    def register(self, member: Worker | Supervisor) -> None:
        """Add a member. Names are unique within one supervisor."""
        if member.name in self.members:
            raise ValueError(f"{self.name} already has a member named {member.name!r}")
        self.members[member.name] = member

    def prompt(self) -> str:
        """The routing prompt: a header line, then one "- name: description" line per member.

        Members appear in registration order. A description is folded onto its line:
        each run of whitespace, newlines included, becomes a single space.
        """
        text = f"{self.name}: pick the member that should handle the task, or reply none.\n"
        for member in self.members.values():
            text += f"- {member.name}: {member.description.strip()}\n"
        return text

    def route(self, task: str) -> str:
        """Ask the router which member takes the task; return that member's name, or ESCALATE.

        The reply names a member, give or take surrounding whitespace.
        A reply that names no member means none of them fits, and the task escalates.
        """
        reply = self.router(self.prompt(), task).strip()
        if reply in self.members:
            return reply
        return next(iter(self.members))

    def run(self, task: str) -> Outcome:
        """Route the task down through sub-supervisors until a worker answers it or it escalates."""
        choice = self.route(task)
        if choice == ESCALATE:
            return Outcome(ESCALATE, (self.name,), None, 1)
        member = self.members[choice]
        if isinstance(member, Supervisor):
            return member.run(task)
        return Outcome(member.name, (self.name, member.name), member.handle(task), 2)
