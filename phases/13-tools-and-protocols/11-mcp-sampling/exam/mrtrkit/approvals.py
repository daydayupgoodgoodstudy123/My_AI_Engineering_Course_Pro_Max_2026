"""Run many MRTR interactions at once, with approvals from the user and a budget per principal.

Every decision about a round is logged as one CSV row. The log names the originating method and
the input keys; it never carries prompt text.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .host import HostError, retry_request, screen

COLUMNS = ("interaction", "round", "request_id", "method", "input_key", "decision", "tokens")


@dataclass(frozen=True)
class Interaction:
    name: str  # a label the host chose; free text
    principal: str  # the authenticated user the interaction runs as
    method: str  # tools/call, prompts/get or resources/read
    params: dict[str, Any]


@dataclass(frozen=True)
class Approval:
    interaction: str
    round: int
    approved: bool


@dataclass(frozen=True)
class Budget:
    tokens: int
    bytes: int


def round_cost(requests: dict[str, Any]) -> Budget:
    """What a round may spend: the maxTokens of its input requests, and the UTF-8 bytes of their messages' text."""
    tokens = sum(request["params"]["maxTokens"] for request in requests.values())
    size = sum(
        len(message["content"]["text"].encode("utf-8"))
        for request in requests.values()
        for message in request["params"]["messages"]
    )
    return Budget(tokens, size)


async def run_interactions(
    interactions: list[Interaction],
    *,
    send: Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]],
    approvals: AsyncIterator[Approval],
    model: Callable[[dict[str, Any]], dict[str, Any]],
    budgets: dict[str, Budget],
    ids: Iterator[int],
    max_rounds: int = 3,
) -> AsyncIterator[str]:
    """Run the interactions side by side and stream one CSV row per round as it is decided.

    send(request, principal) is awaited for every request; all interactions draw ids from ids.
    A round is screened as drive() screens it; a HostError makes it refused. Otherwise it waits
    for its Approval. Approvals arrive in any order, and one may arrive before its round has been
    asked; keep it until then. An approved round is charged round_cost against its principal's
    budget, which all of that principal's interactions share; if what is left cannot cover the
    cost, the round is over_budget instead. Only an approved round runs the model and sends a
    retry; every other decision ends its interaction. If the approvals stream ends, every round
    still waiting is denied. The run ends as soon as every interaction has ended.

    Yields the header row (COLUMNS), then one row per round: request_id is the id of the request
    whose result asked for the round, input_key the round's keys sorted and space-separated,
    decision one of approved, denied, over_budget or refused, and tokens what the round was
    charged (0 unless approved).
    """
    raise NotImplementedError
