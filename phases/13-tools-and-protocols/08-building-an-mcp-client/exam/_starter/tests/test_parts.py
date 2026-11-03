import asyncio
import itertools
import json
import random
import time

import pytest
from multipeer.client import MultiServerClient
from multipeer.namespace import NamespaceError, Route, merge_namespace
from multipeer.negotiate import negotiate
from multipeer.peerconf import PeerConfig, load_peers, save_peers
from multipeer.pending import PendingCalls
from multipeer.pool import StdioPool, TransportLost
from multipeer.protocol import ProtocolError, Selection, modern_request

VERSION = "io.modelcontextprotocol/protocolVersion"
SERVER_INFO = "io.modelcontextprotocol/serverInfo"


def answer(message: dict, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def failure(message: dict, code: int, data=None) -> dict:
    error = {"code": code, "message": "rejected"}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": message["id"], "error": error}


def discover_result(name: str, versions) -> dict:
    return {
        "resultType": "complete",
        "supportedVersions": list(versions),
        "capabilities": {"tools": {}},
        "_meta": {SERVER_INFO: {"name": name, "version": "2.0.0"}},
    }


class ModernPeer:
    """An in-process modern MCP server. It checks each request's own _meta and keeps what it got."""

    def __init__(self, name: str, tools: list[str], versions=("2026-07-28",), result_type: bool = True):
        self.name, self.tools, self.versions, self.result_type = name, tools, list(versions), result_type
        self.received: list[dict] = []

    def __call__(self, message: dict, timeout_ms=None) -> dict:
        self.received.append(message)
        version = message["params"]["_meta"][VERSION]
        if version not in self.versions:
            return failure(message, -32022, {"requested": version, "supported": self.versions})
        if message["method"] == "server/discover":
            return answer(message, discover_result(self.name, self.versions))
        name = message["params"]["name"]
        text = f"[{self.name}] {name} ran" if name in self.tools else f"Unknown tool: {name}"
        result = {"content": [{"type": "text", "text": text}], "isError": name not in self.tools}
        if self.result_type:
            result["resultType"] = "complete"
        return answer(message, result)


class LegacyPeer:
    """A legacy server whose era was negotiated earlier: its results have no resultType."""

    def __init__(self, name: str, tools: list[str]):
        self.name, self.tools = name, tools
        self.received: list[dict] = []

    def __call__(self, message: dict, timeout_ms=None) -> dict:
        self.received.append(message)
        name = message["params"]["name"]
        text = f"[{self.name}] {name} ran" if name in self.tools else f"Unknown tool: {name}"
        return answer(message, {"content": [{"type": "text", "text": text}], "isError": name not in self.tools})


OLD_ARCHIVE = Selection("legacy", "2024-11-05", {"tools": {}}, {"name": "archive", "version": "0.9.0"})


def call_request(request_id) -> dict:
    return modern_request(request_id, "tools/call", {"name": "search", "arguments": {}}, "2026-07-28", {})


def reply(request_id) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"resultType": "complete"}}


