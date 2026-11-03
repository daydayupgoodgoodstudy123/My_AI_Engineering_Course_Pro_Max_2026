import asyncio
import base64
import contextlib
import copy
import hashlib
import ipaddress
import json
import os
import stat
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from oauthflow.client import McpClient
from oauthflow.errors import (
    AuthorizationError,
    CimdInvalid,
    FetchBlocked,
    HttpError,
    IssuerMismatch,
    McpError,
    NeedClientInfo,
    OAuthFlowError,
    RefreshReuse,
)
from oauthflow.fetch import Response, SafeFetcher, public_address, resolve_cimd
from oauthflow.loopback import LoopbackDesk, Outcome
from oauthflow.model import ClientRecord, TokenRecord
from oauthflow.pkce import pkce_pair, s256
from oauthflow.register import FixedClientId, Registrar
from oauthflow.stepup import parse_bearer_challenge, step_up_scope
from oauthflow.vault import CredentialVault

ISSUER = "https://auth.example.com"
LEGACY = "https://login.archive.example"  # the archive's server: it never sends iss
NOTES = "https://notes.example.com/mcp"
ARCHIVE = "https://notes.example.com/archive/mcp"  # same origin, another resource
CIMD_URL = "https://client.example.com/oauth/metadata.json"
REDIRECT = "http://127.0.0.1:8765/callback"
UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

NOTES_TOOLS = {
    "notes.list": "notes:read",
    "notes.create": "notes:write",
    "notes.delete": "notes:delete",
    "notes.admin": "notes:admin",  # not in scopes_supported
    "notes.purge": "notes:purge",  # the server never grants it
    "notes.export": "notes:export",
    "notes.locked": None,  # refused by policy: a 403 without a scope challenge
}


