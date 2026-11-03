"""The Rule of Two, enforced where the host runs tools."""
from __future__ import annotations

from collections.abc import Callable

from .loop import MAX_TURNS, Model, Outcome
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
    raise NotImplementedError
