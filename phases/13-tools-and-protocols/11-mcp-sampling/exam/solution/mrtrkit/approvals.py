"""Run many MRTR interactions at once, with approvals from the user and a budget per principal.

Every decision about a round is logged as one CSV row. The log names the originating method and
the input keys; it never carries prompt text.
"""
from __future__ import annotations

import csv
import io
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
    left = dict(budgets)
    waiting: dict[tuple[str, int], tuple[Interaction, int, Any, dict[str, Any], str]] = {}
    early: dict[tuple[str, int], bool] = {}

    async def ask(it: Interaction, number: int, request: dict[str, Any]) -> str | None:
        """Send a request; park the round its result asks for. Returns a refused row, if any."""
        response = await send(request, it.principal)
        result = response.get("result")
        if not isinstance(result, dict) or result.get("resultType") != "input_required":
            return None
        try:
            requests = screen(it.method, it.params, result, number, max_rounds)
        except HostError:
            keys = " ".join(sorted(result.get("inputRequests", {})))
            return _row(it.name, number, request["id"], it.method, keys, "refused", 0)
        waiting[(it.name, number)] = (it, number, request["id"], requests, result["requestState"])
        return None

    async def decide(slot: tuple[str, int], approved: bool) -> AsyncIterator[str]:
        it, number, request_id, requests, state = waiting.pop(slot)
        keys = " ".join(sorted(requests))
        cost = round_cost(requests)
        have = left.get(it.principal, Budget(0, 0))
        if not approved:
            yield _row(it.name, number, request_id, it.method, keys, "denied", 0)
            return
        if cost.tokens > have.tokens or cost.bytes > have.bytes:
            yield _row(it.name, number, request_id, it.method, keys, "over_budget", 0)
            return
        left[it.principal] = Budget(have.tokens - cost.tokens, have.bytes - cost.bytes)
        yield _row(it.name, number, request_id, it.method, keys, "approved", cost.tokens)
        answers = {key: model(request["params"]) for key, request in requests.items()}
        refused = await ask(it, number + 1, retry_request(next(ids), it.method, it.params, answers, state))
        if refused is not None:
            yield refused
        following = (it.name, number + 1)
        if following in waiting and following in early:
            async for row in decide(following, early.pop(following)):
                yield row

    yield _row(*COLUMNS)
    for it in interactions:
        first = {"jsonrpc": "2.0", "id": next(ids), "method": it.method, "params": it.params}
        refused = await ask(it, 1, first)
        if refused is not None:
            yield refused
    if not waiting:
        return
    async for approval in approvals:
        slot = (approval.interaction, approval.round)
        if slot in waiting:
            async for row in decide(slot, approval.approved):
                yield row
        else:
            early[slot] = approval.approved
        if not waiting:
            return
    for slot in list(waiting):
        async for row in decide(slot, False):
            yield row


def _row(*fields: Any) -> str:
    out = io.StringIO()
    csv.writer(out).writerow(fields)
    return out.getvalue()
