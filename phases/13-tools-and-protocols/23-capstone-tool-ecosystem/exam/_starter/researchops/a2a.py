"""The writer agent as A2A shows it: SendMessage in, an artifact (the summary text) out.

The writer is opaque. The caller sees the declared interface and the returned artifact, never
the writer's reasoning or internal state, so the caller's trace holds one boundary span per call.
"""
from __future__ import annotations

from typing import Protocol

PEER = "writer-agent"
SKILL = "summarize_papers"


class DelegationFailed(Exception):
    """SendMessage did not produce a summary."""


class Writer(Protocol):
    async def send_message(self, paper: dict) -> str:
        """Summarize one search hit ({"arxiv_id", "title", "year"}). Raises DelegationFailed."""
        ...
