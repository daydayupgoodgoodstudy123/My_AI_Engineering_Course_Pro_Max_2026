import asyncio
import copy
import gc
import io
import itertools
import json
import time

import pytest
from uricatalog.cache import ResponseCache
from uricatalog.catalog import Caller, Catalog, Note, sample_catalog
from uricatalog.client import CatalogClient
from uricatalog.server import CatalogServer
from uricatalog.templates import TemplateRouter

VERSION = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
SERVER_INFO = "io.modelcontextprotocol/serverInfo"
SUB = "io.modelcontextprotocol/subscriptionId"
META = {VERSION: "2026-07-28", CAPABILITIES: {}, CLIENT_INFO: {"name": "exam-host", "version": "1.0.0"}}
STAMP = {SERVER_INFO: {"name": "uricatalog", "version": "1.0.0"}}
UPDATED = "notifications/resources/updated"

ALICE = Caller("acme", "alice")
BOB = Caller("acme", "bob")


def req(request_id, method: str, params: dict | None = None) -> dict:
    """A 2026-07-28 request: every one carries its own _meta."""
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**(params or {}), "_meta": META}}


def error_code(response):
    return response.get("error", {}).get("code") if isinstance(response, dict) else None


def unknown_uri(uri: str) -> dict:
    return {"code": -32602, "message": "Unknown or invalid resource URI", "data": {"uri": uri}}


def ack(subscription_id, accepted: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {"_meta": {SUB: subscription_id}, "notifications": accepted},
    }


def updated(subscription_id, uri: str) -> dict:
    return {"jsonrpc": "2.0", "method": UPDATED, "params": {"_meta": {SUB: subscription_id}, "uri": uri}}


def list_changed(subscription_id, which: str) -> dict:
    method = f"notifications/{which}/list_changed"
    return {"jsonrpc": "2.0", "method": method, "params": {"_meta": {SUB: subscription_id}}}


def final(subscription_id) -> dict:
    """The response that ends a subscription gracefully: same id as the listen request."""
    return {
        "jsonrpc": "2.0",
        "id": subscription_id,
        "result": {"resultType": "complete", "_meta": {SUB: subscription_id, **STAMP}},
    }


def listen(server: CatalogServer, request_id, caller: Caller, notifications: dict):
    stream = server.handle(req(request_id, "subscriptions/listen", {"notifications": notifications}), caller)
    assert not isinstance(stream, dict), f"subscriptions/listen opens a stream, got {stream}"
    return stream