@pytest.mark.skip("Part 1")
def test_route_calls() -> None:
    """Each call reaches the tool's owner in that peer's era, and each answer finds its own request."""
    notes = ModernPeer("notes", ["create", "search"], versions=["2026-07-28", "2027-01-01", "2099-01-01"])
    files = ModernPeer("files", ["read", "search"], versions=["2099-01-01", "2026-07-28"])
    archive = LegacyPeer("archive", ["restore", "search"])
    hub = ModernPeer("hub", ["notes/search"])
    client = MultiServerClient(modern_versions=("2026-07-28", "2027-01-01"))
    client.add_peer("notes", notes)
    client.add_peer("files", files)
    client.add_peer("archive", archive, OLD_ARCHIVE)
    client.add_peer("hub", hub)
    for name in ("notes", "files", "hub"):
        client.discover(name)
    client.routes = {
        "create": Route("notes", "create"),
        "files/search": Route("files", "search"),
        "hub/notes/search": Route("hub", "notes/search"),
        "notes/search": Route("notes", "search"),
        "read": Route("files", "read"),
        "restore": Route("archive", "restore"),
        "search": Route("archive", "search"),
    }

    client.call("create", {"title": "Draft"})
    client.call("read", {"path": "notes.md"})
    stamps = {peer.name: peer.received[-1]["params"]["_meta"][VERSION] for peer in (notes, files)}
    assert stamps == {"notes": "2027-01-01", "files": "2026-07-28"}, (
        "each request carries the highest version both sides support"
    )

    found = client.call("notes/search", {"query": "mcp"})
    assert found["content"][0]["text"] == "[notes] search ran", (
        "the owning peer receives the tool name it declared"
    )
    relayed = client.call("hub/notes/search", {"query": "mcp"})
    assert relayed["content"][0]["text"] == "[hub] notes/search ran", (
        "the owning peer receives the tool name it declared, even one with a '/' in it"
    )

    restored = client.call("restore", {"item": "box-7"})
    assert restored["resultType"] == "complete" and restored["content"][0]["text"] == "[archive] restore ran"
    assert "_meta" not in archive.received[-1]["params"], "a legacy peer gets requests in the legacy shape"
    assert client.call("search", {})["content"][0]["text"] == "[archive] search ran"

    client.add_peer("sloppy", ModernPeer("sloppy", ["ping"], result_type=False))
    client.discover("sloppy")
    client.routes["ping"] = Route("sloppy", "ping")
    try:
        client.call("ping", {})
    except ProtocolError:
        pass
    else:
        pytest.fail("a modern result without resultType is invalid")

    table = PendingCalls()
    table.add(call_request(1))
    table.add(call_request("1"))
    for bogus in (True, 1.0, None, [1]):
        try:
            table.resolve(reply(bogus))
        except ProtocolError:
            continue
        pytest.fail(f"an answer with id {bogus!r} matches no request")
    request, _ = table.resolve(reply("1"))
    assert request["id"] == "1", "the string id '1' and the integer id 1 are different requests"
    try:
        kept = table.resolve(reply(1))[0]
    except ProtocolError:
        kept = None
    assert kept is not None and kept["id"] == 1 and len(table) == 0, (
        "a rejected answer leaves the real request pending"
    )
    for request_id in range(3):
        table.add(call_request(request_id))
    table.resolve(reply(1))
    assert [request["id"] for request, _ in table.drain()] == [0, 2] and len(table) == 0, (
        "drain hands back what is still in flight, oldest first"
    )

    requests = [call_request(i) for i in range(5000)]
    answers = [reply(i) for i in range(5000)]
    random.Random(8).shuffle(answers)
    start = time.perf_counter()
    for request in requests:
        table.add(request)
    matched = [table.resolve(response)[0]["id"] for response in answers]
    elapsed = time.perf_counter() - start
    assert matched == [response["id"] for response in answers] and len(table) == 0
    assert elapsed < 0.1, "tracking and matching 5000 in-flight requests must not scan the table each time"


OPERATOR_FILE = """\
# Pinned MCP peers for the research host. Edited by hand.
[notes]
argv = python3 -m notes_server --root "/srv/research notes"

[archive]
argv = archive-mcp --listen 127.0.0.1:%PORT% --banner 'it'"'"'s 100% old'
allow_legacy = yes
legacy_revisions = 2025-11-25 2024-11-05
probe_timeout_ms = 275

[files]
endpoint = https://files.internal.example/mcp?team=a%20b
allow_legacy = off
"""

OPERATOR_PEERS = [
    PeerConfig("notes", argv=("python3", "-m", "notes_server", "--root", "/srv/research notes")),
    PeerConfig(
        "archive",
        argv=("archive-mcp", "--listen", "127.0.0.1:%PORT%", "--banner", "it's 100% old"),
        allow_legacy=True,
        legacy_revisions=("2025-11-25", "2024-11-05"),
        probe_timeout_ms=275,
    ),
    PeerConfig("files", endpoint="https://files.internal.example/mcp?team=a%20b"),
]

