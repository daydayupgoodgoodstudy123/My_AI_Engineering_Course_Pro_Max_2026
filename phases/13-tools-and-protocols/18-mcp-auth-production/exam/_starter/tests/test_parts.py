import asyncio
import copy
import csv
import hashlib
import io
import json
import sqlite3
import time
from pathlib import Path

import pytest
from tokengate.clock import ManualClock
from tokengate.gate import Gate, IssuerPolicy
from tokengate.idp import AuthorizationServer, Unavailable
from tokengate.introspection import IntrospectionCache
from tokengate.outcome import Outcome
from tokengate.prm import ProtectedResource
from tokengate.redirects import redirect_uri_fits, registration_error
from tokengate.resource import ResourceServer
from tokengate.timeline import replay

AUTH = "https://auth.example.com"
PARTNERS = "https://partners.example.com"
LAB = "https://lab.example.com"
STRANGER = "https://stranger.example.net"
NOTES = "https://mcp.example.com/notes"
TASKS = "https://mcp.example.com/tasks"
NOTES_METADATA = "https://mcp.example.com/.well-known/oauth-protected-resource/notes"
INVOKE = "mcp:tools.invoke"
DELETE = "mcp:tools.delete"
T0 = 1_700_000_000
ALLOW = Outcome("allow", 200, "ok")


def refused(reason: str, health: str = "ok") -> Outcome:
    """A 401 refusal, exactly as the client sees it."""
    challenge = f'Bearer error="invalid_token", error_description="{reason}", resource_metadata="{NOTES_METADATA}"'
    return Outcome("refuse", 401, reason, health, challenge)


def notes_gate(clock, auth, partners, *, cache_max_age=None) -> Gate:
    """The notes server: auth tokens are JWTs, partners tokens are introspected."""
    server = ResourceServer(ProtectedResource(NOTES, (AUTH, PARTNERS)), {AUTH: auth, PARTNERS: partners}, clock=clock)
    policies = {
        AUTH: IssuerPolicy("jwt", refresh_interval=300, stale_window=600),
        PARTNERS: IssuerPolicy("introspection", cache_max_age=cache_max_age),
    }
    cache = IntrospectionCache(clock=clock, revocation_window=60, negative_ttl=5)
    return Gate(server, policies, cache, opaque_issuer=PARTNERS)


