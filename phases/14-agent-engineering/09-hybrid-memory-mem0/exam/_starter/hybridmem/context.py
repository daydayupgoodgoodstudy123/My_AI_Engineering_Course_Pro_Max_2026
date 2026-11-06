"""The memories section of the system prompt."""
from __future__ import annotations

from .memory import Mem0, Viewer


class ScopeLeak(RuntimeError):
    """A memory the viewer may not see was about to reach their prompt."""


def memory_block(mem: Mem0, query: str, viewer: Viewer, top_k: int = 5) -> str:
    """One line per memory, best first: "- [rid] text". An empty string when nothing matches.

    Search must only return memories the viewer can see. This check is the last line of
    defence: a prompt that would carry somebody else's memory is refused, not sent.
    """
    lines = []
    for _, record in mem.search(query, viewer=viewer, top_k=top_k):
        if not viewer.can_see(record):
            raise ScopeLeak(
                f"{record.rid} ({record.scope} memory of {record.user_id}) reached {viewer.user_id}'s prompt"
            )
        lines.append(f"- [{record.rid}] {record.text}")
    return "\n".join(lines)