NOT_PINNED = [
    (
        "[DEFAULT]\nargv = any-mcp\nallow_legacy = true\nlegacy_revisions = 2025-11-25\n\n[notes]\nargv = notes-mcp\n",
        "a [DEFAULT] section would grant legacy to every peer",
    ),
    (
        "[*]\nargv = any-mcp\nallow_legacy = true\nlegacy_revisions = 2025-11-25\n",
        "a wildcard peer pins nothing",
    ),
    (
        "[files]\nendpoint = https://*.internal.example/mcp\nallow_legacy = true\nlegacy_revisions = 2025-11-25\n",
        "a wildcard endpoint pins nothing",
    ),
    (
        "[notes]\nargv = notes-mcp\n\n[notes]\nargv = other-mcp\nallow_legacy = true\nlegacy_revisions = 2025-11-25\n",
        "a peer is pinned once, not merged from two sections",
    ),
    (
        "[notes]\nargv = notes-mcp\nendpoint = https://notes.internal.example/mcp\n",
        "a peer has exactly one of argv or endpoint",
    ),
    ("[notes]\nprobe_timeout_ms = 500\n", "a peer has exactly one of argv or endpoint"),
    ("[archive]\nargv = archive-mcp\nallow_legacy = true\n", "allow_legacy needs the revisions it may accept"),
    ("[archive]\nargv = archive-mcp\nallow_legacy = sometimes\n", "allow_legacy is a boolean"),
    ("[archive]\nargv = archive-mcp\nprobe_timeout_ms = 0\n", "probe_timeout_ms is a positive integer"),
    ("[archive]\nargv = archive-mcp\nprobe_timeout_ms = -275\n", "probe_timeout_ms is a positive integer"),
]


@pytest.mark.skip("Part 2")
def test_peer_config_roundtrip(tmp_path) -> None:
    """Pinned peers survive a save and a reload exactly, and nothing that is not one pinned peer loads."""
    path = tmp_path / "peers.ini"
    path.write_text(OPERATOR_FILE, encoding="utf-8")
    assert load_peers(path) == OPERATOR_PEERS, "an operator's file loads as written, in file order"

    made = [
        PeerConfig(
            "Archive",
            argv=("node", "server.js", "--name", 'say "hi"', "", "  padded  ", "50%", "%PORT%", "#x", "a;b"),
            allow_legacy=True,
            legacy_revisions=("2025-11-25",),
            probe_timeout_ms=1,
        ),
        PeerConfig("archive", endpoint="https://archive.internal.example/mcp?q=%41&r=%%"),
        PeerConfig("files", argv=("files-mcp",), probe_timeout_ms=60_000),
    ]
    saved = tmp_path / "saved.ini"
    save_peers(saved, made)
    assert load_peers(saved) == made, "every pinned peer comes back exactly, in the same order"

    with pytest.raises(FileNotFoundError):
        load_peers(tmp_path / "missing.ini")
    for text, why in NOT_PINNED:
        path.write_text(text, encoding="utf-8")
        try:
            load_peers(path)
        except ValueError:
            continue
        pytest.fail(why)


class ScriptedPeer:
    """A stdio peer that answers from a script and keeps every message and deadline it got.

    A step is a function of the request, an exception to raise, or None for an empty answer.
    """

    def __init__(self, discover, initialize=None):
        self.steps = {"server/discover": discover, "initialize": initialize}
        self.sent: list[dict] = []
        self.deadlines: list = []

    def __call__(self, message: dict, timeout_ms=None):
        self.sent.append(message)
        self.deadlines.append(timeout_ms)
        if len(self.sent) > 4:
            pytest.fail("the client keeps probing: one retry and one initialize at most")
        step = self.steps.get(message["method"]) if "id" in message else None
        if isinstance(step, BaseException):
            raise step
        return step(message) if callable(step) else step

    @property
    def methods(self) -> list[str]:
        return [message["method"] for message in self.sent]