@pytest.mark.skip("Part 1")
def test_jwks_and_audience() -> None:
    """Only listed issuers, only this audience, and a JWKS cache that survives the issuer's key rotation."""
    clock = ManualClock(T0)
    auth = AuthorizationServer(AUTH, clock, latency=0.005)  # every JWKS fetch is a 5 ms round trip
    partners = AuthorizationServer(PARTNERS, clock)
    lab = AuthorizationServer(LAB, clock)  # reachable from here, but trusted only by another MCP server
    stranger = AuthorizationServer(STRANGER, clock)  # nothing here can reach it
    for idp in (auth, partners, lab, stranger):
        idp.rotate_key()  # every issuer's first key is k1
    server = ResourceServer(
        ProtectedResource(NOTES, (AUTH, PARTNERS)),
        {idp.issuer: idp for idp in (auth, partners, lab)},
        clock=clock,
    )

    good = auth.token(NOTES)
    assert server.validate(good, INVOKE).decision == "allow"
    assert server.validate(partners.token(NOTES), INVOKE).decision == "allow", (
        "every listed issuer is trusted, each with its own keys"
    )
    for token in (stranger.token(NOTES), lab.token(NOTES), auth.token(NOTES, iss=None)):
        assert server.validate(token, INVOKE) == refused("iss not allowed"), (
            "only issuers in the protected-resource metadata are trusted"
        )
    assert lab.jwks_requests == 0, "an issuer that is not listed never costs a JWKS fetch"
    assert server.validate(lab.token(NOTES, kid=7), INVOKE) == refused("iss not allowed"), (
        "the issuer is checked before anything else in the token"
    )

    assert server.validate(auth.token(TASKS), INVOKE) == refused("audience mismatch"), (
        "a token for another MCP server is refused"
    )
    assert server.validate(auth.token(None), INVOKE) == refused("audience mismatch"), (
        "a token without aud is not for this server"
    )
    for aud in (NOTES + "/admin", NOTES + "/"):
        assert server.validate(auth.token(aud), INVOKE) == refused("audience mismatch"), (
            "aud must equal this server's resource exactly"
        )

    start = time.perf_counter()
    for _ in range(200):
        server.validate(good, INVOKE)
    assert time.perf_counter() - start < 0.1, "validating with warm keys must not wait on the JWKS endpoint"

    auth.rotate_key()  # the authorization server publishes k2 and signs with it from now on
    fresh = auth.token(NOTES)
    before = auth.jwks_requests
    assert server.validate(fresh, INVOKE).decision == "allow", (
        "a token signed by a newly published key validates after one refresh"
    )
    assert auth.jwks_requests == before + 1, "a new kid costs one refresh"
    assert server.validate(good, INVOKE).decision == "allow", "the previous key keeps working during the overlap"
    assert auth.jwks_requests == before + 1, "keys already cached cost no fetch"
    assert auth.minted == 2, "validating never makes the authorization server mint keys"

    auth.retire_key("k1")
    clock.now = T0 + 60
    server.refresh_jwks(AUTH)  # the scheduled refresh job runs
    assert set(server.jwks_cache) == {AUTH, PARTNERS}, "jwks_cache is keyed by issuer"
    assert server.jwks_cache[AUTH]["fetched_at"] == T0 + 60, "a refresh records when the keys were fetched"
    assert server.validate(good, INVOKE) == refused("unknown kid"), "a retired key stops working after the next refresh"

    partner_fetches = partners.jwks_requests
    for i in range(5):
        before = auth.jwks_requests
        assert server.validate(auth.token(NOTES, kid=f"spray-{i}"), INVOKE) == refused("unknown kid")
        assert auth.jwks_requests - before <= 1, "an unknown kid costs at most one JWKS fetch"
    assert (auth.kids, auth.minted) == (["k2"], 2), "an unknown kid never changes the issuer's keys"
    assert partners.jwks_requests == partner_fetches, "a miss refreshes only the token's own issuer"
    partners.rotate_key()
    assert server.validate(partners.token(NOTES), INVOKE).decision == "allow", "every issuer's keys refresh on their own"


def canonical(value) -> str:
    """JSON with sorted keys: equal only when every value and every JSON type survived."""
    return json.dumps(value, sort_keys=True)


def stored_values(path: str) -> list[str]:
    """Every value in every table of a SQLite file, as text."""
    db = sqlite3.connect(path)
    try:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return [str(value) for table in tables for row in db.execute(f'SELECT * FROM "{table}"') for value in row]
    finally:
        db.close()


