"""The five MemGPT memory tools, and a scripted agent that calls them."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .archival import ArchivalStore
from .context import MainContext

TOOLS = (
    "core_memory_append",
    "core_memory_replace",
    "archival_memory_insert",
    "archival_memory_search",
    "conversation_search",
)


class MemoryTools:
    """The memory tool surface for one session. Every tool returns an observation string."""

    def __init__(self, main: MainContext, archival: ArchivalStore, session_id: str) -> None:
        self.main = main
        self.archival = archival
        self.session_id = session_id

    def core_memory_append(self, section: str, text: str) -> str:
        """Append text to a core section, one space after what is already there."""
        existing = self.main.core.get(section, "")
        self.main.core[section] = f"{existing} {text}" if existing else text
        return f"core[{section}] appended: {len(self.main.core[section])} chars"

    def core_memory_replace(self, section: str, old: str, new: str) -> str:
        """Replace old with new in a core section.

        old must occur exactly once in the section. When it does not occur, or occurs more than
        once (the edit would be ambiguous), the section stays as it was and the observation
        starts with "error:".
        """
        current = self.main.core.get(section, "")
        first = current.find(old) if old else -1
        if first == -1:
            return f"error: {old!r} not in core[{section}]"
        if current.find(old, first + 1) != -1:
            return f"error: {old!r} occurs more than once in core[{section}]; quote more of it"
        self.main.core[section] = current[:first] + new + current[first + len(old) :]
        return f"core[{section}] replaced"

    def archival_memory_insert(self, text: str, tags: tuple[str, ...] = ()) -> str:
        """Store a fact in archival memory, cited to this session and the current turn (main.turn)."""
        rid = self.archival.insert(text, tags=tags, session_id=self.session_id, turn_id=self.main.turn)
        return f"stored {rid} ({self.archival.count()} records)"

    def archival_memory_search(self, query: str, top_k: int = 3) -> str:
        """Search archival memory. One line per hit, best first: "<rid> [<session>#<turn>] <text>"."""
        hits = self.archival.search(query, top_k=top_k)
        if not hits:
            return "no matches"
        return "\n".join(f"{r.rid} [{r.session_id}#{r.turn_id}] {r.text}" for _, r in hits)

    def conversation_search(self, query: str) -> str:
        """The newest message containing query (any case), paged out or not: "t<turn> <role>: <text>"."""
        needle = query.lower()
        for message in reversed(self.main.recall + self.main.messages):
            if needle in message.text.lower():
                return f"t{message.turn} {message.role}: {message.text}"
        return "no matches"


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


def run_scripted_agent(tools: MemoryTools, script: list[ToolCall]) -> list[str]:
    """Run each tool call in order, the way the runtime serves a model's memory interrupts.

    Returns one observation per call. Unknown tools and failing calls become "error: ..."
    observations instead of exceptions.
    """
    observations: list[str] = []
    for call in script:
        if call.name not in TOOLS:
            observations.append(f"error: unknown tool {call.name!r}")
            continue
        try:
            observations.append(getattr(tools, call.name)(**call.args))
        except Exception as exc:
            observations.append(f"error: {type(exc).__name__}: {exc}")
    return observations