def modern_server(*versions):
    """server/discover answered the way a modern server answers it."""

    def step(message):
        asked = message["params"]["_meta"][VERSION]
        if asked not in versions:
            return failure(message, -32022, {"requested": asked, "supported": list(versions)})
        return answer(message, discover_result("srv", versions))

    return step


def refuse(code: int, data=None):
    return lambda message: failure(message, code, data)


GOOD_INIT = {
    "protocolVersion": "2025-11-25",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "archive", "version": "1.0.0"},
}


def legacy_answer(result=GOOD_INIT, **envelope):
    def step(message):
        response = answer(message, dict(result))
        response.update({key: value(message) if callable(value) else value for key, value in envelope.items()})
        return response

    return step


def without(result: dict, key: str) -> dict:
    return {k: v for k, v in result.items() if k != key}


BAD_INITIALIZE = [
    (TimeoutError("deadline exceeded"), "an initialize that times out"),
    (ConnectionError("transport closed"), "a peer that closes during initialize"),
    (None, "an empty answer"),
    (refuse(-32601), "an error answer"),
    (legacy_answer(id=lambda message: message["id"] + 1), "an answer to another request"),
    (legacy_answer(error={"code": -32603, "message": "both"}), "a result and an error together"),
    (legacy_answer(jsonrpc="1.0"), "an answer that is not JSON-RPC 2.0"),
    (legacy_answer({**GOOD_INIT, "protocolVersion": "2026-07-28"}), "a revision outside legacy_revisions"),
    (legacy_answer(without(GOOD_INIT, "protocolVersion")), "no protocolVersion"),
    (legacy_answer({**GOOD_INIT, "capabilities": ["tools"]}), "capabilities that are not an object"),
    (legacy_answer(without(GOOD_INIT, "capabilities")), "no capabilities"),
    (legacy_answer(without(GOOD_INIT, "serverInfo")), "no serverInfo"),
    (legacy_answer({**GOOD_INIT, "serverInfo": {"name": "", "version": "1.0.0"}}), "an empty serverInfo name"),
    (legacy_answer({**GOOD_INIT, "serverInfo": {"name": 7, "version": "1.0.0"}}), "a serverInfo name that is not a string"),
    (legacy_answer({**GOOD_INIT, "serverInfo": {"name": "archive", "version": ""}}), "an empty serverInfo version"),
    (legacy_answer({**GOOD_INIT, "serverInfo": {"name": "archive", "version": 1}}), "a serverInfo version that is not a string"),
]

LEGACY = Selection("legacy", "2025-11-25", {"tools": {}}, {"name": "archive", "version": "1.0.0"})
ARCHIVE = PeerConfig(
    "archive",
    argv=("archive-mcp",),
    allow_legacy=True,
    legacy_revisions=("2025-11-25", "2024-11-05"),
    probe_timeout_ms=275,
)
NOTES = PeerConfig("notes", argv=("notes-mcp",))


def probe(config: PeerConfig, peer: ScriptedPeer, versions=("2026-07-28", "2027-01-01")) -> Selection:
    return negotiate(config, peer, itertools.count(41), modern_versions=versions, discovery_timeout_ms=1000)


def fails(config: PeerConfig, peer: ScriptedPeer) -> bool:
    try:
        probe(config, peer)
    except ProtocolError:
        return True
    return False