def challenge_of(verifier: str) -> str:
    """S256, computed by the test itself."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def ok(tool: str) -> dict:
    return {"content": [{"type": "text", "text": f"{tool} done"}], "isError": False}


def attempt(action):
    """Run action and return its result, or the oauthflow error it raised."""
    try:
        return action()
    except OAuthFlowError as exc:
        return exc


def resource_metadata_url(resource: str) -> str:
    parts = urlsplit(resource)
    return f"{parts.scheme}://{parts.netloc}/.well-known/oauth-protected-resource{parts.path}"


def rpc_error(body: dict, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": code, "message": message}}


class FakeAuthServer:
    """An authorization server: the browser round trip (the user approves unless told to
    decline), the token endpoint and DCR. Every code it issues is full of characters that
    need percent-encoding."""

    def __init__(self, world, issuer, tag, *, resources, send_iss=True, cimd=True, dcr=False,
                 authorize_query="", grant_also=None, never_grant=(), refuse_cimd=False):
        self.world = world
        self.issuer = issuer
        self.tag = tag
        self.resources = set(resources)
        self.send_iss = send_iss
        self.refuse_cimd = refuse_cimd
        self.grant_also = dict(grant_also or {})
        self.never_grant = set(never_grant)
        self.metadata = {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize{authorize_query}",
            "token_endpoint": f"{issuer}/token",
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": cimd,
        }
        if send_iss:
            self.metadata["authorization_response_iss_parameter_supported"] = True
        if dcr:
            self.metadata["registration_endpoint"] = f"{issuer}/register"
        self.clients = {CIMD_URL} if cimd else set()
        self.codes: dict[str, dict] = {}
        self.authorized: list[dict] = []  # every authorization request's parameters
        self.redeemed: list[dict] = []  # every token request's fields
        self.registered: list[dict] = []  # every DCR request
        self.decline = False
        self.forge_iss = None
        self.count = 0

    def authorize(self, params: dict) -> dict:
        self.authorized.append(dict(params))
        if params.get("response_type") != "code":
            raise AuthorizationError("unsupported_response_type")
        if params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
            raise AuthorizationError("invalid_request", "PKCE with S256 is required")
        client_id = params.get("client_id")
        if client_id == CIMD_URL and self.refuse_cimd:
            raise AuthorizationError("invalid_client", "the client metadata document failed validation")
        if client_id not in self.clients:
            raise AuthorizationError("invalid_client", f"unknown client {client_id!r}")
        if params.get("redirect_uri") != REDIRECT:
            raise AuthorizationError("invalid_request", "unregistered redirect_uri")
        if params.get("resource") not in self.resources:
            raise AuthorizationError("invalid_target", f"{self.issuer} does not serve {params.get('resource')}")
        if self.decline:
            self.decline = False
            raise AuthorizationError("access_denied", "the user declined")
        asked = set(params.get("scope", "").split())
        granted = set(asked)
        for scope in asked:
            granted |= set(self.grant_also.get(scope, ()))
        granted -= self.never_grant
        self.count += 1
        code = f"{self.tag}{self.count}+/=&%~ x"
        # this server lists granted scopes in its own order
        self.codes[code] = {**params, "granted": " ".join(sorted(granted, reverse=True))}
        answer = {"code": code, "state": params["state"]}
        iss = self.forge_iss if self.forge_iss is not None else (self.issuer if self.send_iss else None)
        if iss is not None:
            answer["iss"] = iss
        return answer

    def token(self, form: dict) -> dict:
        self.redeemed.append(dict(form))
        grant = self.codes.pop(form.get("code"), None)
        if grant is None or form.get("grant_type") != "authorization_code":
            return {"error": "invalid_grant", "error_description": "unknown or already used code"}
        for name in ("client_id", "redirect_uri", "resource"):
            if form.get(name) != grant[name]:
                return {"error": "invalid_grant", "error_description": f"{name} differs from the authorization request"}
        if challenge_of(form.get("code_verifier", "")) != grant["code_challenge"]:
            return {"error": "invalid_grant", "error_description": "PKCE verification failed"}
        self.count += 1
        token = f"at-{self.tag}-{self.count}"
        self.world.issued[token] = {"issuer": self.issuer, "audience": grant["resource"],
                                    "scope": set(grant["granted"].split())}
        return {"access_token": token, "token_type": "Bearer", "expires_in": 3600, "scope": grant["granted"]}

    def register(self, metadata: dict) -> dict:
        self.registered.append(copy.deepcopy(metadata))
        kind = metadata.get("application_type", "web")  # the OpenID Connect default
        for uri in metadata.get("redirect_uris", []):
            parts = urlsplit(uri)
            if kind == "web" and (parts.scheme != "https" or parts.hostname in ("127.0.0.1", "::1", "localhost")):
                raise AuthorizationError("invalid_redirect_uri", "a web client needs remote https redirect URIs")
        self.count += 1
        client_id = f"dcr-{self.tag}-{self.count}"
        self.clients.add(client_id)
        return {**metadata, "client_id": client_id, "registration_access_token": f"rat-{self.tag}-{self.count}"}


class FakeResource:
    """An MCP resource server. A token must come from its issuer and name it as audience;
    each tool needs one scope."""

    def __init__(self, world, resource, issuer, tools, *, unlisted=()):
        self.world = world
        self.resource = resource
        self.issuer = issuer
        self.tools = dict(tools)
        scopes = {scope for scope in tools.values() if scope} - set(unlisted)
        self.metadata = {"resource": resource, "authorization_servers": [issuer],
                         "scopes_supported": sorted(scopes)}

    def handle(self, headers: dict, body: dict):
        pointer = f'resource_metadata="{resource_metadata_url(self.resource)}"'
        bearer = headers.get("Authorization", "")
        grant = self.world.issued.get(bearer[len("Bearer "):]) if bearer.startswith("Bearer ") else None
        if (grant is None or grant.get("revoked") or grant["issuer"] != self.issuer
                or grant["audience"] != self.resource):
            return 401, {"WWW-Authenticate": f'Bearer error="invalid_token", {pointer}'}, rpc_error(body, -32001, "Unauthorized")
        tool = body["params"]["name"]
        needed = self.tools[tool]
        if needed is None:
            return 403, {}, rpc_error(body, -32003, "Forbidden by policy")
        if needed not in grant["scope"]:
            challenge = f'Bearer error="insufficient_scope", scope="{needed}", {pointer}'
            return 403, {"WWW-Authenticate": challenge}, rpc_error(body, -32003, "Insufficient scope")
        return 200, {}, {"jsonrpc": "2.0", "id": body["id"], "result": ok(tool)}


class World:
    """The network the in-process client sees: metadata documents, authorization servers and
    MCP resources. Every metadata fetch takes `latency` seconds."""

    def __init__(self, latency: float = 0.0) -> None:
        self.latency = latency
        self.documents: dict[str, dict] = {}
        self.auth: dict[str, FakeAuthServer] = {}
        self.endpoints: dict[str, FakeAuthServer] = {}
        self.resources: dict[str, FakeResource] = {}
        self.issued: dict[str, dict] = {}
        self.fetched: list[str] = []
        self.registrations: list[str] = []

    def add_auth(self, server: FakeAuthServer) -> FakeAuthServer:
        self.auth[server.issuer] = server
        self.documents[f"{server.issuer}/.well-known/oauth-authorization-server"] = server.metadata
        for key in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
            if key in server.metadata:
                self.endpoints[server.metadata[key]] = server
        return server

    def add_resource(self, server: FakeResource) -> FakeResource:
        self.resources[server.resource] = server
        self.documents[resource_metadata_url(server.resource)] = server.metadata
        return server

    def revoke(self, token: str) -> None:
        self.issued[token]["revoked"] = True

    def get_json(self, url: str) -> dict:
        if self.latency:
            time.sleep(self.latency)
        self.fetched.append(url)
        if url not in self.documents:
            raise HttpError(404, url)
        return copy.deepcopy(self.documents[url])

    def authorize(self, endpoint: str, params: dict) -> dict:
        return self.endpoints[endpoint].authorize(dict(params))

    def token(self, endpoint: str, form: dict) -> dict:
        return self.endpoints[endpoint].token(dict(form))

    def register(self, endpoint: str, metadata: dict) -> dict:
        self.registrations.append(endpoint)
        return self.endpoints[endpoint].register(copy.deepcopy(metadata))

    def post_mcp(self, resource: str, headers: dict, body: dict):
        return self.resources[resource].handle(dict(headers), copy.deepcopy(body))


def build_world(latency: float = 0.0, **notes_policy) -> World:
    world = World(latency)
    world.add_auth(FakeAuthServer(world, ISSUER, "n", resources={NOTES}, **notes_policy))
    world.add_auth(FakeAuthServer(world, LEGACY, "a", resources={ARCHIVE}, send_iss=False,
                                  authorize_query="?tenant=notes"))
    world.add_resource(FakeResource(world, NOTES, ISSUER, NOTES_TOOLS, unlisted={"notes:admin"}))
    world.add_resource(FakeResource(world, ARCHIVE, LEGACY, {"archive.search": "archive:read"}))
    return world


@pytest.mark.skip("Part 1")
def test_discovery_and_code_flow() -> None:
    """Discovery keeps the resource path, PKCE is S256, iss is compared exactly, and each resource is discovered once."""
    world = build_world(latency=0.004)
    notes = world.auth[ISSUER]
    client = McpClient(world, FixedClientId(CIMD_URL), redirect_uri=REDIRECT)

    token = client.login(NOTES, "notes:read")
    assert (token.issuer, token.resource, token.scope) == (ISSUER, NOTES, "notes:read"), (
        "a token is kept under (issuer, resource) with the scope the server granted"
    )
    assert client.call(NOTES, "notes.list") == ok("notes.list"), "an authorized call goes through"

    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128 and set(verifier) <= UNRESERVED, (
        "a code_verifier is 43 to 128 unreserved characters"
    )
    assert challenge == challenge_of(verifier), "the code_challenge is the S256 of the code_verifier"
    assert pkce_pair()[0] != verifier, "every flow gets a fresh verifier"
    assert s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", (
        "S256 is BASE64URL(SHA-256(verifier)) without padding (RFC 7636, Appendix B)"
    )

    redeemed = len(notes.redeemed)
    for forged in ("https://auth.example.com/", "https://AUTH.example.com", "https://auth.example.com:443",
                   "https://auth.example%2Ecom", ""):
        notes.forge_iss = forged
        refused = attempt(lambda: client.login(NOTES, "notes:read"))
        assert isinstance(refused, IssuerMismatch), f"iss is compared exactly: {forged!r} is not {ISSUER!r}"
    notes.forge_iss = None
    assert len(notes.redeemed) == redeemed, "a response with the wrong iss never reaches the token endpoint"

    start = time.perf_counter()
    for _ in range(200):
        client.call(NOTES, "notes.list")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, "discovery runs once per resource, not before every request"

    assert client.discovery(ARCHIVE).issuer == LEGACY, (
        "two resources on one origin are discovered separately: each has its own metadata"
    )
    archive = attempt(lambda: client.login(ARCHIVE, "archive:read"))
    assert isinstance(archive, TokenRecord), "a response without iss is fine when the server never sends one"
    assert client.call(ARCHIVE, "archive.search") == ok("archive.search"), "each resource uses its own token"
    world.auth[LEGACY].forge_iss = ISSUER
    refused = attempt(lambda: client.login(ARCHIVE, "archive:read"))
    world.auth[LEGACY].forge_iss = None
    assert isinstance(refused, IssuerMismatch), (
        "a present iss is checked even when the server does not advertise authorization_response_iss_parameter_supported"
    )
    assert client.call(NOTES, "notes.list") == ok("notes.list"), "the first resource's token is untouched"


@contextlib.contextmanager
def umask(mask: int):
    previous = os.umask(mask)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.skip("Part 2")
def test_vault_snapshot(tmp_path, monkeypatch) -> None:
    """Records are keyed by the exact issuer and (issuer, resource); the file is private from birth and reads back exactly."""
    def chmod_refused(*args, **kwargs):
        raise AssertionError("the vault file is private from the moment it is created, never chmod-ed later")

    for name in ("chmod", "fchmod", "lchmod"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, chmod_refused)

    path = tmp_path / "vault.json"
    one = "https://auth-one.example"
    slash = one + "/"
    pre = ClientRecord(one, "notes-desktop", "preregistered", client_secret="s3cr+t/=")
    dcr = ClientRecord(slash, "dcr-41f", "dcr", registration_access_token="rat-41f")
    notes = TokenRecord(one, NOTES, "at-1", "notes:write notes:read", 1_785_000_000, "rt-1")
    archive = TokenRecord(one, ARCHIVE, "at-2", "archive:read", 1_785_000_060)
    other = TokenRecord(slash, NOTES, "at-3", "notes:read", 1_785_000_120, "rt-3")

    with umask(0o022):
        vault = CredentialVault(path)
        assert vault.client(one) is None and vault.token(one, NOTES) is None, "a new vault is empty"
        vault.put_client(pre)
        vault.put_client(dcr)
        for record in (notes, archive, other):
            vault.put_token(record)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, "only the owner can read or write the vault file"

        reopened = CredentialVault(path)
        assert reopened.client(one) == pre, "a client record reads back exactly"
        assert reopened.client(slash) == dcr, "a trailing slash makes another issuer, with its own records"
        assert reopened.client("https://AUTH-ONE.example") is None, "issuers are exact strings"
        assert reopened.token(one, NOTES) == notes, "a token record reads back exactly, scope string as granted"
        assert type(reopened.token(one, NOTES).expires_at) is int, "expires_at stays whole seconds"
        assert reopened.token(one, ARCHIVE) == archive, "tokens are kept per (issuer, resource)"
        assert reopened.token(slash, NOTES) == other, "tokens are kept per exact issuer"
        assert reopened.client("https://auth-two.example") is None and reopened.token("https://auth-two.example", NOTES) is None, (
            "after the resource moves to another issuer, nothing minted by the first one is offered"
        )

        rotated = TokenRecord(one, NOTES, "at-4", "notes:write notes:read", 1_785_003_600, "rt-2")
        reopened.rotate(one, NOTES, "rt-1", rotated)
        later = CredentialVault(path)
        assert later.token(one, NOTES) == rotated, "a rotation is in the file at once"
        # rt-3 is the refresh token of (slash, NOTES), not of (one, NOTES)
        with pytest.raises(ValueError):
            later.rotate(one, NOTES, "rt-3", TokenRecord(one, NOTES, "at-x", "notes:read", 1_785_003_700, "rt-x"))
        assert later.token(slash, NOTES) == other, "a refresh token belongs to one (issuer, resource) only"
        kept = TokenRecord(one, NOTES, "at-5", "notes:write notes:read", 1_785_007_200)
        later.rotate(one, NOTES, "rt-2", kept)
        assert later.token(one, NOTES).refresh_token == "rt-2", (
            "when the server issues no new refresh token, the current one stays"
        )
        newer = TokenRecord(one, NOTES, "at-6", "notes:write notes:read", 1_785_010_800, "rt-6")
        later.rotate(one, NOTES, "rt-2", newer)
        assert CredentialVault(path).token(one, NOTES) == newer, "a refresh token that was kept still rotates"
        echoed = TokenRecord(one, NOTES, "at-7", "notes:write notes:read", 1_785_014_400, "rt-6")
        later.rotate(one, NOTES, "rt-6", echoed)
        latest = TokenRecord(one, NOTES, "at-8", "notes:write notes:read", 1_785_018_000, "rt-8")
        assert attempt(lambda: later.rotate(one, NOTES, "rt-6", latest)) is None and CredentialVault(path).token(one, NOTES) == latest, (
            "a refresh token that the server sent back unchanged is still the current one"
        )

        replay = CredentialVault(path)
        with pytest.raises(RefreshReuse):
            replay.rotate(one, NOTES, "rt-1", TokenRecord(one, NOTES, "at-9", "notes:read", 1_785_021_600, "rt-9"))
        assert replay.token(one, NOTES) is None, "reuse of a rotated refresh token drops the record"
        final = CredentialVault(path)
        assert final.token(one, NOTES) is None, "the drop is in the file"
        assert final.token(slash, NOTES) == other and final.token(one, ARCHIVE) == archive, (
            "reuse drops only that (issuer, resource)"
        )
        assert final.client(one) == pre and final.client(slash) == dcr, "client records survive every rewrite"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, "the vault file stays private after every rewrite"


@pytest.mark.skip("Part 3")
def test_step_up_and_enrollment(tmp_path) -> None:
    """A scope challenge is read exactly, step-up asks for granted plus challenged scope, a 401 is not a step-up, and enrollment follows the lesson's order."""
    pointer = "https://notes.example.com/.well-known/oauth-protected-resource/mcp"
    lesson = f'Bearer error="insufficient_scope", scope="notes:delete", resource_metadata="{pointer}"'
    assert parse_bearer_challenge(lesson) == {
        "error": "insufficient_scope", "scope": "notes:delete", "resource_metadata": pointer,
    }, "the lesson's challenge"
    tricky = ('Basic realm="Notes, \\"Archive\\"", Bearer realm="Notes", error=insufficient_scope, '
              'scope="notes:delete notes:admin", error_description="Delete needs \\"notes:delete\\", then retry"')
    assert parse_bearer_challenge(tricky) == {
        "realm": "Notes",
        "error": "insufficient_scope",
        "scope": "notes:delete notes:admin",
        "error_description": 'Delete needs "notes:delete", then retry',
    }, "only the Bearer challenge counts; quoted strings keep their commas and case, and lose their escapes"
    assert parse_bearer_challenge('bearer error="invalid_token"') == {"error": "invalid_token"}, (
        "scheme names compare case-insensitively"
    )
    assert parse_bearer_challenge('Basic realm="notes"') == {}, "no Bearer challenge, no parameters"
    assert parse_bearer_challenge('Bearer error="invalid_token", Basic realm="notes"') == {"error": "invalid_token"}, (
        "the Bearer challenge ends where the next challenge's scheme starts"
    )

    assert step_up_scope("notes:write notes:read", "notes:delete") == "notes:delete notes:read notes:write", (
        "step-up asks for granted plus challenged scopes, each once, in sorted order"
    )
    assert step_up_scope("", "notes:read notes:read") == "notes:read", "each scope once, and an empty scope adds nothing"
    letters = " ".join(f"s:{c}" for c in "qwertyuiop")
    assert step_up_scope(letters, "s:a") == " ".join(sorted(letters.split() + ["s:a"])), (
        "the scopes always come in sorted order"
    )

    world = build_world(grant_also={"notes:read": ["notes:write"]}, never_grant={"notes:purge"})
    notes = world.auth[ISSUER]
    client = McpClient(world, FixedClientId(CIMD_URL), redirect_uri=REDIRECT)
    assert client.login(NOTES, "notes:read").scope == "notes:write notes:read", (
        "a token keeps the scope the server granted, which can be more than was asked for"
    )
    archive = client.login(ARCHIVE, "archive:read")
    assert attempt(lambda: client.call_with_step_up(NOTES, "notes.create")) == ok("notes.create"), (
        "a call within the granted scope goes straight through"
    )
    assert len(notes.authorized) == 1, "a granted scope needs no new flow"

    assert attempt(lambda: client.call_with_step_up(NOTES, "notes.delete")) == ok("notes.delete"), (
        "a 403 scope challenge leads to a step-up and a retry"
    )
    assert notes.authorized[-1]["scope"] == "notes:delete notes:read notes:write", (
        "step-up asks for every scope granted so far plus the challenged one"
    )
    assert attempt(lambda: client.call_with_step_up(NOTES, "notes.admin")) == ok("notes.admin"), (
        "a challenged scope is asked for even when scopes_supported does not list it"
    )
    assert notes.authorized[-1]["scope"] == "notes:admin notes:delete notes:read notes:write", (
        "the challenged scope joins every scope granted so far"
    )
    flows = len(notes.authorized)
    still = attempt(lambda: client.call_with_step_up(NOTES, "notes.purge"))
    assert isinstance(still, McpError) and still.status == 403, "a call that still fails after one step-up raises McpError"
    assert len(notes.authorized) == flows + 1, "one step-up per call"
    policy = attempt(lambda: client.call_with_step_up(NOTES, "notes.locked"))
    assert isinstance(policy, McpError) and policy.status == 403 and len(notes.authorized) == flows + 1, (
        "a 403 without a scope challenge is not a step-up"
    )

    current = client.tokens[(ISSUER, NOTES)]
    notes.decline = True
    declined = attempt(lambda: client.call_with_step_up(NOTES, "notes.export"))
    assert isinstance(declined, AuthorizationError), "a declined step-up raises"
    assert client.tokens.get((ISSUER, NOTES)) == current, (
        "a declined step-up keeps the token: it still works for what it was granted"
    )
    world.revoke(current.access_token)
    assert attempt(lambda: client.call_with_step_up(NOTES, "notes.list")) == ok("notes.list"), (
        "a 401 leads to a new flow and a retry"
    )
    assert notes.authorized[-1]["scope"] == current.scope, "after a 401 the new flow asks for the same scope again"
    world.revoke(client.tokens[(ISSUER, NOTES)].access_token)
    notes.decline = True
    declined = attempt(lambda: client.call_with_step_up(NOTES, "notes.list"))
    assert isinstance(declined, AuthorizationError), "a declined flow after a 401 raises"
    assert (ISSUER, NOTES) not in client.tokens, "a token the server no longer accepts is dropped before the new flow"
    assert client.tokens[(LEGACY, ARCHIVE)] == archive, "nothing that happens to one resource touches another's token"

    one, two, old, old2, bare = (f"https://{name}.example" for name in ("auth-one", "auth-two", "old-auth", "old-auth-2", "bare-auth"))
    for issuer, tag, cimd, dcr in ((one, "one", True, True), (two, "two", True, True), (old, "old", False, True),
                                   (old2, "older", False, True), (bare, "bare", False, False)):
        world.add_auth(FakeAuthServer(world, issuer, tag, resources=set(), cimd=cimd, dcr=dcr))
    meta = {issuer: server.metadata for issuer, server in world.auth.items()}
    vault = CredentialVault(tmp_path / "vault.json")
    vault.put_client(ClientRecord(one, "notes-desktop", "preregistered"))
    registrar = Registrar(world, vault, client_name="Notes desktop", redirect_uri=REDIRECT, cimd_url=CIMD_URL, allow_dcr=True)
    assert registrar.client_id_for(one, meta[one]) == "notes-desktop", "a client pre-registered with the issuer comes first"
    assert registrar.client_id_for(two, meta[two]) == CIMD_URL, "CIMD comes before DCR"
    assert registrar.client_id_for(one + "/", {**meta[one], "issuer": one + "/"}) == CIMD_URL, (
        "a pre-registration belongs to one exact issuer string"
    )
    first = registrar.client_id_for(old, meta[old])
    assert world.auth[old].registered and world.auth[old].registered[0]["application_type"] == "native", (
        "DCR is the fallback when the server has no CIMD support"
    )
    assert registrar.client_id_for(old, meta[old]) == first and len(world.registrations) == 1, (
        "a DCR client is registered once per issuer and reused"
    )
    assert vault.client(old) == ClientRecord(old, first, "dcr", None, f"rat-{first[4:]}"), (
        "a DCR registration is kept in the vault under the exact issuer"
    )
    assert registrar.client_id_for(old2, meta[old2]) not in (first, CIMD_URL), (
        "a DCR client id is never offered to another issuer"
    )
    assert registrar.client_id_for(old, {**meta[old], "client_id_metadata_document_supported": True}) == CIMD_URL, (
        "once the server supports CIMD, CIMD comes before the DCR client registered earlier"
    )
    restarted = Registrar(world, CredentialVault(tmp_path / "vault.json"), client_name="Notes desktop",
                          redirect_uri=REDIRECT, cimd_url=CIMD_URL, allow_dcr=True)
    assert restarted.client_id_for(old, meta[old]) == first and len(world.registrations) == 2, (
        "a DCR registration survives a restart"
    )
    strict = Registrar(world, vault, client_name="Notes desktop", redirect_uri=REDIRECT, cimd_url=CIMD_URL)
    with pytest.raises(NeedClientInfo):
        strict.client_id_for("https://old-auth-3.example", {**meta[old], "issuer": "https://old-auth-3.example"})
    with pytest.raises(NeedClientInfo):
        registrar.client_id_for(bare, meta[bare])
    assert len(world.registrations) == 2, "DCR only when it is allowed and the server offers it"

    broken_issuer, broken = "https://auth.broken.example", "https://broken.example.com/mcp"
    world.add_auth(FakeAuthServer(world, broken_issuer, "b", resources={broken}, cimd=True, dcr=True, refuse_cimd=True))
    world.add_resource(FakeResource(world, broken, broken_issuer, {"notes.list": "notes:read"}))
    failed = attempt(lambda: McpClient(world, registrar, redirect_uri=REDIRECT).login(broken, "notes:read"))
    assert isinstance(failed, AuthorizationError) and failed.error == "invalid_client", (
        "a CIMD client id the server rejects is an error"
    )
    assert len(world.registrations) == 2, "a CIMD failure is never a reason to fall back to DCR"


