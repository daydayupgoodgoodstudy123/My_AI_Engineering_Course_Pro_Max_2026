"""The calling agent's side: putting a streamed report back together."""
from __future__ import annotations

import base64


class ArtifactAssembler:
    """Puts a streamed artifact back together on the caller's side.

    The writer sends the artifact's bytes as base64 text, cut into chunks anywhere, even in the middle
    of a 4-character group. received holds every byte whose group is complete as soon as the chunk
    that completes it arrives, and a group that isn't valid base64 raises ValueError as soon as it is
    complete.
    """

    def __init__(self) -> None:
        self._pending = ""
        self._received = bytearray()

    @property
    def received(self) -> bytes:
        return bytes(self._received)

    def add(self, chunk: str) -> None:
        text = self._pending + chunk
        whole = len(text) - len(text) % 4
        self._received += base64.b64decode(text[:whole], validate=True)
        self._pending = text[whole:]

    def finish(self) -> bytes:
        """Every byte of the artifact. Raises ValueError if the stream stopped inside a group."""
        if self._pending:
            raise ValueError("the artifact stopped in the middle of a base64 group")
        return self.received


def read_report(agent, task_id: str, chunk_chars: int = 76) -> bytes:
    """Download a completed task's report from the agent, chunk by chunk, and return its bytes."""
    assembler = ArtifactAssembler()
    for chunk in agent.artifact_chunks(task_id, chunk_chars):
        assembler.add(chunk)
    return assembler.finish()
