import asyncio
import base64
import io
import json
import string
import time

import pytest
from streamhttp.client import Outcome, ProtocolError, ResponseReader, StreamLost
from streamhttp.drafts import Draft, DraftStore, UnknownHandle, VersionConflict
from streamhttp.protocol import Principal
from streamhttp.server import HttpRequest, StreamableServer
from streamhttp.sse import SSE_HEADERS, Heartbeat, Progress, ToolResult, stream_tool_call
from streamhttp.wire import FramingError, HeaderMismatch, Headers, check_mirrored_headers, read_body

VERSION = "2026-07-28"
MIB = 1 << 20
STAMP = {"io.modelcontextprotocol/serverInfo": {"name": "streamhttp", "version": "1.0.0"}}
ALICE = Principal("alice", "acme")
MALLORY = Principal("mallory", "acme")


def rpc(request_id, method: str, params: dict | None = None, version: str = VERSION) -> dict:
    """A modern message: protocol version and client capabilities travel in params._meta.

    request_id None makes it a notification.
    """
    meta = {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    message["params"] = {**(params or {}), "_meta": meta}
    if request_id is None:
        del message["id"]
    return message


def encode(message: dict) -> bytes:
    return json.dumps(message).encode("utf-8")


def mirror(value: str) -> str:
    """Mcp-Name as a client writes it: visible ASCII as is, anything else in the Base64 sentinel."""
    plain = all(0x20 <= ord(c) <= 0x7E for c in value) and value == value.strip()
    if plain and not value.startswith("=?base64?"):
        return value
    return "=?base64?" + base64.b64encode(value.encode("utf-8")).decode("ascii") + "?="


def post_headers(message: dict, body: bytes, replace: dict | None = None, extra=()) -> list[tuple[str, str]]:
    """The headers a modern client sends with this POST. replace swaps a header, or drops it (None)."""
    params = message.get("params", {})
    version = params.get("_meta", {}).get("io.modelcontextprotocol/protocolVersion", VERSION)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Content-Length": str(len(body)),
        "MCP-Protocol-Version": version,
        "Mcp-Method": message["method"],
    }
    if message["method"] in ("tools/call", "prompts/get"):
        headers["Mcp-Name"] = mirror(params["name"])
    if message["method"] == "resources/read":
        headers["Mcp-Name"] = mirror(params["uri"])
    for name, value in (replace or {}).items():
        if value is None:
            del headers[name]
        else:
            headers[name] = value
    return [*headers.items(), *extra]


class Trickle:
    """A client connection that hands over at most `step` bytes per read."""

    def __init__(self, data: bytes, step: int = 1024) -> None:
        self._data = data
        self._pos = 0
        self.step = step
        self.reads = 0

    def read(self, n: int = -1) -> bytes:
        self.reads += 1
        size = self.step if n is None or n < 0 else min(n, self.step)
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def rest(self) -> bytes:
        return self._data[self._pos :]


def rejection(headers: Headers, message: dict) -> HeaderMismatch | None:
    """The HeaderMismatch that check_mirrored_headers raises, or None when the headers pass."""
    try:
        check_mirrored_headers(headers, message)
    except HeaderMismatch as exc:
        return exc
    return None


def refused(pairs: list[tuple[str, str]], stream: Trickle) -> bool:
    try:
        read_body(Headers(pairs), stream)
    except FramingError:
        return True
    return False