@pytest.mark.skip("Part 3")
def test_era_negotiation() -> None:
    """Modern evidence keeps a peer modern; the legacy era needs the allowlist and a valid initialize."""
    peer = ScriptedPeer(modern_server("2026-07-28", "2027-01-01", "2099-01-01"))
    chosen = probe(NOTES, peer)
    assert (chosen.era, chosen.protocol_version) == ("modern", "2027-01-01")
    assert peer.methods == ["server/discover"] and peer.deadlines == [1000]
    assert peer.sent[0]["params"]["_meta"][VERSION] == "2026-07-28", "discovery probes with modern_versions[0]"

    peer = ScriptedPeer(modern_server("2026-07-28", "2027-01-01"), initialize=legacy_answer())
    chosen = probe(ARCHIVE, peer, versions=("2099-01-01", "2026-07-28", "2027-01-01"))
    assert peer.methods == ["server/discover", "server/discover"], (
        "-32022 means retry discovery, even for an allowlisted peer"
    )
    assert [message["id"] for message in peer.sent] == [41, 42], "the retry is a new request with a new id"
    assert peer.sent[1]["params"]["_meta"][VERSION] == "2027-01-01", (
        "retry at the highest version in error.data.supported that we support"
    )
    assert (chosen.era, chosen.protocol_version) == ("modern", "2027-01-01")

    for step, sent, why in (
        (refuse(-32020), 1, "-32020 proves a modern peer: correct the request, never initialize"),
        (refuse(-32021), 1, "-32021 proves a modern peer: correct the request, never initialize"),
        (refuse(-32022, {"supported": ["2099-01-01"]}), 1, "-32022 with no version in common fails"),
        (refuse(-32022, {"supported": ["2027-01-01"]}), 2, "one retry after -32022, then fail"),
    ):
        peer = ScriptedPeer(step, initialize=legacy_answer())
        assert fails(ARCHIVE, peer) and peer.methods == ["server/discover"] * sent, why

    for silence in (TimeoutError("deadline exceeded"), ConnectionError("closed"), None, refuse(-32601), refuse(-32603)):
        peer = ScriptedPeer(silence, initialize=legacy_answer())
        assert fails(NOTES, peer) and peer.methods == ["server/discover"], (
            "an ambiguous answer is no evidence: a peer that is not allowlisted never receives initialize"
        )

    for silence in (TimeoutError("deadline exceeded"), ConnectionError("closed"), None, refuse(-32601), refuse(-32602)):
        peer = ScriptedPeer(silence, initialize=legacy_answer())
        assert probe(ARCHIVE, peer) == LEGACY, "an allowlisted peer is legacy once initialize checks out"
        assert peer.methods == ["server/discover", "initialize", "notifications/initialized"]
        assert peer.deadlines[:2] == [1000, 275], "initialize runs under the peer's own probe_timeout_ms"
        params = peer.sent[1]["params"]
        assert params["protocolVersion"] == "2025-11-25" and "_meta" not in params, (
            "initialize is a legacy request for the first configured revision"
        )
        assert "id" not in peer.sent[2], "notifications/initialized is a notification"
    peer = ScriptedPeer(refuse(-32601), initialize=legacy_answer({**GOOD_INIT, "protocolVersion": "2024-11-05"}))
    assert probe(ARCHIVE, peer).protocol_version == "2024-11-05", "any revision in legacy_revisions is accepted"
    peer = ScriptedPeer(refuse(-32601), initialize=legacy_answer({**GOOD_INIT, "capabilities": {}}))
    assert not fails(ARCHIVE, peer), "an empty capabilities object is still an object"

    for step, why in BAD_INITIALIZE:
        peer = ScriptedPeer(refuse(-32601), initialize=step)
        assert fails(ARCHIVE, peer), f"fail closed on {why}"
        assert peer.methods == ["server/discover", "initialize"], (
            f"one initialize, and no notifications/initialized, after {why}"
        )


TOOLS = {
    "files": [{"name": "read"}, {"name": "restore"}, {"name": "search"}],
    "notes": [{"name": "restore", "annotations": {"readOnlyHint": True}}, {"name": "search"}],
    "flaky": [{"name": "lookup"}, {"name": "status"}],
    "slow": [{"name": "wait"}],
}