@pytest.mark.skip("Part 2")
def test_introspection_cache(tmp_path) -> None:
    """Replicas share introspection results by token digest, and no token ever reaches the disk."""
    path = str(tmp_path / "introspection.sqlite3")
    clock = ManualClock(T0 + 0.25)
    token = "op_" + "9c41e7b2" * 5
    response = {
        "active": True,
        "iss": PARTNERS,
        "aud": NOTES,
        "sub": "zoë@example.com",
        "client_id": "https://app.example.com/oauth/client.json",
        "scope": "mcp:tools.read mcp:tools.invoke",
        "token_type": "Bearer",
        "iat": T0,
        "exp": T0 + 600,
        "auth_time": 1699999990.125,
        "cnf": {"x5t#S256": "bwcK0esc3ACC3DB2Y5_lESsXE8o9ltc05O89jdN-dg2"},
        "ext": {"tenant": 9007199254740993, "groups": ["eng", "ops"], "mfa": False},
    }

    def open_cache() -> IntrospectionCache:
        return IntrospectionCache(path, clock=clock, revocation_window=60, negative_ttl=5)

    sent = copy.deepcopy(response)
    first, second = open_cache(), open_cache()  # two replicas, one file
    assert first.put(PARTNERS, token, NOTES, response, max_age=120) == T0 + 60.25, (
        "a positive entry lives until the earliest of exp, max_age and the revocation window"
    )
    assert response == sent, "put leaves the caller's response alone"
    assert canonical(second.get(PARTNERS, token, NOTES)) == canonical(sent), (
        "a cached response comes back exactly, at every replica"
    )
    assert second.get(PARTNERS, token, TASKS) is None, "a result for one resource never answers for another"
    assert second.get(AUTH, token, NOTES) is None, "nor for another issuer"
    assert second.get(PARTNERS, token[:-1] + "0", NOTES) is None, "nor for another token"
    first.close()
    second.close()

    values = stored_values(path)
    assert any(hashlib.sha256(token.encode()).hexdigest() in value.lower() for value in values), (
        "entries are keyed by the token's SHA-256 hex digest"
    )
    assert not any(token[:8] in value for value in values), "the token never appears in the cache, not even in part"
    assert token.encode() not in Path(path).read_bytes(), "the token never reaches the disk"
    cache = open_cache()
    assert canonical(cache.get(PARTNERS, token, NOTES)) == canonical(sent), "the cache survives a restart"

    def expiry(answer: dict, max_age=None):
        return cache.put(PARTNERS, "op_ttl", NOTES, answer, max_age=max_age)

    assert expiry({"active": True, "exp": T0 + 30}, max_age=120) == T0 + 30, "never past the token's exp"
    assert expiry({"active": True, "exp": T0 + 600}, max_age=20) == T0 + 20.25, "never past the issuer's max_age"
    assert expiry({"active": True}) == T0 + 60.25, "never past the revocation window"
    assert expiry({"active": False}, max_age=120) == T0 + 5.25, "a negative result is cached briefly"
    assert expiry({"active": True, "exp": T0}) is None, "a result that is already expired is not stored"
    assert expiry({"active": True, "exp": T0 + 600}, max_age=0) is None, "max_age 0 means the answer is not reused"
    assert expiry({"active": "false"}) == T0 + 5.25, 'only "active": true is a positive answer'

    cache.put(PARTNERS, "op_live", NOTES, {"active": True, "scope": "a"})
    cache.put(PARTNERS, "op_live", NOTES, {"active": True, "scope": "b"})
    clock.now = T0 + 59
    assert cache.get(PARTNERS, "op_live", NOTES) == {"active": True, "scope": "b"}, "storing again replaces the entry"
    clock.now = T0 + 61
    assert cache.get(PARTNERS, "op_live", NOTES) is None, "an entry is not served past its expiry"

    cache.put(PARTNERS, "op_new", NOTES, {"active": False})
    clock.now = T0 + 65
    assert cache.get(PARTNERS, "op_new", NOTES) == {"active": False}, "a negative result is served while it lives"
    clock.now = T0 + 67
    assert cache.get(PARTNERS, "op_new", NOTES) is None, "a newly issued token is not held inactive for long"

    answer = {"active": True, "aud": NOTES, "exp": T0 + 3600, "scope": INVOKE}
    calls: list[float] = []

    def introspect() -> dict:
        calls.append(clock())
        return dict(answer)

    answers = [cache.lookup(PARTNERS, "op_read", NOTES, introspect, max_age=10) for _ in range(2)]
    assert answers == [answer, answer] and len(calls) == 1, "a live entry answers without introspecting"
    clock.now += 6
    assert cache.lookup(PARTNERS, "op_read", NOTES, introspect, max_age=10) == answer
    assert len(calls) == 1, "a live entry answers without introspecting"
    clock.now += 5
    assert cache.lookup(PARTNERS, "op_read", NOTES, introspect, max_age=10) == answer
    assert len(calls) == 2, "lookup stores with the issuer's max_age, and reading an entry does not extend it"

    def unavailable() -> dict:
        raise Unavailable("introspection endpoint timed out")

    def inactive() -> dict:
        calls.append(clock())
        return {"active": False}

    assert [cache.lookup(PARTNERS, "op_junk", NOTES, inactive) for _ in range(2)] == [{"active": False}] * 2
    assert len(calls) == 3, "a negative answer is reused too, so junk tokens do not hammer the issuer"

    with pytest.raises(Unavailable):
        cache.lookup(PARTNERS, "op_down", NOTES, unavailable)
    assert cache.get(PARTNERS, "op_down", NOTES) is None, "a failed introspection stores nothing"
    cache.close()


