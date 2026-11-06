"""Prompt-based ReAct: the model writes Thought and Action lines, the runtime writes the Observation.

    Question: What is the capital of France?
    Thought: I need to look up the capital of France.
    Action: search("capital of France")
    Observation: Paris is the capital of France.
    Thought: The answer is Paris.
    Action: finish("Paris")
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .loop import to_observation
from .tools import ToolRegistry

FORMAT_ERROR = 'error: no readable Action. Write one line: Action: tool("argument", ...)'


@dataclass
class Step:
    """One completion, as the runtime reads it."""

    text: str  # the part of the completion that counts, trailing whitespace removed
    thought: str  # the Thought, continuation lines included
    action: str | None = None  # a tool name or "finish"; None when there is no readable Action
    args: list[str] = field(default_factory=list)
    error: str = ""  # why there is no readable Action


@dataclass
class ReactRun:
    answer: str | None  # finish's argument, or None when max_steps ran out first
    steps: list[Step]


def parse_step(completion: str) -> Step:
    """Read one completion of a prompt-based ReAct model.

    - Only the runtime writes observations: a line that starts with "Observation:" ends the
      completion, and it and everything after it are dropped.
    - The first line that starts with "Action:" is the action, and it ends the completion too:
      the lines after it are dropped as well. text is what is left, trailing whitespace removed.
    - thought is everything before the Action line without the leading "Thought:", so a Thought
      can go on over several lines. Surrounding whitespace is removed.
    - An action reads name("argument", ...). Tool names may contain dots. Each argument is a
      double-quoted string with JSON escapes (\\" \\\\ \\n \\u00e9 ...); arguments are separated by
      commas, with optional spaces around them. Nothing may follow the closing parenthesis.
    - finish takes exactly one argument, the answer.

    A completion without a readable action gives a Step with action None and the reason in error.
    """
    raise NotImplementedError


def run_react(
    model: Any,
    tools: ToolRegistry,
    question: str,
    *,
    max_steps: int = 8,
    observe: Callable[[Any], str] = to_observation,
) -> ReactRun:
    """Answer a question with a prompt-based ReAct loop over a text model (model.complete(prompt)).

    Every prompt is "Question: <question>\\n" followed by one block per step so far:

        <the step's text>\\n
        Observation: <observation>\\n

    An action runs through the registry with its arguments as positional ones, and observe turns
    what the tool returned into the observation. A step without a readable action gets FORMAT_ERROR
    as its observation, and the loop goes on. finish ends the run with its argument as the answer.
    """
    raise NotImplementedError