@pytest.mark.skip("Part 1")
def test_read_post() -> None:
    """Header names fold case and header values do not; the body is read fast and strictly."""
    search = rpc(7, "tools/call", {"name": "searchNotes", "arguments": {"query": "mcp"}})
    body = encode(search)
    # an HTTP/2 hop delivers every header name in lowercase
    lowered = Headers([(name.lower(), value) for name, value in post_headers(search, body)])
    assert read_body(lowered, Trickle(body, step=7)) == body, "a body arriving in small pieces is read whole"
    assert rejection(Headers(post_headers(search, body)), search) is None, "headers that mirror the body pass"
    assert rejection(lowered, search) is None, "header names are case-insensitive"

    shouting = Headers(post_headers(search, body, replace={"Mcp-Method": "Tools/Call"}))
    assert rejection(shouting, search) is not None, (
        "header values are case-sensitive: Tools/Call is not tools/call"
    )
    padded = Headers(post_headers(search, body, replace={"Mcp-Name": mirror("searchNotes ")}))
    assert rejection(padded, search) is not None, (
        "decoded values are compared exactly: a trailing space counts"
    )

    read = rpc(8, "resources/read", {"uri": "notes://笔记-1"})
    assert rejection(Headers(post_headers(read, encode(read))), read) is None, (
        "Mcp-Name mirrors params.uri for resources/read, compared after Base64 decoding"
    )
    other_note = Headers(post_headers(read, encode(read), replace={"Mcp-Name": mirror("notes://笔记-2")}))
    elsewhere = rejection(other_note, read)
    assert elsewhere is not None and elsewhere.code == -32020, "a Mcp-Name naming another resource is -32020"

    huge = b"x" * (12 * MIB)
    start = time.perf_counter()
    got = read_body(Headers([("Content-Length", str(len(huge)))]), Trickle(huge, step=4096), limit=16 * MIB)
    elapsed = time.perf_counter() - start
    assert got == huge, "the whole body comes back"
    assert elapsed < 0.1, "reading a body must take time linear in its size"

    chunked = [("Content-Length", "10"), ("transfer-encoding", "chunked")]
    for pairs, case in (
        ([], "a body without Content-Length"),
        ([("Content-Length", "10"), ("Content-Length", "12")], "conflicting Content-Length headers"),
        (chunked, "Content-Length with Transfer-Encoding"),
        ([("Content-Length", "١٠")], "a length in non-ASCII digits"),
        ([("Content-Length", "+10")], "a signed length"),
        ([("Content-Length", "0")], "an empty body"),
        ([("Content-Length", str(MIB + 1))], "a body over the limit"),
    ):
        stream = Trickle(b"0123456789NEXT")
        assert refused(pairs, stream) and stream.reads == 0, f"{case} is refused before the body is read"
    assert refused([("Content-Length", "10")], Trickle(b"01234")), (
        "a body shorter than Content-Length is refused"
    )
    pipelined = Trickle(b"0123456789NEXT")
    assert read_body(Headers([("Content-Length", "10")]), pipelined) == b"0123456789", (
        "the body is exactly Content-Length bytes"
    )
    assert pipelined.rest() == b"NEXT", "bytes after the body stay in the stream"


@pytest.mark.skip("Part 2")
def test_shared_drafts(tmp_path) -> None:
    """A draft saved through one replica loads exactly through another, for its owner, until it expires."""
    path = str(tmp_path / "drafts.sqlite3")
    now = [1_785_000_000_123]

    def clock() -> int:
        return now[0]

    replica_a = DraftStore(path, clock=clock, ttl_ms=900_000)
    replica_b = DraftStore(path, clock=clock, ttl_ms=900_000)
    text = "Agenda\r\n  1. transports  \n\u2028 2. 草稿 🧪\t"
    draft = replica_a.create(ALICE, text)
    assert (draft.version, draft.expires_at_ms) == (1, 1_785_000_900_123), (
        "a new draft is version 1 and expires ttl_ms after it is created"
    )
    loaded = replica_b.get(ALICE, draft.handle)
    assert loaded == draft, "a draft written by one replica loads exactly on another"
    assert type(loaded.expires_at_ms) is int and type(loaded.version) is int, "times are integer milliseconds"

    minted = [replica_a.create(ALICE, "a").handle for _ in range(20)]
    minted += [replica_b.create(ALICE, "b").handle for _ in range(20)]
    assert len({draft.handle, *minted}) == 41, "no two replicas ever mint the same handle"
    def random_bits(handle: str) -> int:
        return len(handle) * (4 if set(handle) <= set(string.hexdigits) else 6)

    assert all(random_bits(handle) >= 128 for handle in minted), "a handle carries at least 128 random bits"

    now[0] += 60_000
    saved = replica_b.save(ALICE, draft.handle, "v2", expected_version=1)
    assert saved == Draft(draft.handle, ALICE, 2, "v2", draft.expires_at_ms), (
        "a save bumps the version and keeps the expiry"
    )
    assert replica_a.get(ALICE, draft.handle) == saved, "every replica reads the latest save"
    with pytest.raises(VersionConflict) as stale:
        replica_a.save(ALICE, draft.handle, "a stale edit", expected_version=1)
    assert stale.value.current == 2, "a conflict reports the version now stored"
    assert replica_b.get(ALICE, draft.handle).text == "v2", "a stale save changes nothing"

    with pytest.raises(UnknownHandle) as never_issued:
        DraftStore(str(tmp_path / "elsewhere.sqlite3"), clock=clock).get(ALICE, draft.handle)
    for intruder in (MALLORY, Principal("alice", "globex")):
        with pytest.raises(UnknownHandle) as foreign:
            replica_b.get(intruder, draft.handle)
        assert str(foreign.value) == str(never_issued.value), (
            "someone else's handle fails exactly like one never issued"
        )
        with pytest.raises(UnknownHandle):
            replica_b.save(intruder, draft.handle, "taken over", expected_version=1)
    assert replica_a.get(ALICE, draft.handle).text == "v2", "an intruder changes nothing"

    now[0] = draft.expires_at_ms - 1
    assert replica_b.get(ALICE, draft.handle).version == 2, "a draft is live until its expiry instant"
    now[0] = draft.expires_at_ms
    with pytest.raises(UnknownHandle):
        replica_a.get(ALICE, draft.handle)
    with pytest.raises(UnknownHandle):
        replica_b.save(ALICE, draft.handle, "too late", expected_version=2)
    replica_a.close()
    replica_b.close()


