"""The routing gateway: one OpenAI-shaped chat request in, an alias's fallback chain behind it."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from .budget import Budget
from .guard import redact_messages
from .pricing import PRICES, Price, cost_micros
from .providers import Attempt, ProviderError, Reply

# alias -> fallback chain, in priority order
ROUTES = {
    "smart": ["openai/gpt-4o", "anthropic/claude-sonnet", "google/gemini-pro"],
    "fast": ["openai/gpt-4o-mini", "anthropic/claude-haiku"],
}

# send(model, messages) returns the provider's reply or raises ProviderError
Send = Callable[[str, list[dict]], Reply]


class RequestRejected(Exception):
    """A provider rejected the request itself (a 4xx). Another model will not fix it."""

    def __init__(self, error: ProviderError) -> None:
        super().__init__(str(error))
        self.model = error.model
        self.status = error.status


class AllProvidersFailed(Exception):
    """Every model the request could go to failed with a 5xx."""

    def __init__(self, alias: str, attempts: tuple[Attempt, ...]) -> None:
        tried = ", ".join(f"{a.model} {a.status}" for a in attempts) or "nothing"
        super().__init__(f"every model for {alias} failed: {tried}")
        self.alias = alias
        self.attempts = attempts


@dataclass(frozen=True)
class Invocation:
    """A served request: who sent it, what was tried, what served it and what it cost."""

    team: str
    alias: str
    at: datetime
    attempts: tuple[Attempt, ...]
    served_model: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    redacted: bool
    text: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Gateway:
    """Serves chat requests for teams through model aliases."""

    def __init__(
        self,
        send: Send,
        budget: Budget,
        *,
        routes: dict[str, list[str]] = ROUTES,
        prices: dict[str, Price] = PRICES,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.send = send
        self.budget = budget
        self.routes = routes
        self.prices = prices
        self.clock = clock

    def route(self, team: str, alias: str, messages: list[dict]) -> Invocation:
        """Serve one chat request for a team through the alias's fallback chain.

        The team's budget is checked before anything is sent, and PII is redacted from every
        message before any provider sees it. The chain is tried in order: a 5xx moves on to the
        next model; any other provider error means the request itself is bad, and it is raised
        at once as RequestRejected without trying another model. If every model answers with a
        5xx, raise AllProvidersFailed. A served request is charged to the team, at the prices of
        the model that served it, in the month the request arrived.
        """
        now = self.clock()
        self.budget.check(team, now)
        chain = self.routes[alias]
        price = self.prices[chain[0]]
        prepared, redacted = redact_messages(messages)
        attempts: list[Attempt] = []
        for model in chain:
            try:
                reply = self.send(model, prepared)
            except ProviderError as err:
                attempts.append(Attempt(model, err.status))
                continue
            attempts.append(Attempt(model, 200))
            break
        else:
            raise AllProvidersFailed(alias, tuple(attempts))
        cost = cost_micros(price, reply.input_tokens, reply.output_tokens)
        self.budget.charge(team, now, cost)
        return Invocation(
            team=team,
            alias=alias,
            at=now,
            attempts=tuple(attempts),
            served_model=model,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            cost_micros=cost,
            redacted=redacted,
            text=reply.text,
        )
