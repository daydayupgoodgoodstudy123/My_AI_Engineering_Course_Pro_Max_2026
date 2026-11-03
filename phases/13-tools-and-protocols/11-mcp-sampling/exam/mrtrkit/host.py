"""The host side of MRTR: answer input_required results with the client's own model, safely.

The host is the trust boundary for embedded requests. It fulfils input only for methods that may
ask for it, only for requests it declared a capability for, never for more rounds than its cap,
and only after the user approves. The server's requestState goes back untouched.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from .protocol import CAPABILITIES_META, McpError

MRTR_METHODS = ("tools/call", "prompts/get", "resources/read")
# input request method -> the client capability it needs; the host fulfils nothing else
FULFILS = {"sampling/createMessage": "sampling"}


class HostError(Exception):
    """The host stopped an interaction. reason is method, rounds, capability, context or denied."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def screen(
    method: str, params: dict[str, Any], result: dict[str, Any], round_no: int, max_rounds: int
) -> dict[str, Any]:
    """Check an input_required result before the user or the model sees any of it.

    Returns the result's inputRequests. Raises HostError with reason
      method      if the original method may not ask for input (only tools/call, prompts/get and
                  resources/read may);
      rounds      if round_no (1 for the first input_required) is past max_rounds;
      capability  if an input request is not one the host fulfils, or needs a capability that
                  params' own _meta does not declare;
      context     if an input request asks for an includeContext other than "none".
    """
    raise NotImplementedError


def retry_request(
    request_id: int, method: str, params: dict[str, Any], answers: dict[str, Any], state: str
) -> dict[str, Any]:
    """The request that retries the original call with one round's answers.

    Same method and the original params (name, arguments, _meta), plus this round's answers as
    inputResponses and this round's requestState exactly as the server sent it. params itself is
    left as it was.
    """
    raise NotImplementedError


def drive(
    send: Callable[[dict[str, Any]], dict[str, Any]],
    method: str,
    params: dict[str, Any],
    *,
    approve: Callable[[str, dict[str, Any]], bool],
    model: Callable[[dict[str, Any]], dict[str, Any]],
    ids: Iterator[int],
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Run one MRTR interaction and return its final result.

    send(request) returns the JSON-RPC response; every request takes the next id from ids.
    Each input_required round is screened first. Then the user approves every input request of
    the round, approve(key, input_request); only when all are approved does the model answer each
    one, model(input_request["params"]), with the params exactly as the server sent them.
    An error response raises McpError; a screen failure or a denial raises HostError.
    """
    raise NotImplementedError