def post(server, message, *, principal=ALICE, origin=None, replace=None, extra=(), path="/mcp", body=None):
    body = encode(message) if body is None else body
    headers = post_headers(message, body, replace, extra)
    if origin is not None:
        headers.append(("Origin", origin))
    return server.handle(HttpRequest("POST", path, headers, io.BytesIO(body), principal))


def reply(response) -> dict:
    media = (response.header("Content-Type") or "").split(";")[0].strip()
    assert media == "application/json", (
        f"a JSON-RPC body goes out as application/json: {response.status} {media!r}"
    )
    return json.loads(response.body)


def tool_payload(response) -> dict:
    result = reply(response)["result"]
    assert result["isError"] is False, f"the tool call succeeds: {result['content']}"
    return json.loads(result["content"][0]["text"])


@pytest.mark.skip("Part 3")
def test_http_responses(tmp_path) -> None:
    """Every request gets the status, headers and body that the 2026-07-28 transport defines."""

    def clock() -> int:
        return 1_785_000_000_000

    drafts = DraftStore(str(tmp_path / "drafts.sqlite3"), clock=clock)
    server = StreamableServer(drafts, allowed_origins=("http://localhost", "https://client.example"))
    listing = rpc(1, "tools/list")
    listed = post(server, listing)
    assert listed.status == 200 and reply(listed)["result"]["tools"], (
        "a valid POST gets its JSON-RPC response"
    )

    for method in ("GET", "DELETE", "PUT"):
        answer = server.handle(HttpRequest(method, "/mcp", [], io.BytesIO(b"")))
        assert (answer.status, answer.header("Allow")) == (405, "POST"), (
            f"{method} is not part of the modern transport: 405 with Allow: POST"
        )
    legacy = post(server, listing, path="/sse")
    assert legacy.status == 404 and b"jsonrpc" not in legacy.body, (
        "a missing endpoint is a plain 404, never a JSON-RPC error"
    )

    for origin in ("http://localhost", "https://client.example"):
        assert post(server, listing, origin=origin).status == 200, f"Origin {origin!r} is allowed"
    for origin in ("http://evil.example", "https://client.example.attacker.net", "http://127.0.0.1", "null"):
        assert post(server, listing, origin=origin).status == 403, (
            f"Origin {origin!r} is present and not exactly an allowed origin"
        )
    assert post(server, listing, origin="").status == 403, "an empty Origin header is present, not missing"
    hostile = server.handle(HttpRequest("GET", "/mcp", [("Origin", "http://evil.example")], io.BytesIO(b"")))
    assert hostile.status == 403, "Origin is checked before the method"

    future = rpc(2, "tools/list", version="2027-01-01")
    for message, header in ((listing, "2027-01-01"), (future, VERSION)):
        mixed = post(server, message, replace={"MCP-Protocol-Version": header})
        assert mixed.status == 400 and reply(mixed)["error"]["code"] == -32020, (
            "a header that disagrees with the body is -32020, even when one of the versions is unsupported"
        )
    unsupported = post(server, future)
    assert unsupported.status == 400 and reply(unsupported)["error"]["code"] == -32022, (
        "header and body agree on a version this server does not support: -32022"
    )
    assert reply(unsupported)["id"] == 2
    data = reply(unsupported)["error"].get("data")
    assert data == {"supported": ["2026-07-28"], "requested": "2027-01-01"}, (
        "-32022 names the supported versions and the requested one"
    )

    world = rpc(3, "tools/call", {"name": "ping-世界", "arguments": {}})
    decoded = post(server, world)
    assert decoded.status == 200 and reply(decoded)["result"]["isError"] is True, (
        "a Base64 Mcp-Name is decoded before it is compared; the unknown tool is a tool error"
    )
    for bad in ("=?base64?cGluZy3kuJbnlYw?=", "ping-世界", None):
        rejected = post(server, world, replace={"Mcp-Name": bad})
        assert rejected.status == 400 and reply(rejected)["error"]["code"] == -32020, (
            f"Mcp-Name {bad!r} is -32020"
        )
    bare = post(server, {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})
    assert bare.status == 400 and reply(bare)["error"]["code"] == -32602, "a request without _meta is invalid"

    for method in ("tools/list", "prompts/list"):
        accepted = post(server, rpc(None, method))
        assert (accepted.status, accepted.body) == (202, b""), (
            f"an accepted notification ({method}) is 202 with no body"
        )
    mislabeled = post(server, rpc(None, "tools/list"), replace={"Mcp-Method": "tools/call"})
    assert mislabeled.status == 400 and reply(mislabeled)["error"]["code"] == -32020, (
        "a notification is checked like a request before it is accepted"
    )
    from_the_future = post(server, rpc(None, "tools/list", version="2027-01-01"))
    assert from_the_future.status == 400 and reply(from_the_future)["error"]["code"] == -32022, (
        "a notification's version is checked before it is accepted"
    )
    missing = post(server, rpc(5, "prompts/list"))
    assert missing.status == 404 and reply(missing)["error"]["code"] == -32601, (
        "an unknown method is 404 with a JSON-RPC -32601 body"
    )
    assert reply(missing)["id"] == 5
    malformed = post(server, rpc(14, "tools/call", {"name": "ping", "arguments": []}))
    assert malformed.status == 200 and reply(malformed)["error"]["code"] == -32602, (
        "only -32601 is a 404; any other JSON-RPC error from dispatch is 200"
    )

    removed = [("Mcp-Session-Id", "s-1"), ("Last-Event-ID", "41")]
    discover = post(server, rpc(6, "server/discover"), extra=removed)
    assert discover.status == 200 and discover.header("Mcp-Session-Id") is None, (
        "Mcp-Session-Id and Last-Event-ID are ignored, and no session id is minted or echoed"
    )
    framing = post(server, listing, extra=[("Content-Length", "3")])
    assert framing.status == 400 and reply(framing)["error"]["code"] == -32700, (
        "a body that cannot be framed is -32700"
    )
    assert reply(framing)["id"] is None, "a body that cannot be read has no id to echo"
    not_utf8 = b'{"jsonrpc":"2.0","id":1,"method":"tools/list","x":"\xff"}'
    for raw, kind in ((b"{not json", "JSON"), (not_utf8, "UTF-8")):
        garbage = post(server, listing, body=raw)
        assert garbage.status == 400 and reply(garbage)["error"]["code"] == -32700, (
            f"a body that is not {kind} is -32700"
        )

    shared = str(tmp_path / "shared.sqlite3")
    replica_1 = StreamableServer(DraftStore(shared, clock=clock))
    replica_2 = StreamableServer(DraftStore(shared, clock=clock))

    def call_tool(replica, request_id, name, arguments, principal=ALICE):
        message = rpc(request_id, "tools/call", {"name": name, "arguments": arguments})
        return post(replica, message, principal=principal)

    created = tool_payload(call_tool(replica_1, 10, "draft_create", {"text": "outline"}))
    edit = {"handle": created["handle"], "version": 1, "text": "outline, v2"}
    saved = tool_payload(call_tool(replica_2, 11, "draft_save", edit))
    assert saved == {"handle": created["handle"], "version": 2}, (
        "a fresh POST to another replica continues the draft by its handle"
    )
    lookup = {"handle": created["handle"]}
    assert tool_payload(call_tool(replica_1, 12, "draft_read", lookup))["text"] == "outline, v2"
    stolen = call_tool(replica_2, 13, "draft_read", lookup, principal=MALLORY)
    assert reply(stolen)["result"]["isError"] is True, (
        "a handle works only for the authenticated caller who made it"
    )