# How each run of each peer's process behaves; a peer's last entry covers every later run.
PLAN = {
    "files": [{"hold": 2}],  # answers its first two calls in reverse order
    "notes": [{"hold": 2, "then": "exit"}, {"versions": ("2026-07-28", "2027-01-01")}],
    "flaky": [{"exit_on": {"lookup"}}, {"exit_on": {"lookup"}}, {}],
    "slow": [{"gate": {"wait"}}],
}


class FakeStdout:
    def __init__(self) -> None:
        self.lines: asyncio.Queue = asyncio.Queue()
        self.eof = False

    async def readline(self) -> bytes:
        if self.eof and self.lines.empty():
            return b""
        return await self.lines.get()

    def send(self, message: dict) -> None:
        self.lines.put_nowait(json.dumps(message).encode() + b"\n")

    def close(self) -> None:
        self.eof = True
        self.lines.put_nowait(b"")


def parse(line: bytes):
    try:
        return json.loads(line)
    except ValueError:
        return None


class FakeStdin:
    def __init__(self, process: "FakeProcess") -> None:
        self.process = process
        self.data = bytearray()
        self.partial = b""

    def write(self, data: bytes) -> None:
        if self.process.exited:
            raise BrokenPipeError("the process has exited")
        self.data += data
        self.partial += data
        while b"\n" in self.partial:
            line, self.partial = self.partial.split(b"\n", 1)
            message = parse(line)
            if not isinstance(message, dict):
                pytest.fail(f"a peer's stdin carries one JSON-RPC message per line, got {line[:50]!r}")
            self.process.receive(message)

    async def drain(self) -> None:
        pass


