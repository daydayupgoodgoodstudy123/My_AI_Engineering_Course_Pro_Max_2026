"""The executor's gate: the only place a reviewed action is handed to the runner."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .policy import ActionRequest, ReviewDecision, SandboxPolicy, Verdict, review_action


@dataclass(frozen=True)
class ActionRecord:
    """What the runner receives for one action: the reviewed, normalized values only."""

    kind: str
    target: str | None
    origin: str | None
    argv: tuple[str, ...]


@dataclass(frozen=True)
class GateResult:
    decision: ReviewDecision
    ran: bool


class ActionGate:
    """Hands an action to the runner only when review_action allows it.

    A require-approval decision waits for an approver: once someone has accepted the
    consequence, the caller submits the request again with approved=True. A deny is final.
    """

    def __init__(self, policy: SandboxPolicy, runner: Callable[[ActionRecord], None]) -> None:
        self.policy = policy
        self.runner = runner

    def submit(self, request: ActionRequest) -> GateResult:
        decision = review_action(self.policy, request)
        if decision.verdict is Verdict.DENY:
            return GateResult(decision, False)
        record = ActionRecord(
            request.kind, decision.normalized_target, decision.normalized_origin, request.command
        )
        self.runner(record)
        return GateResult(decision, True)
