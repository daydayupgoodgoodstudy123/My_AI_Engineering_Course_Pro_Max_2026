"""Main context: the part of the prompt the model always sees."""
from __future__ import annotations

from dataclasses import dataclass, field

from .tokens import approx_tokens


@dataclass(frozen=True)
class Message:
    role: str
    text: str
    turn: int


@dataclass
class MainContext:
    """Pinned core sections, a running summary, and the most recent messages.

    Messages are numbered 1, 2, 3, ... as they arrive; turn is the number of the latest one.
    max_tokens budgets the conversation part of the prompt: each message costs
    approx_tokens(message.text) and the summary costs approx_tokens(summary). Core sections
    are capped separately and do not count.

    Paging out moves the oldest messages to recall, one at a time, until the context fits
    max_tokens again. The newest message always stays, even when it alone is over budget.
    conversation_search still finds what is in recall.
    """

    max_tokens: int = 2048
    core: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    messages: list[Message] = field(default_factory=list)
    recall: list[Message] = field(default_factory=list)
    turn: int = 0

    def append(self, role: str, text: str) -> list[Message]:
        """Add a message, then page out what no longer fits. Returns the paged-out messages."""
        self.push(role, text)
        return self.evict()

    def push(self, role: str, text: str) -> Message:
        """Add a message without paging anything out."""
        self.turn += 1
        message = Message(role, text, self.turn)
        self.messages.append(message)
        return message

    def evict(self) -> list[Message]:
        """Page out the oldest messages until the context fits. Returns them, oldest first."""
        paged: list[Message] = []
        while self.tokens() > self.max_tokens and len(self.messages) > 1:
            message = self.messages.pop(0)
            self.recall.append(message)
            paged.append(message)
        return paged

    def tokens(self) -> int:
        """What the summary and the messages in context cost right now."""
        return approx_tokens(" ".join([self.summary] + [m.text for m in self.messages]))

    def render(self) -> str:
        """The prompt text the model sees."""
        parts = ["[core]"]
        parts += [f"  {name}: {text}" for name, text in self.core.items()]
        if self.summary:
            parts += ["[summary]", f"  {self.summary}"]
        parts.append("[messages]")
        parts += [f"  {m.role}: {m.text}" for m in self.messages]
        return "\n".join(parts)