@pytest.mark.skip("Part 1")
def test_reads_prompts_and_subscriptions() -> None:
    """Every surface applies the same authorization, absence is an error, and delivery is exact."""
    server = CatalogServer(sample_catalog())
    salary = server.catalog.get("notes://note-3").text

    own = server.handle(req(1, "resources/read", {"uri": "notes://note-3"}), ALICE)["result"]
    assert own["contents"] == [{"uri": "notes://note-3", "mimeType": "text/markdown", "text": salary}]
    assert (own["ttlMs"], own["cacheScope"]) == (60_000, "private")

    review = {"name": "review_note", "arguments": {"uri": "notes://note-3", "focus": "tone"}}
    mine = server.handle(req(2, "prompts/get", review), ALICE)["result"]
    assert mine["messages"][0]["content"]["text"].endswith(salary), "review_note embeds the note"
    leak = server.handle(req(3, "prompts/get", review), BOB)
    assert leak.get("error") == unknown_uri("notes://note-3"), "a prompt is no side channel around resources/read"

    missing = server.handle(req(4, "resources/read", {"uri": "notes://missing"}), ALICE)
    assert missing.get("error") == unknown_uri("notes://missing"), "an unknown URI is invalid params, not an empty read"
    hidden = server.handle(req(5, "resources/read", {"uri": "notes://note-3"}), BOB)
    assert hidden.get("error") == unknown_uri("notes://note-3"), (
        "a note the caller may not read looks exactly like a missing one"
    )

    stream = listen(server, 17, ALICE, {
        "resourceSubscriptions": ["notes://note-2", "notes://note-1", "notes://note-2"],
        "promptsListChanged": "yes",
        "resourcesListChanged": True,
        "toolsListChanged": True,
    })
    accepted = {"resourcesListChanged": True, "resourceSubscriptions": ["notes://note-1", "notes://note-2"]}
    assert stream.sent == [ack(17, accepted)], "the acknowledgment lists only what the server accepted"
    for bad in ({"resourceSubscriptions": "notes://note-1"}, {"resourceSubscriptions": ["notes://note-1", 7]}, None):
        params = {} if bad is None else {"notifications": bad}
        response = server.handle(req(18, "subscriptions/listen", params), ALICE)
        assert error_code(response) == -32602, "a malformed filter is invalid params"
    loose = listen(server, 19, ALICE, {"promptsListChanged": 1, "resourcesListChanged": 1.0})
    assert loose.sent == [ack(19, {})], "a list-changed flag is accepted only when it is exactly true"

    twin = listen(server, 17, BOB, {"resourceSubscriptions": ["notes://note-1"], "promptsListChanged": True})
    other = listen(server, 23, ALICE, {"resourceSubscriptions": ["notes://note-1"]})
    tens = listen(server, 31, BOB, {"resourceSubscriptions": ["notes://note-10"]})
    flags = listen(server, 41, BOB, {"resourcesListChanged": True})
    hub = server.hub
    notified = hub.resource_updated("notes://note-1")
    assert tens.sent == [ack(31, {"resourceSubscriptions": ["notes://note-10"]})], (
        "notes://note-1 is not notes://note-10"
    )
    assert stream.sent[1:] == twin.sent[1:] == [updated(17, "notes://note-1")], "two clients may both listen with id 17"
    assert other.sent[1:] == [updated(23, "notes://note-1")], "each event carries its own stream's subscription id"
    assert notified == 3, "resource_updated returns how many streams it notified"
    assert hub.list_changed("prompts") == 1 and twin.sent[-1] == list_changed(17, "prompts"), (
        "list_changed goes only to streams that accepted it"
    )
    hub.close(stream)
    assert stream.sent[-1] == final(17), "closing ends the stream with a final response to the listen request"
    later = (hub.resource_updated("notes://note-1"), hub.list_changed("resources"))
    assert stream.sent[-1] == final(17), "a closed subscription hears nothing more"
    assert later == (2, 1) and flags.sent[1:] == [list_changed(41, "resources")]

    for s in range(100):
        listen(server, 1000 + s, ALICE, {"resourceSubscriptions": [f"notes://bulk-{s}-{u}" for u in range(3000)]})
    targets = [f"notes://bulk-{(7 * i) % 100}-{(13 * i) % 3000}" for i in range(1200)]
    gc.collect()
    start = time.perf_counter()
    counts = [hub.resource_updated(uri) for uri in targets]
    assert time.perf_counter() - start < 0.1, "delivering an update should stay fast with many subscriptions"
    assert counts == [1] * len(targets)


class Clock:
    """A clock the test moves by hand, in integer milliseconds."""

    def __init__(self, now: int) -> None:
        self.now = now

    def __call__(self) -> int:
        return self.now


def read_result(uri: str, text: str, ttl: int = 60_000, scope: str = "private") -> dict:
    return {
        "resultType": "complete",
        "contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}],
        "ttlMs": ttl,
        "cacheScope": scope,
        "_meta": copy.deepcopy(STAMP),
    }


def list_result(uris: list[str], next_cursor: str | None = None) -> dict:
    result = {
        "resultType": "complete",
        "resources": [{"uri": uri, "name": uri[8:], "description": "", "mimeType": "text/markdown"} for uri in uris],
        "ttlMs": 30_000,
        "cacheScope": "private",
        "_meta": copy.deepcopy(STAMP),
    }
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return result


PROMPT_LIST = {
    "resultType": "complete",
    "prompts": [{"name": "review_note", "title": "Review a note", "description": "Review one note", "arguments": []}],
    "ttlMs": 600_000,
    "cacheScope": "public",
    "_meta": STAMP,
}