@pytest.mark.skip("Part 3")
def test_gate_decisions() -> None:
    """The issuer's configured mode picks the check, and every dependency failure has a declared outcome."""
    clock = ManualClock(T0)
    auth = AuthorizationServer(AUTH, clock)
    auth.rotate_key()
    partners = AuthorizationServer(PARTNERS, lambda: clock() - 90)  # its clock runs 90 s behind ours
    partners.rotate_key()  # it signs JWTs too, but this deployment introspects every partners token
    gate = notes_gate(clock, auth, partners, cache_max_age=30)
    server = gate.server

    good = auth.token(NOTES)
    assert gate.check(good, INVOKE) == ALLOW
    assert gate.check(good, DELETE) == Outcome(
        "refuse",
        403,
        "insufficient scope",
        "ok",
        f'Bearer error="insufficient_scope", scope="{DELETE}", resource_metadata="{NOTES_METADATA}"',
    ), "a missing scope is a 403 that names the scope to ask for"

    fetches = auth.jwks_requests
    assert gate.check(auth.token(NOTES, alg="none", kid="k9"), INVOKE) == refused("alg not allowed"), (
        "an unsigned token is refused for its algorithm"
    )
    assert auth.jwks_requests == fetches, "an algorithm the issuer does not use costs no JWKS fetch"
    assert gate.check(auth.token(NOTES, alg="HS512"), INVOKE) == refused("alg not allowed"), (
        "the issuer's configured algorithms decide, not the token header"
    )
    rs256_only = Gate(server, {AUTH: IssuerPolicy("jwt", algorithms=("RS256",))}, gate.introspection)
    assert rs256_only.check(good, INVOKE) == refused("alg not allowed"), "each issuer's policy names its algorithms"
    for bad in ({"exp": str(T0 + 3600)}, {"exp": True}, {"scope": [INVOKE]}):
        assert gate.check(auth.token(NOTES, **bad), INVOKE) == refused("malformed"), (
            f"a claim of the wrong type is malformed: {bad}"
        )
    assert gate.check(auth.token(NOTES, iss=[AUTH]), INVOKE) == refused("iss not allowed"), "iss must be a string"

    early = partners.opaque_token(NOTES)
    for unreadable in (float("nan"), float("inf")):
        clock.now = unreadable
        for token in (good, early):
            assert gate.check(token, INVOKE) == Outcome("error", 503, "clock unavailable", "degraded"), (
                "a clock that cannot be read is an operational error, never a reason to let a token through"
            )
    clock.now = T0

    opaque = partners.opaque_token(NOTES)
    assert [gate.check(opaque, INVOKE), gate.check(opaque, INVOKE)] == [ALLOW, ALLOW], (
        "an opaque token is introspected at the opaque issuer"
    )
    assert partners.introspection_requests == 1, "introspection results are cached"
    from_partners = partners.token(NOTES)
    partners.revoke(from_partners)
    assert gate.check(from_partners, INVOKE) == refused("inactive"), (
        "a partners token is introspected, even when it looks like a JWT"
    )
    assert partners.jwks_requests == 0, "a partners token is never validated locally"
    assert gate.check(partners.opaque_token(TASKS), INVOKE) == refused("audience mismatch"), (
        "an introspected token must be for this resource"
    )
    assert gate.check(partners.opaque_token(None), INVOKE) == refused("audience mismatch"), (
        "an introspected token without aud is not for this resource either"
    )
    assert gate.check(partners.opaque_token(NOTES, ttl=60), INVOKE) == refused("expired"), (
        "an active answer is still checked against our clock"
    )
    assert gate.check(partners.opaque_token(NOTES, exp="soon"), INVOKE) == refused("malformed"), (
        "an introspection answer with the wrong types is malformed"
    )
    assert gate.check(partners.opaque_token(NOTES, scope="mcp:tools.invoke.readonly"), INVOKE).status == 403, (
        "an introspected token needs the scope too"
    )

    partners.down = True
    assert gate.check(partners.opaque_token(NOTES), INVOKE) == Outcome(
        "error", 503, "introspection unavailable", "degraded"
    ), "an introspection outage fails closed, as an operational error"
    assert gate.check(opaque, INVOKE) == ALLOW, "a live cached answer still counts during the outage"
    partners.down = False
    clock.now = T0 + 45
    before = partners.introspection_requests
    assert gate.check(opaque, INVOKE) == ALLOW
    assert partners.introspection_requests == before + 1, "the issuer's cache guidance bounds how long an answer is reused"

    clock.now = T0 + 350
    auth.rotate_key()
    newer = auth.token(NOTES)
    assert gate.check(newer, INVOKE) == ALLOW, "a refresh that succeeds while deciding leaves health ok"
    auth.down = True
    clock.now = T0 + 700
    with pytest.raises(Unavailable):
        server.refresh_jwks(AUTH)  # the scheduled refresh fails, and the cached keys stay
    fetches = auth.jwks_requests
    assert gate.check(good, INVOKE) == Outcome("allow", 200, "ok", "degraded"), (
        "known keys stay usable within the stale window, reported as degraded"
    )
    assert auth.jwks_requests == fetches, "keys within the stale window are used without asking the issuer again"
    assert gate.check(auth.token(TASKS, kid="k1"), INVOKE) == refused("audience mismatch", "degraded"), (
        "a refusal made with stale keys is degraded too"
    )
    auth.rotate_key()
    assert gate.check(auth.token(NOTES), INVOKE) == Outcome("error", 503, "jwks unavailable", "degraded"), (
        "an unknown kid whose one refresh fails is an outage, never accepted"
    )
    clock.now = T0 + 1200
    assert gate.check(good, INVOKE) == Outcome("allow", 200, "ok", "degraded"), (
        "the stale window starts when the missed refresh was due"
    )
    clock.now = T0 + 1251
    assert gate.check(good, INVOKE) == Outcome("error", 503, "jwks stale", "degraded"), (
        "past the stale window even known keys are not used"
    )
    auth.down = False
    server.refresh_jwks(AUTH)
    assert gate.check(newer, INVOKE) == ALLOW, "the next good refresh restores normal service"


