"""The Rule of Two, enforced where the host runs tools."""
from __future__ import annotations

from collections.abc import Callable

from .loop import MAX_TURNS, Model, Outcome, execute, rejection, tool_message
from .tools import Registry

# The result a blocked call gets, under its own call id.
BLOCKED = {"error": "blocked: the user did not confirm this action"}


def run_request(
    model: Model,
    registry: Registry,
    user_message: str,
    confirm: Callable[[dict], bool],
    *,
    max_turns: int = MAX_TURNS,
) -> Outcome:
    """run_loop for one user request, with the Rule of Two enforced.

    A request may combine at most two of: untrusted input, sensitive data and a
    consequential action. Untrusted input and sensitive data enter the request when a
    tool flagged reads_untrusted or touches_sensitive runs, and stay until the request
    ends. One request is one call of this function: the user's message and every model
    turn until the loop stops. Nothing carries over to the next request.

    A valid consequential call that would bring all three together runs only if
    confirm(call) returns True. Otherwise it is blocked: it does not run, the model gets
    BLOCKED as that call's result, and the loop goes on. Every other call runs without
    asking.
    """
    tools = registry.describe()
    history: list[dict] = [{"role": "user", "content": user_message}]
    untrusted = sensitive = False  # what this request carries so far, over all its turns
    for turn in range(1, max_turns + 1):
        decision = model(history, tools)
        if "content" in decision:
            history.append({"role": "assistant", "content": decision["content"]})
            return Outcome(decision["content"], "final", turn, history)
        history.append({"role": "assistant", "tool_calls": decision["tool_calls"]})
        for call in decision["tool_calls"]:
            result = rejection(registry, call)
            if result is None:
                tool = registry.get(call["name"])
                with_untrusted = untrusted or tool.reads_untrusted
                with_sensitive = sensitive or tool.touches_sensitive
                if tool.consequential and with_untrusted and with_sensitive and not confirm(call):
                    result = dict(BLOCKED)
                else:
                    untrusted, sensitive = with_untrusted, with_sensitive
                    result = execute(tool, call["arguments"])
            history.append(tool_message(call, result))
    return Outcome(None, "max_turns", max_turns, history)
