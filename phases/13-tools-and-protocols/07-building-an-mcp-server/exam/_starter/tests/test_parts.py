import asyncio
import itertools
import json
import time

import pytest
from notesrv.dualera import DualEraServer
from notesrv.notedir import NoteDir
from notesrv.notes import MemoryNotes
from notesrv.server import NotesServer
from notesrv.stdio import serve_stdio

VERSION = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
SERVER_INFO = "io.modelcontextprotocol/serverInfo"
META = {VERSION: "2026-07-28", CAPABILITIES: {}, CLIENT_INFO: {"name": "exam-client", "version": "1.0.0"}}


def req(request_id, method: str, params: dict | None = None, meta: dict = META) -> dict:
    """A modern request. Every one carries its own _meta."""
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**(params or {}), "_meta": meta}}


@pytest.mark.skip("Part 1")
def test_dispatch_contract() -> None:
    """Each request is judged on its own, and each success carries exactly the right fields."""
    server = NotesServer(MemoryNotes())
    note = server.notes.create("Draft", "Ship the stdio loop.", tag="plan", owner="alice")
    assert note.id == "note-4", "ids count up after the three sample notes"

    read = server.handle(req(1, "resources/read", {"uri": f"notes://{note.id}"}), principal="alice")
    assert "result" in read, f"resources/read must find the note its URI names, got {read.get('error')}"
    result = read["result"]
    assert result["contents"][0]["text"] == "# Draft\n\nShip the stdio loop.\n\ntag: plan"
    assert result["resultType"] == "complete"
    assert result["_meta"] == {SERVER_INFO: {"name": "notesrv", "version": "2.0.0"}}
    assert "ttlMs" in result, "a resources/read result is cacheable, so it carries ttlMs"
    assert result["cacheScope"] == "private", "a user's note may only be cached privately"
    tools = server.handle(req(2, "tools/list"))["result"]
    assert tools["cacheScope"] == "public", "tool definitions are the same for everyone and stay public"

    prompt = server.handle(req(3, "prompts/get", {"name": "review_note", "arguments": {"note_id": note.id}}))
    assert prompt["result"]["messages"][0]["content"]["text"].endswith("Ship the stdio loop.")
    assert prompt["result"]["resultType"] == "complete"
    assert "ttlMs" not in prompt["result"] and "cacheScope" not in prompt["result"], (
        "only discovery, list and read results carry cache hints"
    )

    for bad in (True, 1.5, None, {"nested": "id"}, 2**53, -(2**53)):
        message = req(4, "tools/list")
        message["id"] = bad
        response = server.handle(message)
        assert response.get("error", {}).get("code") == -32600 and response["id"] is None, (
            f"id {bad!r} is not a string or a safe integer: -32600 with a null id"
        )
    for good in ("", "req-7", 0, 2**53 - 1, -(2**53 - 1)):
        response = server.handle(req(good, "tools/list"))
        assert "result" in response and response["id"] == good and type(response["id"]) is type(good), (
            f"id {good!r} is valid and comes back unchanged"
        )
    missing = server.handle(req("req-8", "resources/read", {"uri": "notes://note-99"}))
    assert missing.get("error", {}).get("code") == -32602 and missing["id"] == "req-8", (
        "an error answers a request with a valid id, so it carries that id"
    )

    notes = MemoryNotes()
    start = time.perf_counter()
    created = [notes.create(f"note {i}", "body").id for i in range(7000)]
    assert time.perf_counter() - start < 0.12, "creating a note must not get slower as the store grows"
    issued = {"note-1", "note-2", "note-3", *created}
    notes.delete(created[len(created) // 2])
    notes.delete(created[-1])
    fresh = {notes.create("again", "body").id for _ in range(2)}
    assert not fresh & issued, "a deleted note's id is never handed out again"


@pytest.mark.skip("Part 2")
def test_note_dir_roundtrip(tmp_path) -> None:
    """Notes survive a restart byte for byte, and no id is ever handed out twice."""
    root = tmp_path / "notes"
    bodies = [
        "first line\r\nsecond line  \r\n\r\n\tindented, no final newline   ",
        "classic Mac\rline endings\r",
        "emoji 🧪 and ünïcödé\n",
        "",
        "\n\n  between blank lines  \n\n",
    ]
    store = NoteDir(root)
    created = [store.create(f"  title {i}  ", body, tag="lab", owner="alice") for i, body in enumerate(bodies)]
    created.append(store.create("Shared", "nobody owns this one"))
    assert [note.id for note in created] == [f"note-{n}" for n in range(1, 7)], "ids count up from note-1"
    for note in created:
        assert (root / f"{note.id}.body").read_bytes() == note.body.encode("utf-8"), (
            "a body file holds exactly the body's UTF-8 bytes"
        )
    with pytest.raises(KeyError):
        store.get("note-99")
    with pytest.raises(KeyError):
        store.delete("note-99")

    reopened = NoteDir(root)
    assert reopened.all() == created, "after a reopen every note comes back exactly, oldest first"
    extra = [reopened.create(f"extra {i}", f"body {i}").id for i in range(6)]
    assert extra == [f"note-{n}" for n in range(7, 13)], "a reopened store keeps counting where it left off"
    assert [note.id for note in reopened.all()] == [f"note-{n}" for n in range(1, 13)], (
        "oldest first, so note-2 comes before note-10"
    )
    reopened.delete("note-12")
    reopened.delete("note-3")
    assert not list(root.glob("note-3.*")), "delete removes both of the note's files"

    restarted = NoteDir(root)
    assert restarted.create("after the restart", "x").id == "note-13", (
        "a deleted note's number is never handed out again, not even after a restart"
    )
    left = [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 13]
    assert [note.id for note in restarted.all()] == [f"note-{n}" for n in left], "deleted notes stay deleted"
    with pytest.raises(KeyError):
        restarted.get("note-3")
    read = NotesServer(restarted).handle(req(1, "resources/read", {"uri": "notes://note-1"}))
    assert read["result"]["contents"][0]["text"] == f"# {created[0].title}\n\n{bodies[0]}\n\ntag: lab", (
        "the server serves the note from disk unchanged"
    )


@pytest.mark.skip("Part 3")
def test_tool_call_errors() -> None:
    """tools/call keeps protocol errors and tool errors apart, and only a note's owner deletes it."""
    server = NotesServer(MemoryNotes())
    ids = itertools.count(1)

    def call(name: str, arguments, principal: str | None = "alice", meta: dict = META) -> dict:
        params = {"name": name, "arguments": arguments}
        return server.handle(req(next(ids), "tools/call", params, meta), principal=principal)

    for limit in (1, 50):
        found = call("notes_search", {"query": "MCP", "limit": limit, "highlight": True})
        assert found.get("result", {}).get("isError") is False, f"a valid call runs the tool, got {found}"
        assert json.loads(found["result"]["content"][0]["text"]) == [{"id": "note-1", "title": "MCP overview"}]
    listed = server.handle(req(next(ids), "tools/call", {"name": "notes_list"}), principal="alice")
    assert listed.get("result", {}).get("isError") is False, "arguments may be left out"

    for bad in (["MCP"], "MCP", None):
        response = call("notes_search", bad)
        assert response.get("error", {}).get("code") == -32602, (
            "arguments that are not an object are invalid params"
        )
    for arguments, name in (
        ({}, "query"),
        ({"query": 7}, "query"),
        ({"query": "MCP", "limit": 0}, "limit"),
        ({"query": "MCP", "limit": 51}, "limit"),
        ({"query": "MCP", "limit": "5"}, "limit"),
    ):
        result = call("notes_search", arguments).get("result", {})
        assert result.get("isError") is True and name in result["content"][0]["text"], (
            f"arguments that break the inputSchema are a tool error that names {name!r}"
        )
    unknown = call("notes_purge", {}).get("result", {})
    assert unknown.get("isError") is True, "an unknown tool is a tool error, not a protocol error"

    mine = server.notes.create("Mine", "only alice may delete this", owner="alice")
    impostor = {**META, CLIENT_INFO: {"name": "alice", "version": "1.0.0"}}
    refused = call("notes_delete", {"note_id": mine.id}, principal="bob", meta=impostor).get("result", {})
    assert refused.get("isError") is True and mine in server.notes.all(), (
        "only the owner may delete a note, and clientInfo proves nothing"
    )
    anonymous = call("notes_delete", {"note_id": "note-1"}, principal=None).get("result", {})
    assert anonymous.get("isError") is True and "note-1" in {n.id for n in server.notes.all()}, (
        "a note nobody owns cannot be deleted, not even by a caller nobody authenticated"
    )
    shared = call("notes_delete", {"note_id": "note-2"}).get("result", {})
    assert shared.get("isError") is True and "note-2" in {n.id for n in server.notes.all()}, (
        "a note nobody owns cannot be deleted by a signed-in caller either"
    )
    deleted = call("notes_delete", {"note_id": mine.id}).get("result", {})
    assert deleted.get("isError") is False and mine not in server.notes.all(), "the owner may delete the note"
    again = call("notes_delete", {"note_id": mine.id}).get("result", {})
    assert again.get("isError") is True, "deleting a note that is gone is a tool error"

    class BrokenDisk(MemoryNotes):
        def all(self):
            raise OSError(5, "Input/output error", "/srv/notesrv/note-3.json")

    logged: list[str] = []
    broken = NotesServer(BrokenDisk(), log=logged.append)
    params = {"name": "notes_search", "arguments": {"query": "MCP"}}
    response = broken.handle(req(next(ids), "tools/call", params), principal="alice")
    assert response.get("error", {}).get("code") == -32603, (
        "an executor that breaks is an internal error, not a tool result"
    )
    assert "/srv/notesrv" not in json.dumps(response), "the client learns nothing about the server's internals"
    assert any("/srv/notesrv" in entry for entry in logged), "the details go to the server log"


class Pipe:
    """A binary stdout or stderr that remembers how much of what it got was flushed."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.flushed = 0

    def write(self, data: bytes) -> int:
        self.data += data
        return len(data)

    def flush(self) -> None:
        self.flushed = len(self.data)


async def feed(data: bytes, sizes: list[int]):
    """Yield data in chunks whose sizes cycle through sizes; a 0 yields an empty chunk."""
    pos = 0
    for size in itertools.cycle(sizes):
        if pos >= len(data):
            return
        yield data[pos : pos + size]
        pos += size


def run_loop(server: NotesServer, reader, out: Pipe, err: Pipe) -> None:
    asyncio.run(asyncio.wait_for(serve_stdio(server, reader, out, err, "alice"), timeout=2))


class StdioServer(NotesServer):
    """The notes server, plus one note with non-ASCII text, recording who each request came from.

    Given the loop's stdout, it also records how many responses had been flushed when each
    request arrived.
    """

    def __init__(self, stdout: Pipe | None = None) -> None:
        super().__init__(MemoryNotes())
        self.notes.create("Ünïcode 🧪", "a body with\r\nCRLF", tag="exam", owner="alice")
        self.principals: list = []
        self.stdout = stdout
        self.answered: list[int] = []

    def handle(self, message: dict, principal: str | None = None) -> dict | None:
        self.principals.append(principal)
        if self.stdout is not None:
            self.answered.append(bytes(self.stdout.data[: self.stdout.flushed]).count(b"\n"))
        return super().handle(message, principal)


def shape(response: dict) -> tuple:
    if "error" in response:
        return ("error", response["id"], response["error"]["code"])
    return ("result", response["id"], response["result"])


STDIN_LINES = [
    json.dumps(req(1, "tools/list")).encode(),
    b"  \t ",
    json.dumps(req("café-🧪\u2028x", "resources/read", {"uri": "notes://note-4"}), ensure_ascii=False).encode()
    + b"\r",
    b'{"jsonrpc": "2.0", "id": 3, "method": "tools/list"',
    b"",
    json.dumps([req(4, "tools/list")]).encode(),
    b"42",
    b'{"jsonrpc": "2.0", "id": 5, "method": "tools/list", "note": "caf\xe9"}',
    json.dumps(req(6, "prompts/get", {"name": "review_note", "arguments": {"note_id": "note-4"}})).encode(),
    json.dumps(req(7, "server/discover")).encode(),
]


@pytest.mark.skip("Part 4")
def test_stdio_loop() -> None:
    """Newline-delimited JSON-RPC in and out, however stdin happens to be chunked."""
    stdin = b"\n".join(STDIN_LINES)  # the last message has no newline after it
    twin = StdioServer()

    def answer(line: bytes) -> tuple:
        return shape(twin.handle(json.loads(line), principal="alice"))

    expected = [
        answer(STDIN_LINES[0]),
        answer(STDIN_LINES[2]),
        ("error", None, -32700),
        ("error", None, -32600),
        ("error", None, -32600),
        ("error", None, -32700),
        answer(STDIN_LINES[8]),
        answer(STDIN_LINES[9]),
    ]
    for sizes in ([len(stdin)], [1], [7, 0, 30, 2, 50, 3]):
        out, err = Pipe(), Pipe()
        server = StdioServer(out)
        run_loop(server, feed(stdin, sizes), out, err)
        assert out.data.endswith(b"\n"), "every response is one line ending in a newline"
        responses = [json.loads(line) for line in bytes(out.data).split(b"\n")[:-1]]
        assert [shape(r) for r in responses] == expected, (
            f"one response per message, in order, whatever the chunking, e.g. {sizes[:6]}"
        )
        assert out.flushed == len(out.data), "flush every response"
        assert all(a < b for a, b in zip(server.answered, server.answered[1:])), (
            f"answer and flush each line before handling the next one; flushed per request: {server.answered}"
        )
        assert err.data, "lines that cannot be read are reported on stderr"
        assert set(server.principals) == {"alice"}, (
            "each request reaches the server with the transport's principal"
        )

    out, err = Pipe(), Pipe()
    answered: list[int] = []

    async def typing_client():
        for i in range(3):
            answered.append(bytes(out.data[: out.flushed]).count(b"\n"))
            yield json.dumps(req(i, "tools/list")).encode() + b"\n"

    run_loop(StdioServer(), typing_client(), out, err)
    assert answered == [0, 1, 2], "answer and flush each line before reading more input"


LEGACY_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {"roots": {}},
        "clientInfo": {"name": "old-desktop", "version": "0.9.0"},
    },
}


def legacy(request_id, method: str, params: dict | None = None) -> dict:
    """A 2025-11-25 request: no modern _meta, the connection's handshake stands in for it."""
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def error_code(response: dict | None):
    return (response or {}).get("error", {}).get("code")


def modern_fields(result: dict) -> set:
    found = {"resultType", "ttlMs", "cacheScope"} & result.keys()
    return found | ({SERVER_INFO} & result.get("_meta", {}).keys())


@pytest.mark.skip("Part 5")
def test_dual_era_connections() -> None:
    """A legacy handshake belongs to one connection, and modern requests never use it."""
    server = DualEraServer(NotesServer(MemoryNotes()))
    hello = server.handle("A", LEGACY_INIT)["result"]
    assert hello["protocolVersion"] == "2025-11-25"
    assert hello["serverInfo"] == {"name": "notesrv", "version": "2.0.0"}
    assert hello["capabilities"]["tools"] == {"listChanged": False}
    assert not modern_fields(hello), "a legacy initialize result has no modern fields"
    server.handle("A", {"jsonrpc": "2.0", "method": "notifications/initialized"})

    tools = server.handle("A", legacy(2, "tools/list"))["result"]
    read = server.handle("A", legacy(3, "resources/read", {"uri": "notes://note-1"}))["result"]
    names = [tool["name"] for tool in tools["tools"]]
    assert names == ["notes_create", "notes_delete", "notes_list", "notes_search"]
    assert read["contents"][0]["text"].startswith("# MCP overview")
    for result in (tools, read):
        assert not modern_fields(result), "legacy results carry no modern fields"
    discover = server.handle("A", legacy(4, "server/discover"))
    assert error_code(discover) == -32601, "server/discover is modern only"
    tracked = server.handle("A", legacy(5, "tools/list", {"_meta": {"progressToken": "list-5"}}))
    assert "result" in tracked, (
        "a legacy request may carry _meta of its own; only the modern keys make a request modern"
    )

    modern = server.handle("A", req(6, "tools/list")).get("result", {})
    assert modern.get("resultType") == "complete" and modern.get("cacheScope") == "public", (
        "a modern request on a legacy connection is still a modern request"
    )
    for request_id, partial_meta in ((7, {VERSION: "2026-07-28"}), (8, {CAPABILITIES: {}})):
        sent = list(partial_meta)
        partial = server.handle("A", req(request_id, "tools/list", meta=partial_meta))
        assert error_code(partial) == -32602, (
            f"{sent} alone: invalid params, and the handshake does not fill it in"
        )

    other = server.handle("B", legacy(9, "tools/list"))
    assert error_code(other) == -32602, "a handshake on A means nothing on B"
    modern_init = server.handle("C", req(10, "initialize", LEGACY_INIT["params"]))
    assert error_code(modern_init) == -32601, (
        "initialize with modern metadata is a modern request, for a method modern MCP does not have"
    )
    after = server.handle("C", legacy(11, "tools/list"))
    assert error_code(after) == -32602, "a modern initialize starts no handshake"

    asks_modern = {**LEGACY_INIT, "params": {**LEGACY_INIT["params"], "protocolVersion": "2026-07-28"}}
    assert server.handle("D", asks_modern).get("result", {}).get("protocolVersion") == "2025-11-25", (
        "the legacy door speaks only 2025-11-25, whatever the client asks for"
    )
    without_capabilities = {key: value for key, value in LEGACY_INIT["params"].items() if key != "capabilities"}
    assert error_code(server.handle("E", {**LEGACY_INIT, "params": without_capabilities})) == -32602
    after = server.handle("E", legacy(12, "tools/list"))
    assert error_code(after) == -32602, "a failed handshake leaves nothing behind"

    server.close("A")
    server.close("B")  # B never shook hands; its transport ends all the same
    assert error_code(server.handle("A", legacy(13, "tools/list"))) == -32602, (
        "close() forgets the connection's handshake"
    )
    assert "result" in server.handle("D", legacy(14, "tools/list")), "closing A leaves D's handshake alone"
