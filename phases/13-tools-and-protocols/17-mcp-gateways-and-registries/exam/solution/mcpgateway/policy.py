"""Runtime policy: the gateway's allow or deny decision, made again for every call."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass


class PolicyUnavailable(Exception):
    """The policy service could not answer."""


@dataclass(frozen=True)
class Policy:
    """One version of the policy service's document.

    `roles` holds each principal's current roles, keyed by (issuer, principal).
    `tool_roles` holds the roles that may call each public tool. `stale_reads` lists
    the public read tools approved to run on a last-known policy while the service is
    down. `quarantined` lists backends whose state-changing calls are on hold.
    """

    version: str
    roles: Mapping[tuple[str, str], frozenset[str]]
    tool_roles: Mapping[str, frozenset[str]]
    stale_reads: frozenset[str] = frozenset()
    quarantined: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CallContext:
    """What the gateway knows about one call when it asks for a decision."""

    principal: str
    issuer: str
    tenant: str  # the principal's tenant
    token_roles: frozenset[str]  # roles the bearer token claimed when it was issued
    tool: str  # public tool name
    backend: str
    operation: str  # "read" or "write"
    classification: str  # "public", "internal" or "sensitive"
    target_tenant: str | None  # the tenant the call's arguments name, if any
    admitted: bool  # the backend's admission record is approved
    pinned: bool  # the live descriptor matches the admitted pin
    healthy: bool  # current backend health


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    policy_version: str | None
    path: str  # "live", "last_known" or "fail_closed"


class RolePolicy:
    """A fixed table of the roles each public tool needs, checked against the token's roles."""

    version = "static"

    def __init__(self, tool_roles: Mapping[str, Iterable[str]]) -> None:
        self.tool_roles = {tool: frozenset(roles) for tool, roles in tool_roles.items()}

    def decide(self, ctx: CallContext) -> Decision:
        if ctx.token_roles & self.tool_roles.get(ctx.tool, frozenset()):
            return Decision(True, "allowed", self.version, "live")
        return Decision(False, "role", self.version, "live")


class PolicyEngine:
    """Runtime policy backed by a policy service (`fetch`) and the gateway's clock."""

    def __init__(
        self,
        fetch: Callable[[], Policy],
        clock: Callable[[], float],
        last_known_ttl_s: float = 30.0,
    ) -> None:
        self.fetch = fetch
        self.clock = clock
        self.last_known_ttl_s = last_known_ttl_s
        self._last_known: tuple[Policy, float] | None = None

    def decide(self, ctx: CallContext) -> Decision:
        """Decide one call.

        Every decision asks the policy service (`fetch()`); nothing is cached per
        principal, connection or session. The rules apply in this order, and the first
        that fails is the reason:

          "admission"   the backend's admission record is not approved
          "role"        the principal's current roles (policy.roles) include none of
                        policy.tool_roles[ctx.tool]; the token's roles may be out of date
          "pin"         the live descriptor does not match the admitted pin
          "tenant"      the arguments name a tenant other than the principal's
          "health"      the backend is unhealthy
          "quarantine"  a write to a backend the policy quarantines

        A call that passes them all is allowed, reason "allowed". The decision carries
        the version of the policy it used and its path, "live".

        When `fetch()` raises PolicyUnavailable, the failure policy goes by operation
        class. A read of public data whose tool the last-known policy lists in
        `stale_reads` may use that policy while it is less than `last_known_ttl_s`
        old, counted from the fetch that returned it: the same rules apply, with path
        "last_known" and that policy's version. Every other call, writes and sensitive
        reads included, fails closed: reason "policy_unavailable", path "fail_closed",
        no version.
        """
        now = self.clock()
        try:
            policy = self.fetch()
        except PolicyUnavailable:
            if self._may_use_last_known(ctx, now):
                return self._evaluate(self._last_known[0], ctx, "last_known")
            return Decision(False, "policy_unavailable", None, "fail_closed")
        self._last_known = (policy, now)
        return self._evaluate(policy, ctx, "live")

    def _may_use_last_known(self, ctx: CallContext, now: float) -> bool:
        if self._last_known is None:
            return False
        policy, fetched_at = self._last_known
        return (
            ctx.operation == "read"
            and ctx.classification == "public"
            and ctx.tool in policy.stale_reads
            and now - fetched_at < self.last_known_ttl_s
        )

    @staticmethod
    def _evaluate(policy: Policy, ctx: CallContext, path: str) -> Decision:
        roles = policy.roles.get((ctx.issuer, ctx.principal), frozenset())
        checks = (
            ("admission", ctx.admitted),
            ("role", bool(roles & policy.tool_roles.get(ctx.tool, frozenset()))),
            ("pin", ctx.pinned),
            ("tenant", ctx.target_tenant is None or ctx.target_tenant == ctx.tenant),
            ("health", ctx.healthy),
            ("quarantine", not (ctx.operation == "write" and ctx.backend in policy.quarantined)),
        )
        for reason, ok in checks:
            if not ok:
                return Decision(False, reason, policy.version, path)
        return Decision(True, "allowed", policy.version, path)