def form_fields(body: bytes) -> dict[str, str]:
    """Read an application/x-www-form-urlencoded body strictly: ASCII, well-formed, each field once."""
    pairs = parse_qs(body.decode("ascii"), strict_parsing=True, keep_blank_values=True)
    if any(len(values) != 1 for values in pairs.values()):
        raise ValueError("a field appears more than once")
    return {name: values[0] for name, values in pairs.items()}


def split_url(url: str) -> tuple[str, dict[str, str]]:
    """A URL as (everything before the query, each query parameter once)."""
    parts = urlsplit(url)
    pairs = parse_qs(parts.query, strict_parsing=True, keep_blank_values=True)
    assert all(len(values) == 1 for values in pairs.values()), "each authorization parameter appears once"
    return f"{parts.scheme}://{parts.netloc}{parts.path}", {name: values[0] for name, values in pairs.items()}


@pytest.mark.skip("Part 4")
def test_loopback_redirects() -> None:
    """Redirects reach the loopback listener in any order; each finishes its own flow, and token requests are form bodies."""
    world = build_world()
    client = McpClient(world, FixedClientId(CIMD_URL), redirect_uri=REDIRECT)
    clock = [0.0]
    sent: list[tuple[str, dict, bytes]] = []
    gates: dict[str, asyncio.Event] = {}

    async def post(url, headers, body):
        sent.append((url, dict(headers), body))
        if url in gates:
            await gates[url].wait()
        try:
            fields = form_fields(body)
        except (UnicodeDecodeError, ValueError, AttributeError):
            return 400, {"error": "invalid_request", "error_description": "not a form body"}
        answer = world.endpoints[url].token(fields)
        return (400 if "error" in answer else 200), answer

    def browser(url: str) -> str:
        """The user approves; the server redirects to the loopback listener."""
        endpoint, params = split_url(url)
        params.pop("tenant", None)
        server = next(s for s in world.auth.values() if endpoint == s.issuer + "/authorize")
        return REDIRECT + "?" + urlencode(server.authorize(params))

    desk = LoopbackDesk(client, post, clock=lambda: clock[0], ttl=600)
    stale_url = desk.begin(NOTES, "notes:read")
    clock[0] = 700.0
    notes_url = desk.begin(NOTES, "notes:read notes:write")
    archive_url = desk.begin(ARCHIVE, "archive:read")
    forged_url = desk.begin(NOTES, "notes:delete")
    declined_url = desk.begin(ARCHIVE, "archive:read")
    spent_url = desk.begin(ARCHIVE, "archive:read")

    assert " " not in notes_url, "the authorization URL is form-encoded: no raw spaces"
    endpoint, params = split_url(notes_url)
    notes_challenge = params.pop("code_challenge", "")
    assert endpoint == ISSUER + "/authorize" and len(params.pop("state", "")) >= 16, (
        "the authorization endpoint, with a state of at least 128 bits"
    )
    assert len(notes_challenge) == 43 and params == {
        "response_type": "code", "client_id": CIMD_URL, "redirect_uri": REDIRECT,
        "scope": "notes:read notes:write", "code_challenge_method": "S256", "resource": NOTES,
    }, "the authorization request carries client_id, redirect_uri, scope, the S256 challenge and resource"
    endpoint, params = split_url(archive_url)
    assert endpoint == LEGACY + "/authorize" and params.get("tenant") == "notes" and params.get("resource") == ARCHIVE, (
        "a query that the authorization endpoint already has is kept"
    )

    notes_redirect = browser(notes_url)
    archive_redirect = browser(archive_url)
    stale_redirect = browser(stale_url)
    attacker_text = "Session expired. Sign in again at https://evil.example/login"
    forged_redirect = REDIRECT + "?" + urlencode({
        "error": "access_denied", "error_description": attacker_text,
        "state": split_url(forged_url)[1]["state"], "iss": LEGACY,
    })
    declined_redirect = REDIRECT + "?" + urlencode({
        "error": "access_denied", "error_description": "The user said no",
        "state": split_url(declined_url)[1]["state"],
    })
    spent_code = "a0 already+used"  # a code the archive server never issued
    spent_redirect = REDIRECT + "?" + urlencode({"code": spent_code, "state": split_url(spent_url)[1]["state"]})
    unknown_redirect = REDIRECT + "?" + urlencode({"code": "n9", "state": "never-issued", "iss": ISSUER})
    checked: list[dict] = []

    def check_sent() -> None:
        """Read every token request sent so far the way the token endpoint would."""
        for _, headers, body in sent[len(checked):]:
            lowered = {name.lower(): value for name, value in headers.items()}
            assert lowered.get("content-type", "").split(";")[0].strip() == "application/x-www-form-urlencoded", (
                "a token request is sent as application/x-www-form-urlencoded"
            )
            try:
                fields = form_fields(body)
            except (UnicodeDecodeError, ValueError, AttributeError):
                fields = None
            assert fields is not None, "a token request body is form-encoded bytes: every value percent-encoded, each field once"
            assert set(fields) == {"grant_type", "code", "redirect_uri", "client_id", "code_verifier", "resource"}, (
                "a token request carries grant_type, code, redirect_uri, client_id, code_verifier and resource"
            )
            assert (fields["grant_type"], fields["redirect_uri"], fields["client_id"]) == (
                "authorization_code", REDIRECT, CIMD_URL), "the same redirect_uri and client_id as the authorization request"
            checked.append(fields)

    async def scenario() -> None:
        arrivals: asyncio.Queue = asyncio.Queue()

        async def redirects():
            while (url := await arrivals.get()) is not None:
                yield url

        outcomes = desk.serve(redirects())

        async def expect(outcome: Outcome, why: str) -> Outcome:
            try:
                got = await asyncio.wait_for(outcomes.__anext__(), 1.0)
            except asyncio.TimeoutError:
                got = "nothing within a second"
            except StopAsyncIteration:
                got = "the end of the stream"
            except OAuthFlowError as exc:
                got = f"serve raised {type(exc).__name__}: {exc}"
            check_sent()
            assert got == outcome, why
            return got

        gates[ISSUER + "/token"] = asyncio.Event()
        await arrivals.put(notes_redirect)
        await arrivals.put(archive_redirect)
        await expect(Outcome("token", ARCHIVE), (
            "the archive flow gets its token while the notes token request is still waiting"
        ))
        await arrivals.put(notes_redirect)
        await expect(Outcome("rejected", None, "unknown_state"), (
            "a flow takes one redirect: a copy is refused at once, even while the first is still exchanging"
        ))
        assert len(sent) == 2, "a copy of a redirect never reaches the token endpoint"
        await arrivals.put(forged_redirect)
        forged = await expect(Outcome("rejected", NOTES, "issuer_mismatch"), (
            "a redirect whose iss is not the flow's issuer is rejected before its error is read"
        ))
        assert "evil" not in repr(forged), "nothing from a redirect with the wrong iss is shown"
        await arrivals.put(browser(forged_url))
        await expect(Outcome("rejected", None, "unknown_state"), (
            "the first redirect that matches a flow closes it, even when that redirect is rejected"
        ))
        await arrivals.put(declined_redirect)
        await expect(Outcome("denied", ARCHIVE, "access_denied", "The user said no"), (
            "an error redirect from the right server is reported with its error_description"
        ))
        await arrivals.put(spent_redirect)
        await expect(Outcome("denied", ARCHIVE, "invalid_grant", "unknown or already used code"), (
            "an error answer from the token endpoint is reported as a denial with its error_description"
        ))
        await arrivals.put(stale_redirect)
        await expect(Outcome("rejected", NOTES, "expired"), "a flow opened more than ttl seconds ago is rejected as expired")
        await arrivals.put(stale_redirect)
        await expect(Outcome("rejected", None, "unknown_state"), "an expired flow is closed by the redirect that found it")
        await arrivals.put(unknown_redirect)
        await expect(Outcome("rejected", None, "unknown_state"), "a state that matches no open flow is rejected")
        await arrivals.put(None)
        gates[ISSUER + "/token"].set()
        await expect(Outcome("token", NOTES), "the slow exchange finishes after the redirects have ended")
        try:
            extra = await asyncio.wait_for(outcomes.__anext__(), 1.0)
        except StopAsyncIteration:
            extra = None
        except asyncio.TimeoutError:
            extra = "still running"
        assert extra is None, "serve ends once the redirects have ended and every token request has finished"

    asyncio.run(scenario())

    assert len(checked) == 3, "one token request per flow that got a code"
    by_resource = {fields.get("resource"): fields for fields in checked if fields.get("code") != spent_code}
    notes_fields = dict(by_resource.get(NOTES, {}))
    verifier = notes_fields.pop("code_verifier", "")
    assert notes_fields == {
        "grant_type": "authorization_code", "code": split_url(notes_redirect)[1]["code"],
        "redirect_uri": REDIRECT, "client_id": CIMD_URL, "resource": NOTES,
    }, "the token request carries the code as issued, the same redirect_uri and resource, and the client_id"
    assert challenge_of(verifier) == notes_challenge, "the code_verifier is the one behind the flow's code_challenge"
    assert by_resource.get(ARCHIVE, {}).get("code") == split_url(archive_redirect)[1]["code"], (
        "each token request carries its own flow's code"
    )
    kept = client.tokens.get((ISSUER, NOTES))
    assert kept is not None and kept.scope == "notes:write notes:read", "a token is kept under (issuer, resource)"
    assert client.call(NOTES, "notes.list") == ok("notes.list"), "the notes token works"
    assert client.call(ARCHIVE, "archive.search") == ok("archive.search"), "the archive token works"


