import asyncio
import gc
import json
import random
import re
import time

import pytest
from mcpcore.capabilities import missing_capabilities
from mcpcore.lifecycle import METHODS, check_request
from mcpcore.server import NotesServer
from mcpcore.tracer import trace
from mcpcore.transcript import NO_ID, Entry, Transcript
from mcpcore.wire import CAPABILITIES_KEY, CLIENT_INFO_KEY, VERSION_KEY, make_request


def error_of(reply) -> tuple:
    """(code, data) of an error response, (None, None) for anything else."""
    error = reply.get("error") if isinstance(reply, dict) else None
    if not isinstance(error, dict):
        return (None, None)
    return (error.get("code"), error.get("data"))


def text_of(reply):
    """The text of a successful tools/call result, None for anything else."""
    result = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(result, dict) or result.get("isError") is not False:
        return None
    return result["content"][0]["text"]


SEARCH = {
    "name": "notes_search",
    "description": "Search notes by keyword.",
    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}
LISTING = {
    "name": "notes_list",
    "description": "List note titles.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}


def notes_tools() -> list:
    """The lesson's two tools, registered in the lesson's order."""
    return [
        (SEARCH, lambda arguments: f"Found notes matching {arguments['query']!r}"),
        (LISTING, lambda arguments: "JSON-RPC notes, MCP metadata notes"),
    ]


def plain_tool(name: str) -> dict:
    return {"name": name, "description": f"Run {name}.", "inputSchema": {"type": "object", "properties": {}}}


@pytest.mark.skip("Part 1")
def test_stateless_requests() -> None:
    """Every request is built and answered from its own metadata, and nothing else."""
    server = NotesServer(notes_tools())
    search = {"name": "notes_search", "arguments": {"query": "json-rpc"}}
    future = make_request(1, "tools/call", search, version="2027-01-01")
    today = make_request(2, "tools/call", search)
    assert error_of(server.dispatch(future)) == (
        -32022,
        {"requested": "2027-01-01", "supported": ["2026-07-28"]},
    ), "a request for an unsupported version is refused with -32022"
    assert text_of(server.dispatch(today)) == "Found notes matching 'json-rpc'"
    search["arguments"]["query"] = "edited afterwards"
    assert today["params"]["arguments"] == {"query": "json-rpc"} and "_meta" not in search, (
        "the caller's params are neither shared with the request nor changed"
    )

    opted_in = make_request(3, "tools/list")
    opted_in["params"]["_meta"][CAPABILITIES_KEY]["extensions"] = {"io.modelcontextprotocol/tasks": {}}
    declared = {"extensions": {}}
    with_ui = make_request(4, "tools/list", capabilities=declared)
    with_ui["params"]["_meta"][CAPABILITIES_KEY]["extensions"]["io.modelcontextprotocol/ui"] = {}
    plain = make_request(5, "tools/list")
    assert plain["params"]["_meta"][CAPABILITIES_KEY] == {} and declared == {"extensions": {}}, (
        "a request declares only its own capabilities"
    )

    bare = make_request(6, "tools/list")
    del bare["params"]["_meta"][CAPABILITIES_KEY]
    assert error_of(server.dispatch(bare))[0] == -32602, (
        "missing capabilities are invalid params; they are never taken from an earlier request"
    )
    anonymous = make_request(7, "tools/list")
    del anonymous["params"]["_meta"][CLIENT_INFO_KEY]
    assert "result" in server.dispatch(anonymous), "clientInfo is recommended, not required"

    def listing(target: NotesServer) -> dict:
        return target.dispatch(make_request(8, "tools/list"))["result"]

    backward = NotesServer(reversed(notes_tools()))
    assert listing(server) == listing(backward) and [t["name"] for t in listing(server)["tools"]] == [
        "notes_list",
        "notes_search",
    ], "tools/list orders tools by name, whatever the registration order"

    rng = random.Random(6)
    names = [f"tool_{i:05d}" for i in range(20000)]
    rng.shuffle(names)  # plugins register their tools in no particular order
    many = NotesServer((plain_tool(name), lambda arguments: "ok") for name in names)
    calls = [make_request(i, "tools/call", {"name": rng.choice(names), "arguments": {}}) for i in range(500)]
    gc.collect()  # time the lookups, not a collection of the objects built above
    start = time.perf_counter()
    replies = [many.dispatch(call) for call in calls]
    elapsed = time.perf_counter() - start
    assert all(text_of(reply) == "ok" for reply in replies)
    assert elapsed < 0.04, "tools/call should stay fast with thousands of tools"

    assert len(listing(many)["tools"]) == 20000, "tools/list lists every tool"
    many.register(plain_tool("aaa_late"), lambda arguments: "registered late")
    late = make_request(9, "tools/call", {"name": "aaa_late"})
    assert text_of(many.dispatch(late)) == "registered late", "a tool registered later can be called"
    assert listing(many)["tools"][0]["name"] == "aaa_late", "a tool registered later is listed"


BIG_ID = 2**64 + 1
WIRE = [
    (1, "client", b'{"jsonrpc":"2.0","id":7,"method":"tools/list","params":{"_meta":'
     b'{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'),
    (2, "client", b'{"jsonrpc": "2.0", "id": "7", "method": "tools/call", "params": {"name": "notes_search",'
     b' "arguments": {"query": "caf\\u00e9"}, "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28",'
     b' "io.modelcontextprotocol/clientCapabilities": {}}}}'),
    (4, "server", b'{"jsonrpc":"2.0","id":"7","result":{"resultType":"complete","content":[{"type":"text",'
     b'"text":"Found notes matching \'caf\xc3\xa9\'"}],"isError":false}}\r'),
    (3, "server", b'{"jsonrpc":"2.0","id":7,"result":{"resultType":"complete","tools":[]}}'),
    (5, "client", b'{"jsonrpc":"2.0","method":"notifications/progress","params":{"progress":1}}'),
    (6, "client", b'{"jsonrpc":"2.0","id":8,"method":"tools/\xff'),
    (7, "server", b'{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}'),
    (11, "server", b'{"jsonrpc":"2.0","id":18446744073709551617,"error":{"code":-32022,'
     b'"message":"Unsupported protocol version","data":{"requested":"2027-01-01","supported":["2026-07-28"]}}}'),
    (10, "client", b'{"jsonrpc":"2.0","id":18446744073709551617,"method":"server/discover","params":{"_meta":'
     b'{"io.modelcontextprotocol/protocolVersion":"2027-01-01","io.modelcontextprotocol/clientCapabilities":{}}}}'),
]
ENTRIES = [
    Entry(1, "client", WIRE[0][2], "tools/list", 7),
    Entry(2, "client", WIRE[1][2], "tools/call", "7"),
    Entry(3, "server", WIRE[3][2], None, 7),
    Entry(4, "server", WIRE[2][2], None, "7"),
    Entry(5, "client", WIRE[4][2], "notifications/progress", NO_ID),
    Entry(6, "client", WIRE[5][2], None, NO_ID),
    Entry(7, "server", WIRE[6][2], None, None),
    Entry(10, "client", WIRE[8][2], "server/discover", BIG_ID),
    Entry(11, "server", WIRE[7][2], None, BIG_ID),
]


@pytest.mark.skip("Part 2")
def test_transcript_roundtrip(tmp_path) -> None:
    """A transcript gives back every line byte for byte, with each id exactly as it was sent."""
    path = str(tmp_path / "transcript.sqlite3")
    transcript = Transcript(path)
    recorded = [transcript.record(seq, direction, raw) for seq, direction, raw in WIRE]
    assert sorted(recorded, key=lambda entry: entry.seq) == ENTRIES, "record returns the entry it stored"
    with pytest.raises(ValueError):
        transcript.record(12, "proxy", b"{}")
    transcript.close()

    reopened = Transcript(path)
    entries = reopened.entries()
    assert [entry.seq for entry in entries] == [1, 2, 3, 4, 5, 6, 7, 10, 11], (
        "entries come back in seq order, whatever order they were recorded in"
    )
    assert [entry.raw for entry in entries] == [entry.raw for entry in ENTRIES], (
        "every line comes back byte for byte"
    )
    assert entries == ENTRIES, "a reopened transcript gives back every entry exactly"
    assert [e.seq for e in reopened.with_id(7)] == [1, 3] and [e.seq for e in reopened.with_id("7")] == [2, 4], (
        '7 and "7" are different ids'
    )
    assert [e.seq for e in reopened.with_id(None)] == [7], "a null id is an id; a notification has none"
    assert [e.seq for e in reopened.with_id(BIG_ID)] == [10, 11], "an id past 64 bits finds its messages, in seq order"
    reopened.close()


def meta(version="2026-07-28", capabilities=None, info=True) -> dict:
    body_meta = {VERSION_KEY: version, CAPABILITIES_KEY: {} if capabilities is None else capabilities}
    if info:
        body_meta[CLIENT_INFO_KEY] = {"name": "course-client", "version": "1.0.0"}
    return body_meta


def msg(request_id, method, *, version="2026-07-28", capabilities=None, info=True, **params) -> dict:
    """A modern request; the keyword arguments go into params next to _meta."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {**params, "_meta": meta(version, capabilities, info)},
    }


def edited(message: dict, **meta_changes) -> dict:
    """message with params._meta keys replaced; a value of ... removes the key."""
    body_meta = dict(message["params"]["_meta"])
    for key, value in meta_changes.items():
        key = {"version": VERSION_KEY, "capabilities": CAPABILITIES_KEY, "info": CLIENT_INFO_KEY}[key]
        if value is ...:
            body_meta.pop(key, None)
        else:
            body_meta[key] = value
    return {**message, "params": {**message["params"], "_meta": body_meta}}


def wire(message) -> bytes:
    return json.dumps(message).encode()


def http(method: str, version: str = "2026-07-28", name: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "MCP-Protocol-Version": version, "Mcp-Method": method}
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


UNSUPPORTED = {"requested": "2027-01-01", "supported": ["2026-07-28"]}
PROGRESS = {
    "jsonrpc": "2.0",
    "method": "notifications/progress",
    "params": {"progressToken": "t1", "progress": 1, "_meta": meta()},
}
LIFECYCLE = [
    # (rule, body, headers, expected (id, code, data), or None when the message passes)
    ("a body that is not JSON is -32700 with a null id",
     b'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"', None, (None, -32700, None)),
    ("a body that is not one JSON object is -32600 with a null id",
     wire([msg(2, "tools/list")]), None, (None, -32600, None)),
    ("jsonrpc must be \"2.0\"",
     wire({**msg("3", "tools/list"), "jsonrpc": "1.0"}), None, ("3", -32600, None)),
    ("method must be a string",
     wire({**msg(4, "tools/list"), "method": ["tools/list"]}), None, (4, -32600, None)),
    ("params must be an object",
     wire({"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": [meta()]}), None, (5, -32602, None)),
    ("params._meta is required",
     wire({"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}}), None, (6, -32602, None)),
    ("a version that is not a string is -32602, before any header is compared",
     wire(msg(7, "tools/list", version=20260728)), http("tools/list", version="2027-01-01"), (7, -32602, None)),
    ("missing capabilities are -32602, even with an unsupported version",
     wire(edited(msg(8, "tools/list", version="2027-01-01"), capabilities=...)), None, (8, -32602, None)),
    ("capabilities must be an object",
     wire(msg(9, "tools/list", capabilities=True)), http("tools/list"), (9, -32602, None)),
    ("a malformed clientInfo is -32602, even with an unsupported version",
     wire(edited(msg(10, "tools/list", version="2027-01-01"), info={"name": "course-client"})), None,
     (10, -32602, None)),
    ("clientInfo is optional",
     wire(msg(11, "tools/list", info=False)), http("tools/list"), None),
    ("a header version that differs from the body is -32020, even when the header version is unsupported",
     wire(msg(12, "tools/list")), http("tools/list", version="2027-01-01"), (12, -32020, None)),
    ("a header version that differs from the body is -32020, even when the body version is unsupported",
     wire(msg(13, "tools/list", version="2027-01-01")), http("tools/list"), (13, -32020, None)),
    ("over HTTP the mirrored headers are required, even when no headers came at all",
     wire(msg(25, "tools/list")), {}, (25, -32020, None)),
    ("Mcp-Method must equal the body's method, and it is compared before the version is checked",
     wire(msg(14, "tools/list", version="2027-01-01")), http("tools/call", version="2027-01-01"), (14, -32020, None)),
    ("Mcp-Name must equal params.name for tools/call, and it is compared before the version is checked",
     wire(msg(15, "tools/call", version="2027-01-01", name="notes.delete", arguments={})),
     http("tools/call", version="2027-01-01", name="notes.read"), (15, -32020, None)),
    ("Mcp-Name is required for tools/call over HTTP",
     wire(msg(16, "tools/call", name="notes_search", arguments={})), http("tools/call"), (16, -32020, None)),
    ("a version that header and body agree on, but the server does not support, is -32022",
     wire(msg("17", "tools/list", version="2027-01-01")), http("tools/list", version="2027-01-01"),
     ("17", -32022, UNSUPPORTED)),
    ("without HTTP there are no headers to compare",
     wire(msg(18, "tools/list", version="2027-01-01")), None, (18, -32022, UNSUPPORTED)),
    ("the version is checked before the method",
     wire(msg(19, "prompts/list", version="2027-01-01")), None, (19, -32022, UNSUPPORTED)),
    ("for resources/read Mcp-Name mirrors params.uri, and this server has no resources",
     wire(msg(20, "resources/read", uri="notes://welcome")), http("resources/read", name="notes://welcome"),
     (20, -32601, None)),
    ("an unknown method is -32601",
     wire(msg(21, "notes/delete")), None, (21, -32601, None)),
    ("a valid tools/call passes",
     wire(msg(22, "tools/call", name="notes_search", arguments={"query": "mcp"})),
     http("tools/call", name="notes_search"), None),
    ("a notification is never answered outside HTTP, however malformed",
     wire({"jsonrpc": "2.0", "method": "notifications/progress", "params": "oops"}), None, None),
    ("a notification is never answered outside HTTP, whatever is wrong with it",
     wire({"jsonrpc": "1.0", "method": "notifications/progress"}), None, None),
    ("over HTTP a notification is checked like a request, and its error has a null id",
     wire(PROGRESS), http("tools/list"), (None, -32020, None)),
    ("over HTTP a notification's version is checked too",
     wire(edited(PROGRESS, version="2027-01-01")), http("notifications/progress", version="2027-01-01"),
     (None, -32022, UNSUPPORTED)),
    ("over HTTP a notification that passes the checks gets no response",
     wire(PROGRESS), http("notifications/progress"), None),
]


def outcome(reply):
    """(id, code, data) of an error response, None when nothing is sent back.

    Only -32021 and -32022 define their data; other errors may carry data or not.
    """
    if reply is None:
        return None
    code, data = error_of(reply)
    return (reply.get("id", "no id member"), code, data if code in (-32021, -32022) else None)


@pytest.mark.skip("Part 3")
def test_request_lifecycle() -> None:
    """Each message is checked in the lesson's order; the first failing check decides the error."""
    for rule, body, headers, expected in LIFECYCLE:
        assert outcome(check_request(body, headers)) == expected, rule

    refused = check_request(wire(msg(23, "tools/list", version="2027-01-01")))
    refused["error"]["data"]["supported"].append("1999-01-01")
    assert error_of(check_request(wire(msg(24, "tools/list", version="2027-01-01"))))[1] == UNSUPPORTED, (
        "error data is the server's answer to one request, not its own list of versions"
    )


async def replay(messages: list):
    for message in messages:
        yield message


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


TRAFFIC = [
    make_request(1, "server/discover"),
    {"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete", "supportedVersions": ["2026-07-28"]}},
    make_request("req-7", "tools/call", {"name": "notes_delete", "arguments": {}}),
    make_request(7, "tools/list"),
    {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 1}},
    {"jsonrpc": "2.0", "id": 7, "result": {"resultType": "complete", "tools": []}},
    {"jsonrpc": "2.0", "id": "req-7", "error": {"code": -32602, "message": "Unknown tool: notes_delete"}},
    {"jsonrpc": "2.0", "id": 7, "result": {"resultType": "complete", "tools": []}},
    {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
    make_request(1, "tools/list", version="2027-01-01"),
    {"jsonrpc": "2.0", "id": 1, "error": {"code": -32022, "message": "Unsupported protocol version",
                                          "data": {"requested": "2027-01-01", "supported": ["2026-07-28"]}}},
    {"jsonrpc": "2.0", "id": 2, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "old", "version": "0.9"}}},
    {"jsonrpc": "2.0", "id": 2, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                                           "serverInfo": {"name": "old-notes", "version": "0.9"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    make_request(3, "tasks/get", {"taskId": "tsk_1"}),
    {"jsonrpc": "2.0", "id": 3, "error": {"code": -32021, "message": "Missing required client capability",
                                          "data": {"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}}}}},
    make_request(4, "tools/list"),
    {"jsonrpc": "2.0", "id": 4, "result": {"tools": []}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {"_meta": {VERSION_KEY: "2026-07-28"}}},
    {"jsonrpc": "2.0", "id": 5, "error": {"code": -32602, "message": "io.modelcontextprotocol/clientCapabilities must be an object"}},
    {"jsonrpc": "2.0", "id": 6, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "old", "version": "0.9"}}},
    {"jsonrpc": "2.0", "id": 6, "error": {"code": -32601, "message": "Method not found: initialize"}},
    ["not", "an", "envelope"],
    make_request(8, "tools/call", {"name": "notes_export", "arguments": {}},
                 capabilities={"extensions": {"io.modelcontextprotocol/tasks": {}}}),
    {"jsonrpc": "2.0", "id": 8, "result": {"resultType": "task", "taskId": "tsk_2", "status": "working"}},
    {"jsonrpc": "2.0", "id": 2, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                                           "serverInfo": {"name": "old-notes", "version": "0.9"}}},
]
TRACE = [
    "[request/modern] server/discover: version=2026-07-28 capabilities=current-request",
    "[response/modern] server/discover: resultType=complete",
    "[request/modern] tools/call: version=2026-07-28 capabilities=current-request",
    "[request/modern] tools/list: version=2026-07-28 capabilities=current-request",
    "[notification/unknown] notifications/progress: no response expected",
    "[response/modern] tools/list: resultType=complete",
    "[response/unknown] tools/call: code=-32602",
    "[orphan/modern] ?: resultType=complete",
    "[orphan/unknown] ?: code=-32700",
    "[request/modern] tools/list: version=2027-01-01 capabilities=current-request",
    "[response/modern] tools/list: code=-32022",
    "[request/legacy] initialize: connection-scoped handshake",
    "[response/legacy] initialize: resultType=absent",
    "[notification/legacy] notifications/initialized: no response expected",
    "[request/modern] tasks/get: version=2026-07-28 capabilities=current-request",
    "[response/modern] tasks/get: code=-32021",
    "[request/modern] tools/list: version=2026-07-28 capabilities=current-request",
    "[response/invalid] tools/list: resultType=absent",
    "[request/invalid] tools/list: missing modern request metadata",
    "[response/unknown] tools/list: code=-32602",
    "[request/legacy] initialize: connection-scoped handshake",
    "[response/unknown] initialize: code=-32601",
    "[unknown/invalid] : not a JSON-RPC message",
    "[request/modern] tools/call: version=2026-07-28 capabilities=current-request",
    "[response/modern] tools/call: resultType=task",
    "[orphan/invalid] ?: resultType=absent",
]
LINE = re.compile(r"\[([a-z]+)/([a-z]+)\] (\S*): (.+)")


@pytest.mark.skip("Part 4")
def test_trace_stream() -> None:
    """Every message gets one line on its own; a response finds its request by id."""
    text = "".join(collect(trace(replay(TRAFFIC))))
    assert text.endswith("\n") and "\n\n" not in text, "one line per message, each ending in a newline"
    lines = text.split("\n")[:-1]
    assert len(lines) == len(TRAFFIC), "one line per message"
    assert all(LINE.fullmatch(line) for line in lines), "every line is [kind/era] method: detail"
    fields = [LINE.fullmatch(line).groups() for line in lines]
    assert [fields[i][1] for i in (6, 8, 10, 15)] == ["unknown", "unknown", "modern", "modern"], (
        "-32020, -32021 and -32022 are modern evidence; other codes are not"
    )
    assert lines[5:7] == TRACE[5:7], "a response answers the request with its id, not the oldest one pending"
    assert lines[7] == TRACE[7], "a request answered once is no longer pending"
    assert fields[8][2] == "?", "a notification is never pending"
    assert lines[10] == TRACE[10], "an id can be used again once its request is answered"
    assert lines[11:14] == TRACE[11:14], "initialize, its result and notifications/initialized are legacy"
    assert lines[16:18] == TRACE[16:18], (
        "a result without resultType is legacy only when it answers initialize; nothing carries over"
    )
    assert lines[18] == TRACE[18], "a modern request carries both the protocol version and the capabilities"
    assert lines[19] == TRACE[19], "an invalid request still waits for its answer"
    assert lines[21] == TRACE[21], "an error's era comes from its code, even when it answers initialize"
    assert lines[24] == TRACE[24], "any resultType is modern evidence, not only complete"
    assert lines[25] == TRACE[25], "a result is legacy only when it answers initialize, whatever its fields"
    assert lines == TRACE, "label every message as the docstring says"

    pulled: list[int] = []

    async def live():
        for i, message in enumerate(TRAFFIC):
            pulled.append(i)
            yield message

    async def first_line() -> str:
        agen = trace(live())
        line = await agen.__anext__()
        await agen.aclose()
        return line

    assert asyncio.run(first_line()) == TRACE[0] + "\n"
    assert pulled == [0], "write each line as soon as its message arrives"


TASKS = {"extensions": {"io.modelcontextprotocol/tasks": {}}}
SYNC = {
    "extensions": {
        "io.modelcontextprotocol/tasks": {},
        "com.example.notes/sync": {"conflicts": {}, "attachments": {}},
    }
}


@pytest.mark.skip("Part 5")
def test_required_capabilities() -> None:
    """A method's nested capability requirement is checked whole; only the missing part is reported."""
    assert missing_capabilities(TASKS, {}) == TASKS, "nothing declared: the whole requirement is missing"
    assert missing_capabilities(TASKS, {"extensions": {"io.modelcontextprotocol/tasks": {}}}) == {}, (
        "an empty object declares support"
    )
    assert missing_capabilities(TASKS, {"extensions": {}}) == TASKS, (
        "an empty object declares that capability only, not what a requirement nests below it"
    )
    assert missing_capabilities(
        TASKS,
        {"sampling": {}, "extensions": {"io.modelcontextprotocol/tasks": {"ttl": 60}, "io.modelcontextprotocol/ui": {}}},
    ) == {}, "declaring more than required is fine"
    for value in (True, None, [], "io.modelcontextprotocol/tasks", 1):
        assert missing_capabilities(TASKS, {"extensions": {"io.modelcontextprotocol/tasks": value}}) == TASKS, (
            "only an object declares a capability"
        )
    assert missing_capabilities(TASKS, {"extensions": ["io.modelcontextprotocol/tasks"]}) == TASKS, (
        "only an object declares a capability"
    )
    for flattened in ({"extensions.io.modelcontextprotocol/tasks": {}}, {"extensions": {"io": {"modelcontextprotocol/tasks": {}}}}):
        assert missing_capabilities(TASKS, flattened) == TASKS, "keys are compared whole, dots and slashes included"
    declared = {"extensions": {"com.example.notes/sync": {"conflicts": {}}, "io.modelcontextprotocol/ui": {}}}
    assert missing_capabilities(SYNC, declared) == {
        "extensions": {"io.modelcontextprotocol/tasks": {}, "com.example.notes/sync": {"attachments": {}}}
    }, "report only what is missing"
    report = missing_capabilities(SYNC, {"extensions": {}})
    report["extensions"]["com.example.notes/sync"]["attachments"]["edited"] = True
    assert SYNC["extensions"]["com.example.notes/sync"] == {"conflicts": {}, "attachments": {}}, (
        "the result shares no objects with the requirement"
    )

    methods = METHODS | {"tasks/get", "notes/sync"}
    required = {"tasks/get": TASKS, "notes/sync": SYNC}

    def check(message: dict, headers=None):
        return outcome(check_request(wire(message), headers, methods=methods, required=required))

    assert check(msg(1, "tasks/get", taskId="tsk_1")) == (1, -32021, {"requiredCapabilities": TASKS}), (
        "a request without the capabilities its method needs is -32021"
    )
    ui_only = {"extensions": {"io.modelcontextprotocol/ui": {}}}
    assert check(msg("2", "tasks/get", capabilities=ui_only, taskId="tsk_1")) == (
        "2", -32021, {"requiredCapabilities": TASKS}
    ), "a request without the capabilities its method needs is -32021"
    partial = {"extensions": {"io.modelcontextprotocol/tasks": {}, "com.example.notes/sync": {"conflicts": {}}}}
    assert check(msg(10, "notes/sync", capabilities=partial)) == (
        10, -32021, {"requiredCapabilities": {"extensions": {"com.example.notes/sync": {"attachments": {}}}}}
    ), "-32021 reports only the part of the requirement the request is missing"
    assert check(msg(3, "tasks/get", capabilities=TASKS, taskId="tsk_1"), http("tasks/get", name="tsk_1")) is None, (
        "a request that declares what its method needs passes"
    )
    assert check(msg(4, "tools/list")) is None, "a method with no requirement needs nothing"
    assert check(msg(5, "tasks/get", taskId="tsk_1"), http("tasks/get", name="tsk_2")) == (5, -32020, None), (
        "headers are compared before the capabilities"
    )
    assert check(msg(6, "tasks/get", version="2027-01-01", taskId="tsk_1")) == (6, -32022, UNSUPPORTED), (
        "the version is checked before the capabilities"
    )
    assert check(msg(7, "tasks/get", capabilities=["extensions"], taskId="tsk_1")) == (7, -32602, None), (
        "capabilities that are not an object are -32602, not -32021"
    )
    refused = check_request(wire(msg(8, "tasks/get", taskId="tsk_1")), methods=methods, required=required)
    refused["error"]["data"]["requiredCapabilities"]["extensions"]["io.modelcontextprotocol/tasks"]["edited"] = True
    assert check(msg(9, "tasks/get", taskId="tsk_1")) == (
        9, -32021, {"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}}}
    ), "error data shares no objects with the server's requirements"