@pytest.mark.skip("Part 2")
def test_response_cache_roundtrip(tmp_path) -> None:
    """Results come back exactly, only for the callers their hints allow, and survive a restart."""
    clock = Clock(1_000)
    path = str(tmp_path / "responses")
    cache = ResponseCache(path, clock)
    salary = {"uri": "notes://note-3"}
    tricky = "Bänder 東京 🧪\r\nline two\u2028\x00 trailing  \ncut mid-emoji by a JavaScript server: \ud83e"
    private = read_result("notes://note-3", tricky)
    pristine = copy.deepcopy(private)
    assert cache.put("resources/read", salary, ALICE, "en", private) is True
    assert private == pristine, "put leaves the result it was given unchanged"
    assert cache.get("resources/read", salary, ALICE, "en") == pristine, "a cached result comes back exactly"
    assert cache.get("resources/read", salary, BOB, "en") is None, "a private result is never shared with another user"
    assert cache.get("resources/read", salary, Caller("globex", "alice"), "en") is None, (
        "nor with a user of the same name in another tenant"
    )
    assert cache.get("resources/read", salary, ALICE, "fr") is None, "the locale is part of the key"
    assert cache.get("resources/read", {"uri": "notes://note-1"}, ALICE, "en") is None

    public = copy.deepcopy(PROMPT_LIST)
    assert cache.put("prompts/list", {}, ALICE, "en", public) is True
    for someone in (BOB, Caller("globex", "carol")):
        assert cache.get("prompts/list", {}, someone, "en") == public, "a public result may be reused for any caller"
    assert cache.get("prompts/list", {}, BOB, "de") is None, "the locale is part of the key"

    first = list_result(["notes://note-1", "notes://note-10"], next_cursor="eyJhZnRlciI6.c2ln")
    second = list_result(["notes://note-2"])
    assert cache.put("resources/list", {}, ALICE, "en", first) is True
    assert cache.put("resources/list", {"cursor": "eyJhZnRlciI6.c2ln"}, ALICE, "en", second) is True
    assert cache.get("resources/list", {}, ALICE, "en") == first
    assert cache.get("resources/list", {"cursor": "eyJhZnRlciI6.c2ln"}, ALICE, "en") == second, (
        "the cursor is part of the key"
    )
    assert cache.get("resources/list", {"cursor": "None"}, ALICE, "en") is None, (
        'a cursor that reads "None" is not a missing cursor'
    )

    note1 = {"uri": "notes://note-1"}
    zero = read_result("notes://note-1", "do not keep", ttl=0)
    no_store = read_result("notes://note-1", "do not keep", scope="no-store")
    bare = {k: v for k, v in read_result("notes://note-1", "do not keep").items() if k not in ("ttlMs", "cacheScope")}
    for result in (zero, no_store, bare):
        assert cache.put("resources/read", note1, ALICE, "en", result) is False, (
            "only a positive ttlMs with a public or private scope is stored"
        )
        assert cache.get("resources/read", note1, ALICE, "en") is None, (
            "only a positive ttlMs with a public or private scope is stored"
        )

    for sep in [chr(code) for code in range(128)] + ["::", "||", " | ", ", ", "\u2028", "\u241f"]:
        one, two = Caller(f"a{sep}b", "c"), Caller("a", f"b{sep}c")
        assert cache.put("resources/read", salary, one, "en", private) is True
        assert cache.get("resources/read", salary, two, "en") is None, (
            f"two callers never share a key, whatever their names contain ({sep!r})"
        )

    ten = {"uri": "notes://note-10"}
    ten_result = read_result("notes://note-10", "the June outage")
    cache.put("resources/read", note1, ALICE, "en", read_result("notes://note-1", "alice's copy"))
    cache.put("resources/read", note1, BOB, "en", read_result("notes://note-1", "bob's copy"))
    cache.put("resources/read", note1, BOB, "fr", read_result("notes://note-1", "everyone's copy", scope="public"))
    cache.put("resources/read", ten, ALICE, "en", ten_result)
    removed = cache.invalidate("notes://note-1")
    assert cache.get("resources/read", ten, ALICE, "en") == ten_result, "invalidate forgets that URI only"
    assert cache.get("resources/list", {}, ALICE, "en") == first, "invalidate forgets cached reads only"
    readers = ((ALICE, "en"), (BOB, "en"), (BOB, "fr"))
    gone = [cache.get("resources/read", note1, who, locale) for who, locale in readers]
    assert removed == 3 and gone == [None, None, None], (
        "invalidate forgets every cached read of that URI, for every caller"
    )

    clock.now = 2_000
    newer = read_result("notes://note-3", tricky + " (revised, and longer than before)")
    assert cache.put("resources/read", salary, ALICE, "en", newer) is True
    assert cache.get("resources/read", salary, ALICE, "en") == newer, "a newer result replaces the older one"
    cache.close()

    clock.now = 30_999
    reopened = ResponseCache(path, clock)
    assert reopened.get("resources/read", salary, ALICE, "en") == newer, "a reopened cache still has its entries"
    assert reopened.get("prompts/list", {}, BOB, "en") == public, "a reopened cache still has its entries"
    assert reopened.get("resources/read", note1, ALICE, "en") is None, "an invalidated entry stays gone"
    assert reopened.get("resources/list", {}, ALICE, "en") == first, "fresh until ttlMs has passed"
    clock.now = 31_000
    assert reopened.get("resources/list", {}, ALICE, "en") is None, "stale once ttlMs has passed, on the injected clock"
    clock.now = 61_999
    assert reopened.get("resources/read", salary, ALICE, "en") == newer, "fresh until ttlMs has passed"
    clock.now = 62_000
    assert reopened.get("resources/read", salary, ALICE, "en") is None, (
        "stale once ttlMs has passed, on the injected clock"
    )
    reopened.close()


