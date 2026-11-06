"""Scripted stand-ins for the model behind an agent, so that every run is offline and repeatable."""
from __future__ import annotations

from typing import Any


class ScriptedLLM:
    """Answers with its replies in order, one per call, and records every input it was given.

    Use it as an Agent's fn. A call after the last reply is an error: the crew asked the
    model more often than the script allows.
    """

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.inputs: list[Any] = []

    def __call__(self, prompt: Any) -> Any:
        self.inputs.append(prompt)
        if len(self.inputs) > len(self.replies):
            raise RuntimeError(f"no scripted reply left for call {len(self.inputs)}")
        return self.replies[len(self.inputs) - 1]


class Unscripted(Exception):
    """A KeyedLLM was sent a prompt its script has no reply for."""


class KeyedLLM:
    """Answers by prompt, the way the lesson's mock LLM keys its replies off the input, and records
    every input it was given.

    Use it as an Agent's fn. A prompt the script has no reply for is Unscripted: the agent was
    sent something the script did not expect.
    """

    def __init__(self, replies: dict[str, Any]) -> None:
        self.replies = dict(replies)
        self.inputs: list[Any] = []

    def __call__(self, prompt: Any) -> Any:
        self.inputs.append(prompt)
        if prompt not in self.replies:
            raise Unscripted(f"no reply scripted for {prompt!r}")
        return self.replies[prompt]
