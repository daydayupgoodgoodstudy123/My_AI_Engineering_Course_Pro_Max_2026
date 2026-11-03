"""One authorization decision, before the transport turns it into an HTTP response."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    """The answer to one request.

    decision is "allow", "refuse" (an authorization refusal: the credential is bad for this
    request) or "error" (an operational error: an identity dependency could not answer).
    Neither of the last two reaches a tool. health is "ok" or "degraded".
    """

    decision: str
    status: int
    reason: str
    health: str = "ok"
    www_authenticate: str | None = None
    claims: dict | None = field(default=None, compare=False, repr=False)

    @classmethod
    def allow(cls, claims: dict, health: str = "ok") -> Outcome:
        return cls("allow", 200, "ok", health, None, claims)

    @classmethod
    def error(cls, reason: str) -> Outcome:
        """An operational error: HTTP 503 and degraded health. The credential was never judged,
        so there is no WWW-Authenticate challenge."""
        return cls("error", 503, reason, "degraded")
