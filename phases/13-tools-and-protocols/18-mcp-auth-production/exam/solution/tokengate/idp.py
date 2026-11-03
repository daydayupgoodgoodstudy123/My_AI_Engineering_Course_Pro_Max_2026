"""In-process stand-ins for authorization servers: the issuers this MCP server trusts, and others.

An AuthorizationServer signs tokens and rotates its own keys. A resource server reaches it only
through jwks() and introspect(), which stand in for HTTPS calls to its jwks_uri and to its
introspection endpoint. Each call is counted, takes `latency` seconds, and raises Unavailable
while `down` is set.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from .jwt import b64url, encode


class Unavailable(Exception):
    """An identity dependency did not answer."""


class AuthorizationServer:
    def __init__(self, issuer: str, clock: Callable[[], float] = time.time, *, latency: float = 0.0) -> None:
        self.issuer = issuer
        self.clock = clock
        self.latency = latency
        self.down = False
        self.jwks_requests = 0
        self.introspection_requests = 0
        self.minted = 0
        self._published: list[str] = []
        self._issued: dict[str, dict] = {}
        self._revoked: set[str] = set()
        self._serial = 0

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

    @property
    def kids(self) -> list[str]:
        """The key ids published right now, oldest first."""
        return list(self._published)

    def rotate_key(self) -> str:
        """Mint the next signing key, publish it, and sign with it from now on.

        Earlier keys stay published until retire_key, so tokens they signed keep validating
        during the overlap.
        """
        self.minted += 1
        kid = f"k{self.minted}"
        self._published.append(kid)
        return kid

    def retire_key(self, kid: str) -> None:
        """Stop publishing a key. Tokens it signed fail once resource servers refresh."""
        self._published.remove(kid)

    def token(
        self,
        aud: str | None,
        *,
        sub: str = "alice",
        scope: object = "mcp:tools.invoke",
        exp: object = None,
        kid: str | None = None,
        alg: str = "HS256",
        header: dict | None = None,
        **claims: object,
    ) -> str:
        """A JWT access token for audience aud, signed with the current key.

        aud=None leaves the aud claim out, and exp defaults to an hour from now. kid and alg
        set the header (the signature is HS256 with the key that kid names; alg "none" leaves
        it empty), header adds header parameters, and claims adds or overrides claims, iss
        included, so a test can build hostile tokens.
        """
        now = int(self.clock())
        body: dict = {"iss": self.issuer, "sub": sub, "aud": aud, "scope": scope, "iat": now}
        body["exp"] = now + 3600 if exp is None else exp
        if aud is None:
            del body["aud"]
        body.update(claims)
        kid = self._published[-1] if kid is None else kid
        head = {"alg": alg, "typ": "JWT", "kid": kid, **(header or {})}
        token = encode(head, body, None if alg == "none" else self._secret(kid))
        self._issued[token] = body
        return token

    def opaque_token(
        self, aud: str | None, *, sub: str = "alice", scope: str = "mcp:tools.invoke", ttl: int = 3600, **fields: object
    ) -> str:
        """An opaque access token: a random-looking string that only introspection can read."""
        self._serial += 1
        now = int(self.clock())
        token = "op_" + hashlib.sha256(f"{self.issuer}#{self._serial}".encode()).hexdigest()[:40]
        record: dict = {"iss": self.issuer, "sub": sub, "aud": aud, "scope": scope, "iat": now, "exp": now + ttl}
        if aud is None:
            del record["aud"]
        record.update(fields)
        self._issued[token] = record
        return token

    def revoke(self, token: str) -> None:
        """RFC 7009 revocation: the token stops being active here. Copies cached elsewhere are not erased."""
        self._revoked.add(token)

    def jwks(self) -> dict:
        """GET jwks_uri: the key set published right now."""
        self._call("jwks")
        return {
            "keys": [
                {"kid": kid, "kty": "oct", "alg": "HS256", "use": "sig", "k": b64url(self._secret(kid))}
                for kid in self._published
            ]
        }

    def introspect(self, token: str) -> dict:
        """POST the token to the introspection endpoint (RFC 7662) over the authenticated backchannel.

        A token this server did not issue, has revoked, or considers expired answers {"active": false}.
        """
        self._call("introspection")
        record = self._issued.get(token)
        if record is None or token in self._revoked or not self._live(record):
            return {"active": False}
        return {"active": True, **record}

    def _live(self, record: dict) -> bool:
        exp = record.get("exp")
        if isinstance(exp, bool) or not isinstance(exp, (int, float)):
            return True
        return self.clock() < exp

    def _call(self, endpoint: str) -> None:
        if endpoint == "jwks":
            self.jwks_requests += 1
        else:
            self.introspection_requests += 1
        if self.latency:
            time.sleep(self.latency)
        if self.down:
            raise Unavailable(f"{self.issuer} {endpoint} endpoint did not answer")

    def _secret(self, kid: str) -> bytes:
        return hashlib.sha256(f"{self.issuer}|{kid}".encode()).digest()