@dataclass
class Page:
    status: int = 200
    content_type: str = "application/json"
    body: bytes = b'{"ok": true}'
    location: str | None = None
    latency: float = 0.0
    pulled: int = 0

    def chunks(self):
        for start in range(0, len(self.body), 1024):
            self.pulled += 1
            yield self.body[start:start + 1024]


class FakeInternet:
    """Fake DNS and HTTPS with a fake clock. Each lookup of a name takes the next of its answers;
    the last answer repeats."""

    def __init__(self) -> None:
        self.now = 0.0
        self.answers: dict[str, list[list[str]]] = {}
        self.lookups: list[str] = []
        self.pages: dict[str, Page] = {}
        self.requests: list[tuple[str, str, float]] = []

    def name(self, host: str, *answers: list[str]) -> None:
        self.answers[host] = [list(answer) for answer in answers]

    def page(self, url: str, **fields) -> Page:
        self.pages[url] = Page(**fields)
        return self.pages[url]

    def moved(self, url: str, location: str, status: int = 302, latency: float = 0.0) -> None:
        self.page(url, status=status, content_type="text/html", body=b"", location=location, latency=latency)

    def resolve(self, host: str) -> list[str]:
        self.lookups.append(host)
        answers = self.answers.get(host)
        if not answers:
            return []
        return list(answers.pop(0) if len(answers) > 1 else answers[0])

    def get(self, url: str, *, connect_to: str, timeout: float) -> Response:
        self.requests.append((url, connect_to, timeout))
        page = self.pages.get(url) or Page(status=404, content_type="text/html", body=b"")
        if page.latency > timeout:
            self.now += timeout
            raise TimeoutError(url)
        self.now += page.latency
        headers = {"Content-Type": page.content_type}
        if page.location is not None:
            headers["Location"] = page.location
        return Response(page.status, headers, page.chunks())