class FakeProcess:
    """One run of a stdio MCP server. Its tool calls answer "[name#run] tool ran"."""

    def __init__(self, name, run, versions=("2026-07-28",), hold=0, then="reverse", exit_on=(), gate=()):
        self.name, self.run, self.versions = name, run, list(versions)
        self.hold, self.then, self.exit_on, self.gate = hold, then, set(exit_on), set(gate)
        self.stdin, self.stdout = FakeStdin(self), FakeStdout()
        self.exited = False
        self.held: list[dict] = []
        self.gated: list[dict] = []

    def receive(self, message: dict) -> None:
        if "id" not in message:
            return
        version = message["params"]["_meta"][VERSION]
        if version not in self.versions:
            self.stdout.send(failure(message, -32022, {"requested": version, "supported": self.versions}))
        elif message["method"] == "server/discover":
            self.stdout.send(answer(message, discover_result(self.name, self.versions)))
        elif message["method"] == "tools/list":
            listed = {"resultType": "complete", "tools": TOOLS[self.name], "ttlMs": 30000, "cacheScope": "public"}
            self.stdout.send(answer(message, listed))
        elif message["params"]["name"] in self.exit_on:
            self.exit()
        elif message["params"]["name"] in self.gate:
            self.gated.append(message)
        elif len(self.held) < self.hold:
            self.held.append(message)
            if len(self.held) == self.hold:
                if self.then == "exit":
                    self.exit()
                else:
                    for held in reversed(self.held):
                        self.stdout.send(self.ran(held))
                self.hold = 0
        else:
            self.stdout.send(self.ran(message))

    def ran(self, message: dict) -> dict:
        text = f"[{self.name}#{self.run}] {message['params']['name']} ran"
        return answer(message, {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": False})

    def release(self) -> None:
        for message in self.gated:
            self.stdout.send(self.ran(message))
        self.gated.clear()

    def exit(self) -> None:
        self.exited = True
        self.stdout.close()


def spawners(plan: dict) -> tuple[dict, dict]:
    started: dict[str, list[FakeProcess]] = {peer: [] for peer in plan}

    def spawner(peer: str):
        def spawn() -> FakeProcess:
            runs = started[peer]
            settings = plan[peer][min(len(runs), len(plan[peer]) - 1)]
            runs.append(FakeProcess(peer, len(runs) + 1, **settings))
            return runs[-1]

        return spawn

    return {peer: spawner(peer) for peer in plan}, started


def frames(process: FakeProcess) -> list[dict]:
    data = bytes(process.stdin.data)
    assert data.endswith(b"\n"), "every message on a peer's stdin ends with a newline"
    return [json.loads(line) for line in data.split(b"\n")[:-1]]


def calls(process: FakeProcess) -> list[tuple]:
    return [(frame["method"], frame["params"].get("name")) for frame in frames(process)]


def text(result: dict) -> str:
    return result["content"][0]["text"]


async def within(awaitable, why: str, seconds: float = 1.0):
    try:
        return await asyncio.wait_for(awaitable, seconds)
    except asyncio.TimeoutError:
        pass
    pytest.fail(why)


async def until(condition) -> None:
    while not condition():
        await asyncio.sleep(0.001)


@pytest.mark.skip("Part 4")
def test_stdio_pool() -> None:
    """Calls to stdio peers run concurrently; a peer that dies is restarted, and only safe calls go again."""
    spawn, started = spawners(PLAN)
    pool = StdioPool(
        spawn,
        retry_safe={"files": {"restore"}, "notes": {"search"}, "flaky": {"lookup"}},
        modern_versions=("2026-07-28", "2027-01-01"),
    )

    async def scenario():
        await within(pool.start(), "start() discovers and lists every peer")
        pair = asyncio.gather(pool.call("files", "read", {"path": "a.md"}), pool.call("files", "search", {"q": "b"}))
        read, search = await within(pair, "a peer may answer in any order; a call must not wait for the one before it")
        crash = asyncio.gather(
            pool.call("notes", "search", {"q": "c"}), pool.call("notes", "restore", {"item": "d"}), return_exceptions=True
        )
        retried, restore = await within(crash, "a peer that dies fails the calls it had in flight")
        lookup = await within(asyncio.gather(pool.call("flaky", "lookup", {}), return_exceptions=True), "retry once")
        status = await within(pool.call("flaky", "status", {}), "a call that finds its peer down restarts it first")
        waiting = asyncio.ensure_future(pool.call("slow", "wait", {}))
        await within(until(lambda: started["slow"][0].gated), "the call reaches the slow peer")
        quick = await within(pool.call("files", "read", {"path": "e.md"}), "a slow peer holds up only its own calls", 0.5)
        started["slow"][0].release()
        waited = await within(waiting, "the slow peer's answer reaches its call")
        return read, search, retried, restore, lookup[0], status, quick, waited

    read, search, retried, restore, lookup, status, quick, waited = asyncio.run(scenario())
    assert (text(read), text(search)) == ("[files#1] read ran", "[files#1] search ran"), (
        "each call gets its own answer, matched by id"
    )
    assert calls(started["files"][0])[:2] == [("server/discover", None), ("tools/list", None)]
    assert (text(quick), text(waited)) == ("[files#1] read ran", "[slow#1] wait ran")

    assert not isinstance(retried, BaseException) and text(retried) == "[notes#2] search ran", (
        "a call the operator marked retry-safe is sent again on the restarted peer"
    )
    assert isinstance(restore, TransportLost), (
        "a call not marked safe for its own peer fails with TransportLost: readOnlyHint is the server's claim, not the operator's"
    )
    lost, again = frames(started["notes"][0]), frames(started["notes"][1])
    assert calls(started["notes"][1]) == [("server/discover", None), ("tools/list", None), ("tools/call", "search")], (
        "a restarted peer is discovered and listed again before the safe call goes again"
    )
    first_try = next(frame["id"] for frame in lost if frame["params"].get("name") == "search")
    assert again[-1]["id"] != first_try, "a retried call gets a new JSON-RPC id"
    assert [frame["params"]["_meta"][VERSION] for frame in again] == ["2026-07-28", "2027-01-01", "2027-01-01"], (
        "a restart drops the cached era: the new process's versions decide what later requests carry"
    )

    assert isinstance(lookup, TransportLost), "a safe call is retried once, not until it succeeds"
    assert text(status) == "[flaky#3] status ran"
    assert [calls(process)[-1] for process in started["flaky"]] == [
        ("tools/call", "lookup"),
        ("tools/call", "lookup"),
        ("tools/call", "status"),
    ], "one retry per lost call; the next call restarts the peer again"


def tool(name: str) -> dict:
    return {"name": name, "description": f"{name} tool", "inputSchema": {"type": "object"}}


def rejects(catalogs: dict, policy: str = "prefix-on-collision") -> NamespaceError | None:
    try:
        merge_namespace(catalogs, policy=policy)
    except NamespaceError as error:
        return error
    return None


@pytest.mark.skip("Part 5")
def test_namespace_merge() -> None:
    """Every tool gets exactly one canonical name that routes back to it, whatever the connection order."""
    plain = {"notes": [tool("search"), tool("create")], "files": [tool("search"), tool("read")]}
    assert merge_namespace(plain) == {
        "create": Route("notes", "create"),
        "notes/search": Route("notes", "search"),
        "read": Route("files", "read"),
        "search": Route("files", "search"),
    }, "the first peer in sorted order keeps the bare name; a later owner is exposed as <peer>/<tool>"

    catalogs = {**plain, "hub": [tool("notes/search"), tool("read"), tool("files/read")]}
    assert merge_namespace(catalogs) == {
        "create": Route("notes", "create"),
        "hub/files/read": Route("hub", "files/read"),
        "hub/notes/search": Route("hub", "notes/search"),
        "hub/read": Route("hub", "read"),
        "notes/search": Route("notes", "search"),
        "read": Route("files", "read"),
        "search": Route("files", "search"),
    }, "a local name that already contains '/' is always prefixed, so it cannot pose as another peer's tool"
    reordered = {peer: list(reversed(tools)) for peer, tools in reversed(list(catalogs.items()))}
    assert list(merge_namespace(reordered).items()) == list(merge_namespace(catalogs).items()), (
        "the namespace does not depend on the order peers connected or listed their tools in"
    )

    rng = random.Random(13)
    names = ["search", "read", "b", "notes/search", "a/b", "hub/read", "x/y/z"]
    for _ in range(300):
        peers = rng.sample(["a", "b", "hub", "notes", "x"], rng.randint(1, 5))
        catalogs = {peer: [tool(name) for name in rng.sample(names, rng.randint(0, 4))] for peer in peers}
        routes = merge_namespace(catalogs)
        owned = sorted((peer, entry["name"]) for peer, tools in catalogs.items() for entry in tools)
        assert sorted((route.peer, route.local_name) for route in routes.values()) == owned, (
            f"every tool gets exactly one canonical name, never another tool's: {catalogs}"
        )
        for name, route in routes.items():
            back = [route.local_name] if "/" not in name else [route.peer, route.local_name]
            assert name.split("/", 1) == back, "a canonical name splits back into its peer and its local name"

    error = rejects(plain, "reject-on-collision")
    assert error is not None, "reject-on-collision refuses a duplicated tool name"
    assert "files" in str(error) and "notes" in str(error), "a collision error names both peers"
    gateway = {"hub": [tool("notes/search")], "notes": [tool("create")]}
    assert merge_namespace(gateway, "reject-on-collision") == {
        "create": Route("notes", "create"),
        "hub/notes/search": Route("hub", "notes/search"),
    }, "a '/' in a local name is no collision: it is prefixed under either policy"
    for policy in ("prefix-on-collision", "reject-on-collision"):
        assert rejects({"files": [tool("search"), tool("read"), tool("search")]}, policy), (
            "a peer that lists one name twice is a configuration error, under either policy"
        )
    assert rejects({"team/notes": [tool("search")]}), "a peer name with '/' would make prefixed names ambiguous"