async def drain(stream) -> list:
    return [chunk async for chunk in stream]


def parse_sse(raw: bytes) -> list[tuple[str, object]]:
    """Strictly parse what stream_tool_call writes: blocks ending in a blank line, one line each."""
    text = raw.decode("utf-8")
    assert text.endswith("\n\n"), "every event ends with a blank line"
    blocks = text[:-2].split("\n\n")
    assert not any(line.startswith("id:") for block in blocks for line in block.split("\n")), (
        "no SSE event ids: a modern stream is never resumed"
    )
    events: list[tuple[str, object]] = []
    for block in blocks:
        assert "\n" not in block, (
            f"each event is one line, a comment or a data line of compact JSON: {block[:50]!r}"
        )
        if block.startswith(":"):
            events.append(("comment", None))
        else:
            assert block.startswith("data: "), f"a message is a data line: {block[:50]!r}"
            events.append(("data", json.loads(block[len("data: ") :])))
    return events


def progress(token, value, total=None, message=None) -> dict:
    params = {"progressToken": token, "progress": value}
    if total is not None:
        params["total"] = total
    if message is not None:
        params["message"] = message
    return {"jsonrpc": "2.0", "method": "notifications/progress", "params": params}


@pytest.mark.skip("Part 4")
def test_request_scoped_sse() -> None:
    """A long tools/call streams its progress, then one final response, and then the stream ends."""
    resumed: list[bool] = []

    async def indexer():
        yield Progress(1, total=3, message="parsed 草稿")
        yield Heartbeat()
        yield Progress(2.5, total=3)
        yield ToolResult([{"type": "text", "text": "3 notes indexed"}])
        resumed.append(True)
        yield Progress(3, total=3)

    chunks = asyncio.run(drain(stream_tool_call(41, indexer(), progress_token=0)))
    assert chunks and all(isinstance(chunk, bytes) for chunk in chunks), (
        "the stream is written as UTF-8 bytes"
    )
    final = {
        "jsonrpc": "2.0",
        "id": 41,
        "result": {
            "resultType": "complete",
            "content": [{"type": "text", "text": "3 notes indexed"}],
            "isError": False,
            "_meta": STAMP,
        },
    }
    assert parse_sse(b"".join(chunks)) == [
        ("data", progress(0, 1, 3, "parsed 草稿")),
        ("comment", None),
        ("data", progress(0, 2.5, 3)),
        ("data", final),
    ], "progress notifications, a keepalive comment, then the final response"
    assert not resumed, "the stream ends with the final response; the tool is not read any further"
    untracked = parse_sse(b"".join(asyncio.run(drain(stream_tool_call(41, indexer())))))
    assert untracked == [("comment", None), ("data", final)], (
        "without a progress token there are no progress notifications"
    )

    pulled: list[int] = []
    closed: list[bool] = []

    async def crawler():
        try:
            for page in range(1, 1000):
                pulled.append(page)
                yield Progress(page)
                await asyncio.sleep(0)
        finally:
            closed.append(True)

    async def read_one_event_then_hang_up():
        steps = crawler()
        stream = stream_tool_call("crawl-1", steps, progress_token=9)
        first = b""
        while not first.endswith(b"\n\n"):
            first += await stream.__anext__()
        seen = list(pulled)
        await stream.aclose()
        return first, seen, list(closed)

    first, seen, closed_after_hang_up = asyncio.run(read_one_event_then_hang_up())
    assert parse_sse(first) == [("data", progress(9, 1))], (
        "the first event is the first progress notification"
    )
    assert seen == [1], "each event is written as soon as the tool produces it"
    assert closed_after_hang_up == [True], "closing the response stream cancels the call"


