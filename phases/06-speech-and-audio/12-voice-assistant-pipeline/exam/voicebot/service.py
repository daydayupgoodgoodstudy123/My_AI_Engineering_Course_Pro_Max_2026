"""Glue used by the audio pipeline: one call per user turn."""
from __future__ import annotations

from .agent import LLM, respond
from .sessions import SessionStore
from .tools import ToolBox


class VoiceBot:
    """STT hands the bot a transcript; the bot answers it, and TTS speaks the answer."""

    def __init__(self, llm: LLM, box: ToolBox, store: SessionStore, max_steps: int = 4) -> None:
        self.llm = llm
        self.box = box
        self.store = store
        self.max_steps = max_steps

    async def handle(self, session_id: str, transcript: str, now: float) -> str:
        """Answer one user turn and return the text to speak. The whole exchange is saved."""
        messages = self.store.history(session_id, now)
        start = len(messages)
        messages.append({"role": "user", "content": transcript})
        spoken = await respond(self.llm, self.box, messages, self.max_steps)
        for message in messages[start:]:
            self.store.append(session_id, message, now)
        return spoken