def paging_catalog() -> Catalog:
    """n01 to n09 for acme, inserted out of order; n03, n06 and n09 are only for alice."""
    notes = [
        Note(f"notes://n{n:02d}", f"Note {n}", f"Paging fixture {n}", f"text {n}", "acme",
             readers=frozenset({"alice"}) if n % 3 == 0 else frozenset())
        for n in (5, 1, 9, 3, 7, 2, 8, 6, 4)
    ]
    notes.append(Note("notes://n00-globex", "Elsewhere", "Another tenant", "x", "globex"))
    return Catalog(notes)


@pytest.mark.skip("Part 3")
def test_resources_list_pages() -> None:
    """resources/list pages by URI, with signed cursors that any instance can continue."""
    catalog = paging_catalog()
    one = CatalogServer(catalog, secret=b"shared-secret", page_size=3)
    two = CatalogServer(catalog, secret=b"shared-secret", page_size=3)
    ids = itertools.count(1)

    def page(server: CatalogServer, caller: Caller, cursor=None) -> dict:
        params = {} if cursor is None else {"cursor": cursor}
        return server.handle(req(next(ids), "resources/list", params), caller)

    def resume(server: CatalogServer, cursor: str) -> dict:
        response = page(server, ALICE, cursor)
        assert "result" in response, (
            f"any instance with the same secret continues a listing, got {response.get('error')}"
        )
        return response["result"]

    first = page(one, ALICE)["result"]
    assert [r["uri"] for r in first["resources"]] == ["notes://n01", "notes://n02", "notes://n03"], (
        "the caller's resources, sorted by URI, three to a page"
    )
    assert first["resources"][0] == {
        "uri": "notes://n01", "name": "Note 1", "description": "Paging fixture 1", "mimeType": "text/markdown",
    }
    assert (first["ttlMs"], first["cacheScope"]) == (30_000, "private")
    assert isinstance(first.get("nextCursor"), str), "a page that is not the last carries a nextCursor"
    assert page(two, ALICE)["result"] == first, "the same request gets the same page, cursor and all"

    catalog.put(Note("notes://n00", "Note 0", "Added before the cursor", "text 0", "acme"))
    catalog.put(Note("notes://n015", "Note 1.5", "Added before the cursor", "text 1.5", "acme"))
    catalog.put(Note("notes://n045", "Appendix to note 4", "Added after the cursor", "text 4.5", "acme"))
    catalog.remove("notes://n07")
    catalog.remove("notes://n03")  # the last URI of the first page
    second = resume(two, first["nextCursor"])
    third = resume(one, second["nextCursor"])
    walked = [r["uri"] for p in (first, second, third) for r in p["resources"]]
    assert walked == [f"notes://n{n}" for n in ("01", "02", "03", "04", "045", "05", "06", "08", "09")], (
        "a resource added or removed between pages never makes another repeat or go missing"
    )
    assert "nextCursor" not in third, "the last page has no nextCursor"

    fresh = CatalogServer(paging_catalog(), secret=b"shared-secret", page_size=3)
    bobs = page(fresh, BOB)["result"]
    assert [r["uri"] for r in bobs["resources"]] == ["notes://n01", "notes://n02", "notes://n04"], (
        "pages are filled with resources the caller may read"
    )
    rest = page(fresh, BOB, bobs["nextCursor"])["result"]
    assert [r["uri"] for r in rest["resources"]] == ["notes://n05", "notes://n07", "notes://n08"]
    assert "nextCursor" not in rest, "the last page has no nextCursor, even when it is full"

    cursor = first["nextCursor"]
    for intruder in (BOB, Caller("globex", "alice")):
        assert error_code(page(one, intruder, cursor)) == -32602, "a cursor works only for the caller it was issued to"
    again = page(one, ALICE, cursor)["result"]
    variants = [
        cursor[:i] + swap + cursor[i + 1:] for i, char in enumerate(cursor) for swap in sorted({"A", "z", "0"} - {char})
    ]
    for variant in variants + [cursor[:-1], cursor[1:], cursor + ".x"]:
        forged = page(one, ALICE, variant)
        assert error_code(forged) == -32602 or forged.get("result") == again, (
            "a cursor cannot be changed without the server's secret"
        )
    elsewhere = CatalogServer(catalog, secret=b"another-secret", page_size=3)
    assert error_code(page(elsewhere, ALICE, cursor)) == -32602, "only a server with the same secret accepts a cursor"
    for junk in (42, ["notes://n03"], "", "garbage", "a.b", "\u00e9.\u00e9"):
        assert error_code(page(one, ALICE, junk)) == -32602, f"{junk!r} is not a cursor: invalid params"


