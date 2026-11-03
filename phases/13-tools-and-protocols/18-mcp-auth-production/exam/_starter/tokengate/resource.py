"""The MCP server's JWT validator: trusted issuers, a JWKS cache, audience, expiry and scope."""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from .idp import AuthorizationServer
from .jwt import TokenError, parse, verify
from .outcome import Outcome
from .prm import ProtectedResource


class ResourceServer:
    """The MCP server's side of authorization: it caches JWKS and validates every request.

    idps reaches authorization servers by issuer (in production, HTTPS calls to the jwks_uri
    in each issuer's metadata). It can reach issuers this server does not trust;
    prm.authorization_servers is the allow-list.

    jwks_cache maps each issuer to {"keys": {kid: jwk}, "fetched_at": seconds}.
    """

    def __init__(
        self,
        prm: ProtectedResource,
        idps: Mapping[str, AuthorizationServer],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.prm = prm
        self.idps = idps
        self.clock = clock
        self.jwks_cache: dict[str, dict] = {}

    def refresh_jwks(self, issuer: str) -> dict:
        """Re-fetch one issuer's published JWKS, replace its cache entry, and return the entry.

        This is the only JWKS action a resource server takes: rotating keys is the authorization
        server's job. The scheduled refresh job and validate's cache-miss fall-back both call it.
        A fetch that fails raises Unavailable and leaves the cache as it was.
        """
        source = self.idps[issuer]
        published = source.jwks()
        entry = {"keys": {jwk["kid"]: jwk for jwk in published["keys"]}, "fetched_at": self.clock()}
        self.jwks_cache[source.jwks_uri] = entry
        return entry

    def validate(self, token: str, required_scope: str | None = None) -> Outcome:
        """Decide whether a bearer token may call a tool on this server. Runs on every request.

        In order, and the first failure refuses the request:
        - the token parses as a JWT ("malformed");
        - its iss is one of prm.authorization_servers ("iss not allowed"), checked before
          anything is fetched;
        - its header kid names a key in that issuer's cached JWKS; a miss refreshes that issuer
          once and looks again ("unknown kid");
        - the signature verifies ("bad signature");
        - aud equals prm.resource exactly, and a token without aud is not for this server
          ("audience mismatch");
        - now is before exp ("expired");
        - required_scope is one of the token's space-separated scopes (403).
        """
        try:
            header, claims = parse(token)
        except TokenError:
            return self.prm.refuse(401, "malformed")
        issuer = claims.get("iss")
        kid = header.get("kid")
        if not isinstance(kid, str):
            return self.prm.refuse(401, "unknown kid")
        entry = self.jwks_cache.get(issuer) or self.refresh_jwks(issuer)
        key = entry["keys"].get(kid)
        if key is None:
            # The authorization server may have published a key after our last refresh.
            self.idps[issuer].rotate_key()
            entry = self.jwks_cache.get(issuer, entry)
            key = entry["keys"].get(kid)
        if key is None:
            return self.prm.refuse(401, "unknown kid")
        if not verify(token, key):
            return self.prm.refuse(401, "bad signature")
        if claims.get("aud", self.prm.resource) != self.prm.resource:
            return self.prm.refuse(401, "audience mismatch")
        if claims.get("exp", 0) <= self.clock():
            return self.prm.refuse(401, "expired")
        if required_scope is not None and required_scope not in claims.get("scope", "").split():
            return self.prm.refuse(403, "insufficient scope", scope=required_scope)
        return Outcome.allow(claims)