def at(seconds: float) -> int:
    return T0 * 1000 + round(seconds * 1000)


def request(seconds: float, token: str, scope: str = INVOKE) -> dict:
    return {"t_ms": at(seconds), "type": "request", "token": token, "scope": scope}


def parse_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.skip("Part 4")
def test_incident_replay() -> None:
    """Replay an incident: one CSV row per request, written as soon as the request is decided."""
    clock = ManualClock(T0)
    auth = AuthorizationServer(AUTH, clock)
    auth.rotate_key()
    partners = AuthorizationServer(PARTNERS, clock)
    gate = notes_gate(clock, auth, partners, cache_max_age=120)
    old = auth.token(NOTES)

    pulled: list[int] = []

    async def probe():
        for i in range(100):
            pulled.append(i)
            yield request(i / 1000, old)

    async def first_row() -> list[str]:
        rows = replay(probe(), gate, clock)
        chunks = [await rows.__anext__(), await rows.__anext__()]
        await rows.aclose()
        return chunks

    chunks = asyncio.run(first_row())
    assert parse_csv("".join(chunks)) == [
        ["t_ms", "kid", "decision", "reason", "health"],
        [str(at(0)), "k1", "allow", "ok", "ok"],
    ], "the header comes first, then one row per decision"
    assert len(pulled) == 1, "decide each request as soon as it arrives"

    forged = 'k2",allow,ok,ok\n0,k2'  # a kid chosen by an attacker who can read the log

    async def incident():
        yield {"t_ms": at(0), "type": "refresh", "issuer": AUTH}
        yield request(1, old)
        auth.rotate_key()  # the authorization server rotates, and nobody tells the resource server
        new = auth.token(NOTES)
        yield request(2, new)
        yield request(2.5, old)
        yield request(2.7, old, DELETE)
        auth.retire_key("k1")
        yield {"t_ms": at(300), "type": "refresh", "issuer": AUTH}
        yield request(300.5, old)
        auth.down = True
        yield {"t_ms": at(600), "type": "refresh", "issuer": AUTH}
        yield request(650, new)
        yield request(1250, new)
        auth.down = False
        yield {"t_ms": at(1620), "type": "refresh", "issuer": AUTH}
        yield request(1620.5, new)
        opaque = partners.opaque_token(NOTES)
        yield request(1660.5, opaque)
        partners.revoke(opaque)  # RFC 7009 at the issuer; caches elsewhere are not told
        yield request(1690, opaque)
        yield request(1720.3, opaque)
        yield request(1721, opaque)
        yield request(1760, auth.token(NOTES, kid=forged))
        yield request(1765, auth.token(NOTES, kid=7))

    async def drain() -> list[str]:
        return [chunk async for chunk in replay(incident(), gate, clock)]

    chunks = asyncio.run(drain())
    assert parse_csv("".join(chunks)) == [
        ["t_ms", "kid", "decision", "reason", "health"],
        [str(at(1)), "k1", "allow", "ok", "ok"],
        [str(at(2)), "k2", "allow", "ok", "ok"],
        [str(at(2.5)), "k1", "allow", "ok", "ok"],
        [str(at(2.7)), "k1", "refuse", "insufficient scope", "ok"],
        [str(at(300.5)), "k1", "refuse", "unknown kid", "ok"],
        [str(at(650)), "k2", "allow", "ok", "degraded"],
        [str(at(1250)), "k2", "error", "jwks stale", "degraded"],
        [str(at(1620.5)), "k2", "allow", "ok", "ok"],
        [str(at(1660.5)), "", "allow", "ok", "ok"],
        [str(at(1690)), "", "allow", "ok", "ok"],
        [str(at(1720.3)), "", "allow", "ok", "ok"],
        [str(at(1721)), "", "refuse", "inactive", "ok"],
        [str(at(1760)), forged, "refuse", "unknown kid", "ok"],
        [str(at(1765)), "", "refuse", "unknown kid", "ok"],
    ], "one row per request, decided at its own time"
    assert all(len(parse_csv(chunk)) == 1 for chunk in chunks), "each chunk is exactly one CSV record"
    assert partners.jwks_requests == 0, "a refresh event refreshes only its own issuer"

    async def rotation():
        yield {"t_ms": at(1800), "type": "rotate", "issuer": AUTH}  # rotating is the issuer's job, not ours

    async def drain_rotation() -> list[str]:
        return [chunk async for chunk in replay(rotation(), gate, clock)]

    with pytest.raises(ValueError):
        asyncio.run(drain_rotation())