class FakeChannel:
    """The server's end of one shared channel, as the test scripts it.

    Reads are answered from texts (a URI missing from texts is unreadable now); a read of hold is
    answered only once another read has arrived, or after a bounded wait. Everything else the
    server says is pushed by the test, in the order it arrives. None ends the channel.
    """

    def __init__(self, texts: dict[str, str], log: io.StringIO, hold: str) -> None:
        self.texts = texts
        self.log = log
        self.hold = hold
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.reads: list[str] = []
        self.answered = 0
        self.head_of_line = False
        self.log_at_first_read: str | None = None

    async def send(self, message: dict) -> None:
        if message.get("method") == "prompts/list":
            self.push({"jsonrpc": "2.0", "id": message["id"], "result": PROMPT_LIST})
        elif message.get("method") == "resources/read":
            if self.log_at_first_read is None:
                self.log_at_first_read = self.log.getvalue()
            uri = message["params"]["uri"]
            self.reads.append(uri)
            if uri == self.hold:
                asyncio.get_running_loop().create_task(self.answer_late(message, len(self.reads)))
            else:
                self.answer(message)

    def answer(self, message: dict) -> None:
        uri = message["params"]["uri"]
        if uri in self.texts:
            self.push({"jsonrpc": "2.0", "id": message["id"], "result": read_result(uri, self.texts[uri])})
        else:
            self.push({"jsonrpc": "2.0", "id": message["id"], "error": unknown_uri(uri)})
        self.answered += 1

    async def answer_late(self, message: dict, reads: int) -> None:
        for _ in range(500):
            if len(self.reads) > reads:
                break
            await asyncio.sleep(0)
        else:
            self.head_of_line = True
        self.answer(message)

    def push(self, message) -> None:
        self.inbox.put_nowait(message)

    async def receive(self):
        return await self.inbox.get()


async def settle(done, turns: int = 5000) -> None:
    """Let the client run until done() holds, giving up after a bounded number of loop turns."""
    for _ in range(turns):
        if done():
            return
        await asyncio.sleep(0)


