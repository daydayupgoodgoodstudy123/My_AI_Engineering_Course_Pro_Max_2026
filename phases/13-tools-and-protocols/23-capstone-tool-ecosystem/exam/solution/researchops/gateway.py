"""The authorization gateway in front of the research server (the lesson's gateway_call).

A static token table stands in for OAuth, and scope membership stands in for gateway policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Grant:
    actor: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class AuditEntry:
    actor: str
    tool: str
    decision: str  # "allow" or "deny"


# generate_report reads the papers it summarizes and writes the report.
REQUIRED_SCOPES: dict[str, frozenset[str]] = {
    "arxiv_search": frozenset({"research:read"}),
    "generate_report": frozenset({"research:read", "research:write"}),
}


@dataclass
class Gateway:
    """Checks every request before it reaches the research server.

    A request needs a known bearer token, or it gets {"error": "unauthenticated"}. A tools/call
    also needs every scope REQUIRED_SCOPES lists for its tool; without them it gets
    {"error": "insufficient_scope", "scope": "<missing scopes, sorted, space separated>"}, and a
    tool the table does not list gets {"error": "unknown_tool"}. A refused request never reaches
    the server. Every tools/call decision is appended to audit.
    """

    server: object  # anything with handle(request) -> response
    grants: dict[str, Grant]
    required: dict[str, frozenset[str]] = field(default_factory=lambda: dict(REQUIRED_SCOPES))
    audit: list[AuditEntry] = field(default_factory=list)

    def handle(self, token: str, request: dict) -> dict:
        grant = self.grants.get(token)
        if grant is None:
            return {"error": "unauthenticated"}
        if request.get("method") == "tools/call":
            tool = str(request.get("params", {}).get("name"))
            required = self.required.get(tool)
            if required is None:
                self.audit.append(AuditEntry(grant.actor, tool, "deny"))
                return {"error": "unknown_tool"}
            missing = required - grant.scopes
            if missing:
                self.audit.append(AuditEntry(grant.actor, tool, "deny"))
                return {"error": "insufficient_scope", "scope": " ".join(sorted(missing))}
            self.audit.append(AuditEntry(grant.actor, tool, "allow"))
        return self.server.handle(request)
