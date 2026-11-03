"""A scripted stand-in for the model, so the loop runs offline and deterministically."""
from __future__ import annotations

import copy
from typing import Any

# One script entry per model turn: the final answer, or the tool calls to make.
Entry = str | list[tuple[str, dict]]


class ScriptedModel:
    """Plays back a script, one entry per model turn.

    An entry is the final answer (a str) or the tool calls to make (a list of
    (name, arguments) pairs). Calls are numbered call_1, call_2, ... across the
    whole conversation. With repeat=True the last entry is played again and again.

    Like a provider's API, the model insists that every call it made is answered:
    at the start of each turn it reads the result of each of its previous calls
    from the tool message that carries that call's id.

    requests: the history it was given, one copy per turn.
    observed: the result it read for each call id.
    tools: the tool declarations it was given on its latest turn.
    """

    LIMIT = 100

    def __init__(self, script: list[Entry], *, repeat: bool = False) -> None:
        self.script = list(script)
        self.repeat = repeat
        self.requests: list[list[dict]] = []
        self.observed: dict[str, Any] = {}
        self.tools: list[dict] = []
        self._waiting: list[str] = []
        self._made = 0

    def __call__(self, history: list[dict], tools: list[dict]) -> dict:
        if len(self.requests) == self.LIMIT:
            raise RuntimeError(f"the model was asked more than {self.LIMIT} times")
        self.requests.append(copy.deepcopy(history))
        self.tools = tools
        answers = {m["id"]: m["content"] for m in history if m["role"] == "tool"}
        for call_id in self._waiting:
            self.observed[call_id] = answers[call_id]
        self._waiting = []

        turn = len(self.requests) - 1
        if turn < len(self.script):
            entry = self.script[turn]
        elif self.repeat:
            entry = self.script[-1]
        else:
            raise RuntimeError("the script has no entry for this turn")
        if isinstance(entry, str):
            return {"content": entry}
        calls = []
        for name, arguments in entry:
            self._made += 1
            calls.append({"id": f"call_{self._made}", "name": name, "arguments": copy.deepcopy(arguments)})
        self._waiting = [call["id"] for call in calls]
        return {"tool_calls": calls}