@pytest.mark.skip("Part 4")
def test_shared_channel(tmp_path) -> None:
    """Three subscriptions and an ordinary request share one channel; each action is logged as it happens."""
    n1, n2, n3, n4 = "notes://note-1", "notes://note-2", "notes://note-3", "notes://note-4"
    cache = ResponseCache(str(tmp_path / "responses"), Clock(5_000))
    for uri in (n1, n2, n3):
        cache.put("resources/read", {"uri": uri}, ALICE, "en", read_result(uri, f"stale copy of {uri}"))
    out = io.StringIO()

    async def scenario():
        channel = FakeChannel({n1: "note-1, revised", n2: "note-2, revised", n4: "note-4, revised"}, out, hold=n1)
        client = CatalogClient(channel, cache, ALICE, "en", out)
        runner = asyncio.create_task(client.run())

        async def alongside(coro):
            """Await coro while run() keeps going; if run() stops first, surface why."""
            task = asyncio.ensure_future(coro)
            await asyncio.wait({task, runner}, return_when=asyncio.FIRST_COMPLETED)
            if not task.done():
                runner.result()
                raise AssertionError("run() must keep reading until the channel closes")
            return task.result()

        a = await client.listen({"resourceSubscriptions": [n1, n4]})
        b = await client.listen({"resourceSubscriptions": [n2]})
        c = await client.listen({"resourceSubscriptions": [n3, "notes://note-9"]})
        for message in (
            updated(c, n3),  # before c is acknowledged
            ack(a, {"resourceSubscriptions": [n1, n4]}),
            ack(b, {"resourceSubscriptions": [n2]}),
            updated(a, n1),  # the server answers a's re-read late
            updated(a, n4),
            ack(c, {"resourceSubscriptions": [n3]}),
            final(a),  # a ends while its re-read is in flight
            updated(b, n2),
            updated(c, n3),  # note-3 is no longer readable
        ):
            channel.push(message)
        listing = await alongside(client.request("prompts/list", {}))
        await settle(lambda: channel.answered >= 4 or runner.done())
        for message in (final(b), updated(b, n2), updated(99, n1), final(c)):  # after b ended; nobody's id
            channel.push(message)
        channel.push(None)
        await runner
        return a, b, c, listing, channel

    try:
        a, b, c, listing, channel = asyncio.run(asyncio.wait_for(scenario(), timeout=1.0))
    except asyncio.TimeoutError:
        pytest.fail("run() stalled: it must keep reading the channel while a re-read is in flight")

    text = out.getvalue()
    assert text.endswith("\n"), "every action is one line ending in a newline"
    records = [json.loads(line) for line in text.splitlines()]
    assert listing == PROMPT_LIST, "a response reaches its request by id, whatever arrives in between"

    rereads = {r["uri"]: r.get("text") for r in records if r.get("action") == "reread"}
    assert rereads == {n1: "note-1, revised", n2: "note-2, revised", n4: "note-4, revised"}, (
        "an update carries no document: forget the cached copy and read it again"
    )
    acks = {r["subscription"]: r.get("notifications") for r in records if r.get("action") == "acknowledged"}
    assert acks == {a: {"resourceSubscriptions": [n1, n4]}, b: {"resourceSubscriptions": [n2]},
                    c: {"resourceSubscriptions": [n3]}}, "log the filter the server acknowledged"
    dropped = sorted((r["subscription"], r.get("method")) for r in records if r.get("action") == "dropped")
    assert dropped == sorted([(c, UPDATED), (b, UPDATED), (99, UPDATED)]), (
        "an event counts only between its subscription's acknowledgment and final response"
    )

    def lifecycle(subscription_id) -> list:
        return [r for r in records if r.get("subscription") == subscription_id and r.get("action") != "dropped"]

    expected = {
        a: [{"action": "reread", "uri": n1, "text": "note-1, revised"},
            {"action": "reread", "uri": n4, "text": "note-4, revised"}],
        b: [{"action": "reread", "uri": n2, "text": "note-2, revised"}],
        c: [{"action": "unreadable", "uri": n3, "code": -32602}],
    }
    for subscription_id, events in expected.items():
        assert lifecycle(subscription_id) == [
            {"subscription": subscription_id, "action": "acknowledged", "notifications": acks[subscription_id]},
            *({"subscription": subscription_id, **event} for event in events),
            {"subscription": subscription_id, "action": "closed"},
        ], "each subscription logs its acknowledgment, then its events in order, then closed"
    assert not channel.head_of_line, "a slow re-read on one subscription must not hold up the others"
    early = [json.loads(line) for line in (channel.log_at_first_read or "").split("\n")[:-1]]
    assert lifecycle(a)[0] in early, "write each action as it happens"

    assert cache.get("resources/read", {"uri": n1}, ALICE, "en")["contents"][0]["text"] == "note-1, revised", (
        "the fresh read replaces the cached copy"
    )
    assert cache.get("resources/read", {"uri": n3}, ALICE, "en") is None, "an unreadable note leaves nothing cached"