STREAM = (
    b": request-scoped stream\n\n"
    b'data: {"jsonrpc":"2.0","method":"notifications/progress",\n'
    b'data:  "params":{"progressToken":"t-41","progress":1,'
    b'"message":"caf\xc3\xa9 \xe2\x80\xa8 \xf0\x9f\xa7\xaa"}}\n'
    b"\n"
    b":\n"
    b"\n"
    b"event: message\r\n"
    b"id: 7\r\n"
    b"retry: 1000\r\n"
    b'data:{"jsonrpc":"2.0","method":"notifications/progress",\r\n'
    b'data:"params":{"progressToken":"t-41","progress":2}}\r\n'
    b"\r\n"
    b'data: {"jsonrpc":"2.0","id":41,"result":{"resultType":"complete",'
    b'"content":[{"type":"text","text":"ok"}],"isError":false}}\n'
    b"\n"
)
FIRST = progress("t-41", 1, message="café \u2028 🧪")
SECOND = progress("t-41", 2)
FINAL = {
    "jsonrpc": "2.0",
    "id": 41,
    "result": {"resultType": "complete", "content": [{"type": "text", "text": "ok"}], "isError": False},
}
SSE = [("content-type", "Text/Event-Stream; charset=UTF-8")]


def read_all(request_id, headers, pieces) -> Outcome:
    reader = ResponseReader(request_id, headers)
    for piece in pieces:
        reader.feed(piece)
    return reader.finish()