@pytest.mark.skip("Part 5")
def test_dcr_redirects() -> None:
    """Deprecated DCR: every redirect URI has to fit the client's declared application_type."""
    native_ok = [
        "http://127.0.0.1:7333/callback",
        "http://localhost:7333/callback",
        "http://[::1]:7333/callback",
        "http://127.0.0.1/callback",
        "HTTP://LOCALHOST:7333/callback",
        "https://app.example.com/oauth/callback",
        "https://app.example.com/callback?next=a@b",
        "com.example.app:/oauth2redirect",
        "Com.Example.App:/oauth2redirect",
        "com.example-app.desktop:/callback",
        "com.example.app://callback",
        "http://127.0.0.1:7333?flow=desktop",
    ]
    for uri in native_ok:
        assert redirect_uri_fits(uri, "native"), f"{uri!r} is a valid native redirect"
    web_ok = [
        "https://app.example.com/callback",
        "HTTPS://App.Example.com/callback",
        "https://app.example.com:8443/callback?state=x",
        "https://[2001:db8::1]/callback",
    ]
    for uri in web_ok:
        assert redirect_uri_fits(uri, "web"), f"{uri!r} is a valid web redirect"
    native_bad = [
        "http://app.example.com/callback",
        "http://localhost.evil.example/callback",
        "http://127.0.0.1.nip.io/callback",
        "http://127.0.0.2:7333/callback",
        "http://127.0.0.1:7333/call\tback",
        "http://127.0.0.1:7333/call back",
        "http://127.0.0.1:7333/callback\n",
        " http://127.0.0.1:7333/callback",
        "http://127.0.0.1:7333/callback\x7f",
        "http://127.0.0.1:7333/callback#",
        "http://127.0.0.1:7333/callback#done",
        "http://@127.0.0.1:7333/callback",
        "http://admin@127.0.0.1:7333/callback",
        "http://127.0.0.1:/callback",
        "http://127.0.0.1:65536/callback",
        "http://127.0.0.1:+7333/callback",
        "http://127.0.0.1:٧٣٣٣/callback",
        "http://[::1/callback",
        "https:///callback",
        "http:127.0.0.1/callback",
        "myapp:/callback",
        "com..example:/callback",
        "com.example-:/callback",
        "com.-example:/callback",
        "com.exam_ple:/callback",
        "javascript:alert(1)",
        "urn:ietf:wg:oauth:2.0:oob",
        "data:text/plain,callback",
        "ftp://app.example.com/callback",
        "/callback",
        "callback",
        "//app.example.com/callback",
        None,
        7333,
        b"http://127.0.0.1:7333/callback",
    ]
    for uri in native_bad:
        assert not redirect_uri_fits(uri, "native"), f"{uri!r} is not a native redirect"
    web_bad = [
        "http://127.0.0.1:7333/callback",
        "http://app.example.com/callback",
        "com.example.app:/oauth2redirect",
        "https://app.example.com/callback#",
        "https://user@app.example.com/callback",
        "https://app.example.com:99999/callback",
        "https://:443/callback",
    ]
    for uri in web_bad:
        assert not redirect_uri_fits(uri, "web"), f"{uri!r} is not a web redirect"
    with pytest.raises(ValueError):
        redirect_uri_fits("https://app.example.com/callback", "desktop")

    native = ["http://127.0.0.1:7333/callback", "com.example.app:/oauth2redirect"]
    assert registration_error({"application_type": "native", "redirect_uris": native}) is None
    assert registration_error({"application_type": "web", "redirect_uris": web_ok}) is None
    assert registration_error({"redirect_uris": web_ok}) == "invalid_client_metadata", (
        "DCR requires application_type, with no default"
    )
    assert registration_error({"application_type": "desktop", "redirect_uris": "x"}) == "invalid_client_metadata", (
        "application_type is checked first"
    )
    for uris in ([], "http://127.0.0.1:7333/callback", None, [*native, "http://app.example.com/callback"]):
        assert registration_error({"application_type": "native", "redirect_uris": uris}) == "invalid_redirect_uri", (
            f"redirect_uris must be a non-empty list of fitting URIs: {uris!r}"
        )
    assert registration_error({"application_type": "web", "redirect_uris": [*web_ok, native[0]]}) == (
        "invalid_redirect_uri"
    ), "one cleartext redirect sinks a web registration"