TEMPLATES = (
    ("notes://projects/{project}/decisions/{decision}", "decision"),
    ("notes://projects/archive/decisions/{decision}", "archived-decision"),
    ("notes://projects/{project}/notes/{id}", "project-note"),
    ("notes://projects/{slug}/summary", "project-summary"),
    ("notes://projects/{project}", "project"),
    ("notes://{workspace}/roadmap/decisions/latest", "latest-roadmap-decision"),
    ("notes://{note}", "note"),
)


@pytest.mark.skip("Part 5")
def test_template_routes() -> None:
    """Templates compile into one tree: literals first, variables checked, nothing ambiguous."""
    router = TemplateRouter()
    for template, name in TEMPLATES:
        router.add(template, name)

    assert router.match("notes://projects/alpha/decisions/d-1") == ("decision", {"project": "alpha", "decision": "d-1"})
    assert router.match("notes://note-1") == ("note", {"note": "note-1"})
    assert router.match("notes://projects/archive/decisions/d-1") == ("archived-decision", {"decision": "d-1"}), (
        "a literal segment beats a variable"
    )
    assert router.match("notes://projects/roadmap/decisions/latest") == (
        "decision", {"project": "roadmap", "decision": "latest"}
    ), "the template with a literal at the first segment where they differ wins"
    assert router.match("notes://acme/roadmap/decisions/latest") == ("latest-roadmap-decision", {"workspace": "acme"})
    assert router.match("notes://projects/archive/notes/n_7") == ("project-note", {"project": "archive", "id": "n_7"}), (
        "a literal that leads nowhere does not hide a variable that matches"
    )
    assert router.match("notes://projects/archive") == ("project", {"project": "archive"}), (
        "a literal that leads nowhere does not hide a variable that matches"
    )
    assert router.match("notes://projects/alpha/summary") == ("project-summary", {"slug": "alpha"}), (
        "each template names its own variables"
    )

    assert router.match("notes://projects/%41lpha") == ("project", {"project": "Alpha"}), (
        "each segment is percent-decoded"
    )
    assert router.match("notes://projects/%2541lpha") is None, "a segment is percent-decoded exactly once"
    assert router.match("notes://projects/alpha%2Fdecisions%2Fd-1") is None, "an encoded / stays inside its segment"
    for uri in (
        "notes://projects/alpha/decisions/d-1/extra",
        "notes://projects/alpha/decisions",
        "notes://projects/alpha/decisions/",
        "notes://projects/alpha/",
        "notes://projects//decisions/d-1",
        "notes://",
    ):
        assert router.match(uri) is None, f"{uri}: extra or missing segments match nothing"
    for uri in ("notes:/projects/alpha", "file://projects/alpha", "notes:projects/alpha"):
        assert router.match(uri) is None, f"{uri}: only notes:// URIs match"

    longest = "a" * 64
    assert router.match(f"notes://projects/{longest}") == ("project", {"project": longest})
    for value in (
        "a" * 65, "al%20pha", "al.pha", "..", "alpha%0A", "%C3%9Cn%C3%AFcode", "Ünïcode", "alpha?draft=1", "%FFx",
    ):
        assert router.match(f"notes://projects/{value}") is None, (
            f"{value!r}: a variable is 1 to 64 ASCII letters, digits, - or _"
        )

    with pytest.raises(ValueError):
        router.add("notes://projects/{p}/decisions/{d}", "decision-again")
    assert router.match("notes://projects/alpha/decisions/d-1") == ("decision", {"project": "alpha", "decision": "d-1"}), (
        "a rejected template changes nothing"
    )
    for bad in (
        "notes://projects/{project}/links/{project}",
        "notes://projects/v{n}",
        "notes://projects/{project",
        "notes://projects//{x}",
        "notes://projects/{x}/",
        "notes://projects/{1x}",
        "file:///{path}",
    ):
        with pytest.raises(ValueError):
            router.add(bad, "bad")