def failure(raw: bytes, headers=SSE) -> ProtocolError | None:
    try:
        read_all(41, headers, [raw])
    except ProtocolError as exc:
        return exc
    return None


@pytest.mark.skip("Part 5")
def test_layered_decoding() -> None:
    """HTTP picks the format, SSE frames the events, JSON-RPC sorts the messages, whatever the chunks."""
    reader = ResponseReader(41, SSE)
    end_of_first = STREAM.index(b"\n\n", STREAM.index(b"data")) + 2
    assert reader.feed(STREAM[:end_of_first]) == [FIRST], (
        "an event is delivered as soon as its blank line arrives"
    )
    assert reader.feed(STREAM[end_of_first:]) == [SECOND, FINAL]
    expected = Outcome([FIRST, SECOND], FINAL)
    assert reader.finish() == expected

    assert read_all(41, SSE, [STREAM[i : i + 1] for i in range(len(STREAM))]) == expected, (
        "one byte at a time, splitting characters and CRLF"
    )
    for cut in range(len(STREAM) + 1):
        assert read_all(41, SSE, [STREAM[:cut], STREAM[cut:]]) == expected, (
            f"the same messages wherever the chunks split, e.g. at byte {cut}"
        )

    body = '{"jsonrpc":"2.0","id":"req-7","result":{"tools":[{"name":"笔记"}]}}'.encode()
    json_headers = [("Content-Type", "application/json; charset=utf-8")]
    for cut in range(len(body) + 1):
        got = read_all("req-7", json_headers, [body[:cut], body[cut:]])
        assert got == Outcome([], json.loads(body)), "a JSON body is one response, however it is chunked"
    assert failure(b"<html></html>", [("Content-Type", "text/html")]) is not None, (
        "a body that is neither JSON nor SSE is a ProtocolError"
    )
    stray = failure(b'{"jsonrpc":"2.0","id":8,"result":{}}', [("Content-Type", "application/json")])
    assert isinstance(stray, ProtocolError) and not isinstance(stray, StreamLost), (
        "a JSON body that answers another request is a ProtocolError"
    )

    final = b'data: {"jsonrpc":"2.0","id":41,"result":{"resultType":"complete"}}\n\n'
    update = (
        b'data: {"jsonrpc":"2.0","method":"notifications/progress",'
        b'"params":{"progressToken":"t-41","progress":3}}\n\n'
    )
    sampling = b'data: {"jsonrpc":"2.0","id":"s-1","method":"sampling/createMessage","params":{}}\n\n'
    for raw, why in (
        (final + update, "nothing may follow the final response"),
        (sampling + final, "a server must not send requests on a request-scoped stream"),
        (final.replace(b'"id":41', b'"id":"41"'), 'a response to "41" is not the response to 41'),
    ):
        error = failure(raw)
        assert isinstance(error, ProtocolError) and not isinstance(error, StreamLost), why
    assert isinstance(failure(update), StreamLost), "a stream that ends before its final response is lost"
    assert isinstance(failure(final[:-1]), StreamLost), (
        "an event that the body ends in the middle of is dropped"
    )
    refusal = b'data: {"jsonrpc":"2.0","id":41,"error":{"code":-32602,"message":"bad query"}}\n\n'
    assert read_all(41, SSE, [update + refusal]).response["error"]["code"] == -32602, (
        "an error response to the request is its final response too"
    )

    async def tool():
        yield Progress(1, total=2, message="half way")
        yield Heartbeat()
        yield ToolResult([{"type": "text", "text": "done"}])

    chunks = asyncio.run(drain(stream_tool_call(9, tool(), progress_token="p-9")))
    decoded = read_all(9, list(SSE_HEADERS), chunks)
    assert decoded.notifications == [progress("p-9", 1, 2, "half way")], (
        "the client reads what the server streams"
    )
    assert decoded.response["result"]["content"] == [{"type": "text", "text": "done"}]
