"""Load balancing inside an alias: a weighted rotation, data residency and a retry budget."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .gateway import AllProvidersFailed, RequestRejected
from .providers import Attempt, ProviderError, Reply


@dataclass(frozen=True)
class Deployment:
    """One place a model is served: a provider endpoint in one region."""

    name: str
    model: str
    region: str
    weight: int = 1  # share of first picks; 0 means fallback only
    retries: int = 0  # extra tries of this deployment after a 5xx


@dataclass(frozen=True)
class Pool:
    """An alias's deployments in priority order, and how many tries one request may make."""

    deployments: tuple[Deployment, ...]
    max_attempts: int


class NoEligibleDeployment(Exception):
    """None of the alias's deployments may serve the caller's region."""


class RetryBudgetExhausted(Exception):
    """A request made max_attempts tries and still needed another."""

    def __init__(self, alias: str, attempts: tuple[Attempt, ...]) -> None:
        super().__init__(f"{alias} gave up after {len(attempts)} tries")
        self.alias = alias
        self.attempts = attempts


@dataclass(frozen=True)
class Outcome:
    """A served request: the deployment that served it, its reply, and every try in order."""

    deployment: Deployment
    reply: Reply
    attempts: tuple[Attempt, ...]


# call(deployment, messages) returns the reply or raises ProviderError
Call = Callable[[Deployment, list[dict]], Reply]


class Router:
    """Plans and runs requests over each alias's pool of deployments."""

    def __init__(self, pools: dict[str, Pool]) -> None:
        self.pools = pools

    def plan(self, alias: str, region: str | None = None) -> list[Deployment]:
        """The deployments one request will try, in order. Each call advances the alias's rotation.

        When region is given, only deployments in that region are eligible (EU users stay in
        the EU); if none is, raise NoEligibleDeployment. The first deployment is picked by smooth
        weighted round robin over the eligible deployments: each pick adds every candidate's
        weight to its running score, takes the highest score (the earliest listed on a tie) and
        subtracts the candidates' total weight from the winner's score. A deployment with
        weight 0 is never picked first; if every eligible weight is 0, the plan is simply the
        listed order. The other eligible deployments follow the first in their listed order.
        Each alias keeps one rotation per region (None is a region of its own), starting with
        every score at 0.
        """
        raise NotImplementedError

    def send(self, alias: str, messages: list[dict], call: Call, region: str | None = None) -> Outcome:
        """Serve one request by following one plan.

        Each deployment is tried up to 1 + retries times. A 5xx moves on: to another try of the
        same deployment while it has retries left, then to the next deployment. Any other
        ProviderError is raised at once as RequestRejected. Every try counts against the pool's
        max_attempts, shared by the whole cascade: once that many tries have been made and
        another is needed, raise RetryBudgetExhausted with the tries made. If the plan runs out
        first, raise AllProvidersFailed. Attempts name the deployment tried.
        """
        raise NotImplementedError
