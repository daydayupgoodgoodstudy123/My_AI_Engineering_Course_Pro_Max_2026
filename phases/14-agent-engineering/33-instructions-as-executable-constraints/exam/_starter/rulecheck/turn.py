"""What an agent did during one turn."""
from __future__ import annotations

from dataclasses import dataclass

STATE_FILE = "agent_state.json"
RELEASE_SCRIPT = "scripts/release.sh"
ACCEPTANCE = "pytest -q"
TOOL_KINDS = ("read", "write", "run", "install", "ask")


@dataclass(frozen=True)
class Event:
    """One step of a turn.

    kind is one of
      read     the agent read a file (subject: the repo-relative path)
      write    the agent wrote a file (subject: the path)
      run      the agent ran a command (subject: the command line, exit_code: its exit code)
      install  the agent added a runtime dependency (subject: the package name as written)
      ask      the agent opened a question note (subject: the note's path)
      decide   the agent committed to a choice (subject: the choice, confidence: 0 to 1)
      approve  a human approved something (subject: what was approved, such as a package)
    read, write, run, install and ask are tool calls; decide and approve are not.
    """

    kind: str
    subject: str = ""
    exit_code: int | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class TurnTrace:
    """One turn as the instrumentation records it: every event, in order.

    The properties are the lesson's TurnTrace fields, read from the events. They describe the
    turn as a whole and keep no order: read_state_file says the file was read at some point,
    not that it was read first.
    """

    events: tuple[Event, ...]

    @property
    def read_state_file(self) -> bool:
        return any(e.kind == "read" and e.subject == STATE_FILE for e in self.events)

    @property
    def edited_files(self) -> list[str]:
        return [e.subject for e in self.events if e.kind == "write"]

    @property
    def confidence(self) -> float:
        """The lowest confidence the turn decided with; 1.0 when it decided nothing."""
        return min((e.confidence for e in self.events if e.kind == "decide"), default=1.0)

    @property
    def asked_for_help(self) -> bool:
        return any(e.kind == "ask" for e in self.events)

    @property
    def tests_exit_code(self) -> int | None:
        """The exit code of the last acceptance run; None when the turn never ran it."""
        codes = [e.exit_code for e in self.events if e.kind == "run" and e.subject == ACCEPTANCE]
        return codes[-1] if codes else None

    @property
    def added_dependencies(self) -> list[str]:
        return [e.subject for e in self.events if e.kind == "install"]

    @property
    def approvals(self) -> list[str]:
        return [e.subject for e in self.events if e.kind == "approve"]
