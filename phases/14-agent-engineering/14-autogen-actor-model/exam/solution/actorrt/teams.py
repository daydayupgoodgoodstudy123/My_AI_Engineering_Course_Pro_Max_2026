"""Teams on the actor runtime, after AgentChat's RoundRobinGroupChat and SelectorGroupChat.

A team is itself an actor, the manager. It asks one participant at a time to speak with a "speak"
message whose body is the conversation so far: a list of [source, text] pairs that starts with
["user", task]. The participant answers the manager with a "said" message whose body is its text.
A "said" from anyone but the participant the manager is waiting for is ignored.

A chat stops right after a participant's message that contains the stop word as a whole word
(case-sensitive), or as soon as it holds max_messages messages, the task included. When one
message does both, the reason is "stop_word". The task is never checked for the stop word: it is
the instruction, and often names it. If the runtime goes idle before the chat stops (a participant
failed and never answered), the reason is "stalled".
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .runtime import Actor, Message, Runtime


@dataclass
class ChatResult:
    messages: list[tuple[str, str]]  # (source, text), the task first as ("user", task)
    stop_reason: str  # "stop_word", "max_messages" or "stalled"
    selections: list[tuple[str, str]]  # (speaker, how the speaker was chosen), one per turn


class RoundRobinGroupChat(Actor):
    """Participants take turns in a fixed rotation, starting with the first one.

    Every turn is chosen by "rotation".
    """

    def __init__(
        self,
        runtime: Runtime,
        participants: list[str],
        *,
        max_messages: int = 10,
        stop_word: str = "TERMINATE",
        name: str = "team",
    ) -> None:
        super().__init__(name)
        if not participants or len(set(participants)) != len(participants):
            raise ValueError("participants must be distinct names")
        self.runtime = runtime
        self.participants = list(participants)
        self.max_messages = max_messages
        self.stop_word = stop_word
        self._messages: list[tuple[str, str]] = []
        self._selections: list[tuple[str, str]] = []
        self._stop_reason: str | None = None
        self._waiting: str | None = None
        self._stop = re.compile(rf"\b{re.escape(stop_word)}\b")
        runtime.register(self)

    def run(self, task: str) -> ChatResult:
        """Run one chat on task until it stops, and return it."""
        self._messages, self._selections = [], []
        self._stop_reason = self._waiting = None
        self.runtime.send("user", self.name, "task", task)
        while self._stop_reason is None and not self.runtime.run_until_idle():
            pass
        return ChatResult(list(self._messages), self._stop_reason or "stalled", list(self._selections))

    def receive(self, message: Message, runtime: Runtime) -> None:
        if message.topic == "task":
            self._messages.append(("user", message.body))
            self._next_turn(runtime)
        elif message.topic == "said" and message.sender == self._waiting:
            self._waiting = None
            self._messages.append((message.sender, message.body))
            if self._stop.search(message.body):
                self._stop_reason = "stop_word"
            else:
                self._next_turn(runtime)

    def select(self, last: str | None) -> tuple[str, str]:
        """The next speaker after last (None before the first turn), and how it was chosen."""
        return self._after(last), "rotation"

    def _after(self, last: str | None) -> str:
        """The participant after last in the rotation; the first one before any turn."""
        if last is None:
            return self.participants[0]
        return self.participants[(self.participants.index(last) + 1) % len(self.participants)]

    def _next_turn(self, runtime: Runtime) -> None:
        if len(self._messages) >= self.max_messages:
            self._stop_reason = "max_messages"
            return
        last = self._messages[-1][0] if len(self._messages) > 1 else None
        speaker, reason = self.select(last)
        self._selections.append((speaker, reason))
        self._waiting = speaker
        runtime.send(self.name, speaker, "speak", [list(m) for m in self._messages])


class SelectorGroupChat(RoundRobinGroupChat):
    """A selector picks every speaker from the conversation so far, the way a model would.

    selector(messages, participants) is called before each turn with the conversation as
    (source, text) tuples and the participant names in order, and returns a name. The answer counts
    once surrounding whitespace is stripped; it must then be a participant's exact name. A name
    that is not a participant falls back to the participant after the last speaker in the rotation
    ("unknown"), and so does the last speaker again unless allow_repeated_speaker is set
    ("repeat"). Any other answer is the speaker ("selector").
    """

    def __init__(
        self,
        runtime: Runtime,
        participants: list[str],
        selector: Callable[[list[tuple[str, str]], list[str]], str],
        *,
        allow_repeated_speaker: bool = False,
        **options,
    ) -> None:
        if len(participants) < 2 and not allow_repeated_speaker:
            raise ValueError("without repeats a selector chat needs at least two participants")
        self.selector = selector
        self.allow_repeated_speaker = allow_repeated_speaker
        super().__init__(runtime, participants, **options)

    def select(self, last: str | None) -> tuple[str, str]:
        choice = self.selector(list(self._messages), list(self.participants)).strip()
        if choice not in self.participants:
            return self._after(last), "unknown"
        if choice == last and not self.allow_repeated_speaker:
            return self._after(last), "repeat"
        return choice, "selector"
