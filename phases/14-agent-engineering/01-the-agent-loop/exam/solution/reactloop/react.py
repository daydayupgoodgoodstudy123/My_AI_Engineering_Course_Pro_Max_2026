"""Prompt-based ReAct: the model writes Thought and Action lines, the runtime writes the Observation.

    Question: What is the capital of France?
    Thought: I need to look up the capital of France.
    Action: search("capital of France")
    Observation: Paris is the capital of France.
    Thought: The answer is Paris.
    Action: finish("Paris")
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .loop import FINISH, to_observation
from .messages import ToolCall
from .tools import ToolRegistry

FORMAT_ERROR = 'error: no readable Action. Write one line: Action: tool("argument", ...)'

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_STRING = json.JSONDecoder()


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
    kept: list[str] = []
    action_line = None
    for line in completion.split("\n"):
        if line.startswith("Observation:"):
            break
        kept.append(line)
        if line.startswith("Action:"):
            action_line = kept.pop()
            break
    thought = "\n".join(kept).strip()
    if thought.startswith("Thought:"):
        thought = thought[len("Thought:") :].strip()
    text = "\n".join(kept + ([action_line] if action_line is not None else [])).rstrip()
    if action_line is None:
        return Step(text, thought, error="no Action line")
    try:
        name, args = _read_action(action_line[len("Action:") :].strip())
    except ValueError as e:
        return Step(text, thought, error=str(e))
    return Step(text, thought, name, args)


def _read_action(source: str) -> tuple[str, list[str]]:
    match = _NAME.match(source)
    if match is None:
        raise ValueError("the action has no tool name")
    pos = match.end()
    if source[pos : pos + 1] != "(":
        raise ValueError("expected ( after the tool name")
    pos = _skip(source, pos + 1)
    args: list[str] = []
    if source[pos : pos + 1] == ")":
        pos += 1
    else:
        while True:
            if source[pos : pos + 1] != '"':
                raise ValueError("arguments are double-quoted strings")
            value, pos = _STRING.raw_decode(source, pos)
            args.append(value)
            pos = _skip(source, pos)
            if source[pos : pos + 1] == ",":
                pos = _skip(source, pos + 1)
                continue
            if source[pos : pos + 1] == ")":
                pos += 1
                break
            raise ValueError("expected , or ) after an argument")
    if source[pos:].strip():
        raise ValueError("text after the closing parenthesis")
    name = match.group()
    if name == FINISH and len(args) != 1:
        raise ValueError("finish takes exactly one argument")
    return name, args


def _skip(source: str, pos: int) -> int:
    while source[pos : pos + 1].isspace():
        pos += 1
    return pos


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
    prompt = f"Question: {question}\n"
    steps: list[Step] = []
    for _ in range(max_steps):
        step = parse_step(model.complete(prompt))
        steps.append(step)
        if step.action == FINISH:
            return ReactRun(step.args[0], steps)
        if step.action is None:
            observation = FORMAT_ERROR
        else:
            observation = observe(tools.dispatch(ToolCall(step.action, list(step.args))))
        prompt += f"{step.text}\nObservation: {observation}\n"
    return ReactRun(None, steps)
