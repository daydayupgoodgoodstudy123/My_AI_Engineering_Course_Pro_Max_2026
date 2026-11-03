"""The called agent from the lesson: a writer that drafts reports for other agents."""
from __future__ import annotations

import base64
from collections.abc import Iterator

from .model import Artifact, Message, Task, file_part, text_part

WRITER_CARD = {
    "schemaVersion": "1.0",
    "name": "writer-agent",
    "description": "Drafts technical summaries and reports from source material.",
    "url": "https://writer.example.com/a2a",
    "version": "1.0.0",
    "skills": [
        {
            "id": "draft_report",
            "name": "Draft report",
            "description": "Given source material and a target length, produce a report.",
            "inputModes": ["text", "file", "data"],
            "outputModes": ["text", "artifact"],
        }
    ],
    "capabilities": {"streaming": True, "pushNotifications": False},
}

ASK_FOR_LENGTH = "Please specify targetLength as a data part."

REPORT = (
    "# Report ({length})\n"
    "\n"
    "Sources: {sources}.\n"
    "\n"
    "Topic identified, key points extracted, conclusion drafted.\n"
)


def agent_says(text: str) -> Message:
    return Message("agent", [text_part(text)])


def target_length(message: Message) -> str | None:
    """The targetLength from the first of the message's data parts that has one, or None."""
    data = [part.data for part in message.parts if part.type == "data"]
    if data and "targetLength" in data[0]:
        return data[0]["targetLength"]
    return None


class WriterAgent:
    """Serves tasks/send and follow-up messages for the skills on its Agent Card.

    Tasks are kept in self.tasks by id: task_0001, task_0002, ... in the order they are sent.
    """

    def __init__(self, card: dict = WRITER_CARD) -> None:
        self.card = card
        self.tasks: dict[str, Task] = {}

    def tasks_send(self, skill_id: str, message: Message) -> Task:
        """Start a task for one of the skills on this agent's card.

        A skill the card doesn't list is rejected before any work starts: the task goes from submitted
        straight to rejected, with an agent message that names the skill. Otherwise the task starts
        working. It completes at once if one of the message's data parts gives a targetLength (any of
        them, not only the first); if none does, it waits in input_required, with an agent message
        asking for one.
        """
        task = Task(f"task_{len(self.tasks) + 1:04d}", skill_id)
        self.tasks[task.id] = task
        task.messages.append(message)
        task.move("working")
        self._continue(task, message)
        return task

    def tasks_reply(self, task_id: str, message: Message) -> Task:
        """Answer a task that is waiting in input_required.

        The reply moves the task back to working; it then completes, or asks again and waits.
        A task in a terminal state (completed, failed, canceled or rejected) never changes again:
        a reply to one raises TaskError and leaves the task exactly as it was. Unknown ids raise KeyError.
        """
        task = self.tasks[task_id]
        task.messages.append(message)
        task.move("working")
        self._continue(task, message)
        return task

    def _continue(self, task: Task, message: Message) -> None:
        length = target_length(message)
        if length is None:
            task.move("input_required")
            task.messages.append(agent_says(ASK_FOR_LENGTH))
        else:
            self.finish(task, length)

    def finish(self, task: Task, length: str) -> None:
        """Write the report for a working task, attach it as the task's artifact and complete the task."""
        files = [
            part.file
            for message in task.messages
            if message.role == "user"
            for part in message.parts
            if part.type == "file"
        ]
        sources = ", ".join(f"{f.name} ({f.mimeType}, {len(f.content)} bytes)" for f in files) or "none"
        report = REPORT.format(length=length, sources=sources).encode("utf-8")
        task.artifact = Artifact(
            "report", "text/markdown", [file_part("report.md", "text/markdown", report)]
        )
        task.move("completed")

    def artifact_chunks(self, task_id: str, chunk_chars: int) -> Iterator[str]:
        """A completed task's report file as base64 text, cut every chunk_chars characters.

        The cuts ignore base64's 4-character groups, so a chunk can end in the middle of one.
        """
        report = self.tasks[task_id].artifact.parts[0].file.content
        encoded = base64.b64encode(report).decode("ascii")
        for start in range(0, len(encoded), chunk_chars):
            yield encoded[start : start + chunk_chars]