def outside(address: str) -> bool:
    """The test's own idea of an address the fetcher may connect to."""
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


def blocked(fetcher: SafeFetcher, url: str) -> bool:
    try:
        fetcher.fetch_json(url)
    except FetchBlocked:
        return True
    return False


def invalid(fetcher: SafeFetcher, client_id: str) -> bool:
    try:
        resolve_cimd(fetcher, client_id)
    except CimdInvalid:
        return True
    return False


def doc(**fields) -> bytes:
    return json.dumps(fields).encode("utf-8")


@pytest.mark.skip("Part 5")
def test_guarded_fetch() -> None:
    """Every hop of a redirect chain is checked on its own, and a CIMD names exactly its own URL."""
    addresses = {
        "93.184.216.34": True, "2606:4700::1111": True, "127.0.0.1": False, "10.1.2.3": False,
        "172.16.5.4": False, "192.168.0.7": False, "169.254.169.254": False, "100.64.0.10": False,
        "0.0.0.0": False, "224.0.0.251": False, "::1": False, "fe80::1": False, "fd00::5": False,
    }
    assert {address: public_address(address) for address in addresses} == addresses, (
        "only global unicast addresses may be fetched"
    )

    net = FakeInternet()
    cimd = {"client_id": CIMD_URL, "client_name": "Notes desktop", "redirect_uris": [REDIRECT]}
    for host, answer in (("client.example.com", "93.184.216.34"), ("cdn.example.net", "151.101.1.69"),
                         ("static.example.net", "151.101.1.70"), ("short.example.com", "93.184.216.37"),
                         ("meta.example.com", "93.184.216.38"), ("instance-data.example", "169.254.169.254"),
                         ("tailnet.example.com", "100.64.0.10"), ("down.example.com", "93.184.216.39"),
                         ("hops.example.com", "93.184.216.40"), ("loop.example.com", "93.184.216.41"),
                         ("html.example.com", "93.184.216.42"), ("jsonp.example.com", "93.184.216.43"),
                         ("list.example.com", "93.184.216.44"), ("huge.example.com", "93.184.216.45"),
                         ("slow.example.com", "93.184.216.46"), ("gone.example.com", "93.184.216.47"),
                         ("jump.example.com", "93.184.216.49"), ("exact.example.com", "93.184.216.50"),
                         ("garbled.example.com", "93.184.216.51")):
        net.name(host, [answer])
    net.name("flip.example.com", ["93.184.216.35"], ["127.0.0.1"])
    net.name("rebind.example.com", ["93.184.216.36"], ["10.0.0.7"])
    net.name("dual.example.com", ["93.184.216.48", "192.168.1.20"])

    net.page(CIMD_URL, body=json.dumps(cimd).encode("utf-8"))
    net.moved("https://jump.example.com/a", "https://cdn.example.net/c.json")
    net.moved("https://cdn.example.net/c.json", "/v2/c.json")
    net.page("https://cdn.example.net/v2/c.json", content_type="application/json; charset=utf-8")
    net.page("https://flip.example.com/x", content_type="Application/JSON")
    net.moved("https://short.example.com/go", "https://127.0.0.1/admin.json")
    net.moved("https://meta.example.com/go", "https://instance-data.example/latest/meta-data")
    net.moved("https://rebind.example.com/a", "/b")
    net.page("https://rebind.example.com/b")
    net.page("https://dual.example.com/x")
    net.page("https://tailnet.example.com/x")
    net.moved("https://down.example.com/a", "http://down.example.com/a", status=301)
    net.page("http://down.example.com/a")
    for i in range(4):
        net.moved(f"https://hops.example.com/{i}", f"/{i + 1}")
    net.page("https://hops.example.com/4")
    net.moved("https://loop.example.com/a", "https://loop.example.com/b", status=307)
    net.moved("https://loop.example.com/b", "https://loop.example.com/a", status=308)
    net.page("https://html.example.com/x", content_type="text/html", body=b"<html></html>")
    net.page("https://jsonp.example.com/x", content_type="application/jsonp")
    net.page("https://list.example.com/x", body=b"[1, 2]")
    net.page("https://huge.example.com/x", body=doc(padding="x" * 100_000))
    net.page("https://exact.example.com/x", body=doc(padding="x" * (64 * 1024 - 15)))  # exactly max_bytes
    net.page("https://garbled.example.com/x", body=b'{"ok": tru')
    net.moved("https://slow.example.com/0", "/1", latency=2.0)
    net.moved("https://slow.example.com/1", "/2", latency=2.0)
    net.page("https://slow.example.com/2", latency=2.0)
    net.page("https://gone.example.com/x", status=404)

    fetcher = SafeFetcher(net.resolve, net, max_redirects=3, max_bytes=64 * 1024, timeout=5.0, clock=lambda: net.now)
    assert attempt(lambda: fetcher.fetch_json(CIMD_URL)) == cimd, "a public https URL serving a JSON object is fetched"
    assert attempt(lambda: fetcher.fetch_json("https://jump.example.com/a")) == {"ok": True}, (
        "a relative Location is resolved against the URL that sent it; media type parameters are fine"
    )
    assert isinstance(attempt(lambda: fetcher.fetch_json("https://exact.example.com/x")), dict), (
        "a body of exactly max_bytes is not too long"
    )
    assert attempt(lambda: fetcher.fetch_json("https://flip.example.com/x")) == {"ok": True}, (
        "the media type is compared case-insensitively"
    )
    assert net.lookups.count("flip.example.com") == 1 and net.requests[-1][1] == "93.184.216.35", (
        "a hop resolves its host once and connects to the address it checked"
    )

    for url, why in (
        ("http://client.example.com/oauth/metadata.json", "plain http"),
        ("https://short.example.com/go", "a redirect to https://127.0.0.1/"),
        ("https://meta.example.com/go", "a redirect to a name that resolves to 169.254.169.254"),
        ("https://rebind.example.com/a", "a name that resolves to 10.0.0.7 on the next hop"),
        ("https://dual.example.com/x", "a name with a private address among its answers"),
        ("https://tailnet.example.com/x", "an address in 100.64.0.0/10"),
        ("https://[::1]/x", "the IPv6 loopback literal"),
        ("https://0.0.0.0/x", "the unspecified address"),
        ("https://down.example.com/a", "a redirect from https to http"),
        ("https://hops.example.com/0", "a fourth redirect"),
        ("https://loop.example.com/a", "a redirect loop"),
        ("https://html.example.com/x", "an HTML answer"),
        ("https://jsonp.example.com/x", "application/jsonp"),
        ("https://list.example.com/x", "a JSON array"),
        ("https://huge.example.com/x", "a body over max_bytes"),
        ("https://slow.example.com/0", "a chain that runs out of time"),
        ("https://gone.example.com/x", "a 404"),
        ("https://nowhere.example.com/x", "a name that does not resolve"),
        ("https://garbled.example.com/x", "a body that is not valid JSON"),
    ):
        assert blocked(fetcher, url), f"{why} is refused with FetchBlocked"

    assert all(outside(address) for _, address, _ in net.requests), "no connection ever goes to a disallowed address"
    visits = [url for url, _, _ in net.requests]
    assert [url for url in visits if "hops.example.com" in url] == [f"https://hops.example.com/{i}" for i in range(4)], (
        "at most three redirects are followed"
    )
    assert [url for url in visits if "loop.example.com" in url] == ["https://loop.example.com/a", "https://loop.example.com/b"], (
        "a redirect back to a URL already visited is refused at once"
    )
    assert net.pages["https://huge.example.com/x"].pulled <= 65, "an oversized body is abandoned as soon as it is too long"
    assert [timeout for url, _, timeout in net.requests if "slow.example.com" in url] == [5.0, 3.0, 1.0], (
        "all hops share one time budget: each gets what is left"
    )

    assert attempt(lambda: resolve_cimd(fetcher, CIMD_URL)) == cimd, "a valid Client ID Metadata Document comes back as it is"
    old = "https://client.example.com/oauth/old.json"
    net.moved(old, "https://static.example.net/old.json", status=301)
    net.page("https://static.example.net/old.json", body=doc(client_id=old, client_name="Notes", redirect_uris=[REDIRECT]))
    assert attempt(lambda: resolve_cimd(fetcher, old)) == {"client_id": old, "client_name": "Notes", "redirect_uris": [REDIRECT]}, (
        "a CIMD may be served through a redirect, as long as it names the URL it was asked for"
    )
    before = len(net.requests)
    for client_id, why in (("https://client.example.com", "a client_id without a path"),
                           ("https://client.example.com/", "a client_id whose path is /"),
                           ("http://client.example.com/oauth/metadata.json", "a client_id that is not https")):
        assert invalid(fetcher, client_id), f"{why} is not a CIMD client_id"
    assert len(net.requests) == before, "a client_id that cannot be a CIMD URL is never fetched"
    for name, body in (
        ("slash", doc(client_id=CIMD_URL.replace("metadata", "slash") + "/", client_name="Notes", redirect_uris=[REDIRECT])),
        ("moved", None),
        ("anonymous", doc(client_id=CIMD_URL.replace("metadata", "anonymous"), redirect_uris=[REDIRECT])),
        ("unnamed", doc(client_name="Notes", redirect_uris=[REDIRECT])),
        ("nowhere", doc(client_id=CIMD_URL.replace("metadata", "nowhere"), client_name="Notes", redirect_uris=[])),
        ("listless", doc(client_id=CIMD_URL.replace("metadata", "listless"), client_name="Notes", redirect_uris=REDIRECT)),
    ):
        url = CIMD_URL.replace("metadata", name)
        if body is None:
            net.moved(url, "https://static.example.net/moved.json", status=301)
            net.page("https://static.example.net/moved.json",
                     body=doc(client_id="https://static.example.net/moved.json", client_name="Notes", redirect_uris=[REDIRECT]))
        else:
            net.page(url, body=body)
    for name, why in (("slash", "a document whose client_id has an extra trailing slash"),
                      ("moved", "a document that names the URL it was redirected to"),
                      ("anonymous", "a document without client_name"),
                      ("unnamed", "a document without client_id"),
                      ("nowhere", "a document with no redirect_uris"),
                      ("listless", "a document whose redirect_uris is a string, not a list")):
        assert invalid(fetcher, CIMD_URL.replace("metadata", name)), f"{why} is refused with CimdInvalid"
