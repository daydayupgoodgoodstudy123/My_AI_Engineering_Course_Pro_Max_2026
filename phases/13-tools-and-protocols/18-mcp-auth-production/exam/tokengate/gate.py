"""The gate in front of every tool call: one declared outcome per request."""
from __future__ import annotations

from dataclasses import dataclass

from .introspection import IntrospectionCache
from .outcome import Outcome
from .resource import ResourceServer


@dataclass(frozen=True)
class IssuerPolicy:
    """How this deployment checks one issuer's tokens. Configuration, never read from a token."""

    mode: str  # "jwt" or "introspection"
    algorithms: tuple[str, ...] = ("HS256",)  # jwt: the header alg values this issuer signs with
    refresh_interval: float = 300.0  # jwt: period of the scheduled JWKS refresh, in seconds
    stale_window: float = 600.0  # jwt: how long after a missed refresh cached keys stay usable
    cache_max_age: float | None = None  # introspection: the issuer's cache guidance, in seconds


class Gate:
    """The MCP server's front door. Every request gets one outcome before any tool runs."""

    def __init__(
        self,
        server: ResourceServer,
        policies: dict[str, IssuerPolicy],
        introspection: IntrospectionCache,
        *,
        opaque_issuer: str | None = None,
    ) -> None:
        for issuer, policy in policies.items():
            if issuer not in server.prm.authorization_servers:
                raise ValueError(f"{issuer} is not in the protected-resource metadata")
            if policy.mode not in ("jwt", "introspection"):
                raise ValueError(f"unknown validation mode {policy.mode!r}")
        if opaque_issuer is not None and getattr(policies.get(opaque_issuer), "mode", None) != "introspection":
            raise ValueError("the opaque-token issuer must be configured for introspection")
        self.server = server
        self.policies = dict(policies)
        self.introspection = introspection
        self.opaque_issuer = opaque_issuer

    def check(self, token: str, required_scope: str) -> Outcome:
        """Decide one request.

        The outcome is one of:
          allow   200      the token is good for this resource and this scope;
          refuse  401/403  an authorization refusal, built with self.server.prm.refuse;
          error   503      an operational error (Outcome.error): an identity dependency failed.
        health is "degraded" for every error, and for a decision that used JWKS keys fetched
        more than refresh_interval seconds ago; otherwise it is "ok".

        In order:
        1. The clock must read a finite number; otherwise error "clock unavailable".
        2. A token that does not parse as a JWT is opaque and goes to opaque_issuer's
           introspection (refuse "malformed" when there is no opaque issuer).
        3. A JWT's iss must be a string naming a configured issuer ("iss not allowed"). That
           issuer's policy picks the path, whatever the token looks like.
        4. Introspection: self.introspection.lookup, with the policy's cache_max_age. A failure
           to answer is error "introspection unavailable". The response needs "active": true
           ("inactive"), well-formed claims as in step 5 ("malformed"), aud equal to this
           resource ("audience mismatch"), now before exp ("expired"), and the scope (403).
        5. JWT: the header alg must be one of the policy's algorithms ("alg not allowed"). exp
           must be an int and not a bool, and scope a str when present ("malformed"). Keys
           cached more than refresh_interval + stale_window seconds ago are not used: error
           "jwks stale". Then self.server.validate decides, and a JWKS fetch that fails inside it
           is error "jwks unavailable". Apart from validate's one refresh on a miss, the gate
           never fetches keys: refreshing them is the scheduled job's work.
        """
        raise NotImplementedError
