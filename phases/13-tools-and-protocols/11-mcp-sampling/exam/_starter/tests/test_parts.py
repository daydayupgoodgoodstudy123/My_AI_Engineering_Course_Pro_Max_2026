import asyncio
import base64
import copy
import csv
import hashlib
import hmac
import io
import itertools
import json
import re
import struct
import time
from collections import Counter

import pytest
from mrtrkit.approvals import Approval, Budget, Interaction, run_interactions
from mrtrkit.flow import DONE, Phase, advance, first_round, plan
from mrtrkit.host import HostError, drive
from mrtrkit.protocol import McpError, canonical, complete, input_required, request_meta, sampling_request
from mrtrkit.server import SummarizeServer
from mrtrkit.statetoken import Keyring, StateError, open_state, seal_state

SECRET = "correct horse battery staple"
REPO = {
    "README.md": "A small notes server used to teach stateless MCP.",
    "server.py": "def dispatch(request): return handle(request)",
    "client.py": "def retry(request, inputs, state): ...",
    "LICENSE": "MIT",
    "tests/test_server.py": "def test_stateless_retry(): ...",
    "docs/intro.md": "The server has no protocol session state.",
}


class Clock:
    """A fake clock in Unix seconds."""

    def __init__(self, now: int = 1_000_000_000) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_repo(root, extra=None):
    """The lesson's repository under root/repo, and a secret file next to it."""
    repo = root / "repo"
    for name, text in {**REPO, **(extra or {})}.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "secrets.txt").write_text("TOP-SECRET deploy key", encoding="utf-8")
    return repo


def call(audience: str = "developer") -> dict:
    """The params of a first summarize_repo request."""
    return {"name": "summarize_repo", "arguments": {"audience": audience}, "_meta": request_meta()}


def rpc(request_id: int, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}


def retry(params: dict, answers: dict, state: str) -> dict:
    return {**params, "inputResponses": answers, "requestState": state}


def reply(text: str) -> dict:
    """What the host's model returns for one sampling request."""
    return {"role": "assistant", "content": {"type": "text", "text": text}, "model": "host-model", "stopReason": "endTurn"}


def picks(*names: str) -> dict:
    return {"pick_files": reply(json.dumps(list(names)))}


def prompt_of(result: dict, key: str) -> str:
    return result["inputRequests"][key]["params"]["messages"][-1]["content"]["text"]


def error_code(response: dict):
    return response.get("error", {}).get("code")


def finish(server, params: dict, result: dict) -> dict:
    """Answer the summary round and return the structured result."""
    done = server.handle(rpc(99, retry(params, {"summary": reply("Two sentences.")}, result["requestState"])),
                         principal="user-42")
    return done["result"]["structuredContent"]


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@pytest.mark.skip("Part 1")
def test_mrtr_rounds(tmp_path) -> None:
    """summarize_repo over two MRTR rounds: bound to its caller and call, careful with model output, quick to retry."""
    clock = Clock()
    server = SummarizeServer(make_repo(tmp_path), SECRET, clock=clock)
    params = call()
    first = server.handle(rpc(1, params), principal="user-42")["result"]
    assert first["resultType"] == "input_required"
    state = first["requestState"]
    chosen = picks("README.md", "server.py", "docs/intro.md")

    second = server.handle(rpc(2, retry(params, chosen, state)), principal="user-42")
    assert "result" in second, f"a retry that repeats the call continues the flow, got {second.get('error')}"
    assert list(second["result"]["inputRequests"]) == ["summary"]

    body, signature = state.split(".")
    key = hashlib.pbkdf2_hmac("sha256", SECRET.encode(), b"mrtrkit/requestState", 600_000)
    assert unb64(signature) == hmac.new(key, unb64(body), hashlib.sha256).digest(), (
        "requestState is signed with the PBKDF2 key of the shared secret"
    )
    replica = SummarizeServer(server.repo, SECRET, clock=clock)
    assert "result" in replica.handle(rpc(3, retry(params, chosen, state)), principal="user-42"), (
        "any replica that knows the secret continues the flow"
    )
    stranger = SummarizeServer(server.repo, "another secret", clock=clock)
    assert error_code(stranger.handle(rpc(3, retry(params, chosen, state)), principal="user-42")) == -32602, (
        "a server with another secret rejects the state"
    )
    moved = retry(call("executive"), chosen, state)
    assert error_code(server.handle(rpc(4, moved), principal="user-42")) == -32602, (
        "a requestState is bound to the original arguments"
    )
    stolen = server.handle(rpc(5, retry(params, chosen, state)), principal="user-7")
    assert error_code(stolen) == -32602, "a requestState only works for the principal it was issued to"

    outside = str(tmp_path / "secrets.txt")
    sneaky = picks("../secrets.txt", "README.md", outside, "docs/../server.py", "./LICENSE")
    response = server.handle(rpc(6, retry(params, sneaky, state)), principal="user-42")
    assert "result" in response, f"picks the listing did not offer are dropped, not fatal, got {response.get('error')}"
    result = response["result"]
    assert "TOP-SECRET" not in prompt_of(result, "summary"), "model output names a file only if the listing offered it"
    assert finish(server, params, result)["picked"] == ["README.md"], (
        "model output names a file only if the listing offered it"
    )
    nothing = server.handle(rpc(7, retry(params, picks("../secrets.txt", outside), state)), principal="user-42")
    assert error_code(nothing) == -32602, "a pick with no offered file in it is invalid params"
    repeated = picks("README.md", "README.md", "LICENSE", "README.md", "client.py")
    result = server.handle(rpc(8, retry(params, repeated, state)), principal="user-42")["result"]
    assert finish(server, params, result)["picked"] == ["README.md", "LICENSE", "client.py"], (
        "picked files are distinct, in the model's order, at most three"
    )

    last = retry(params, {"summary": reply("Two sentences.")}, second["result"]["requestState"])
    start = time.perf_counter()
    for request_id in range(100, 124):
        assert "result" in server.handle(rpc(request_id, last), principal="user-42")
    assert time.perf_counter() - start < 0.1, "two dozen retries must not take long"

    clock.now += 300
    assert "result" in server.handle(rpc(10, last), principal="user-42"), (
        "a requestState is still valid at its expiresAt second"
    )
    clock.now += 1
    expired = server.handle(rpc(11, last), principal="user-42")
    assert error_code(expired) == -32602, "an expired requestState is rejected, even one that verified before"


def exact(value):
    """A comparable form that keeps types apart: 1, 1.0 and True differ, and so do 0.0 and -0.0."""
    if isinstance(value, dict):
        return ("dict", sorted((key, exact(item)) for key, item in value.items()))
    if isinstance(value, list):
        return ("list", [exact(item) for item in value])
    return (type(value).__name__, repr(value))


def rejected(token, ring, now=1_800_000_000) -> bool:
    try:
        open_state(token, ring, now)
    except StateError:
        return True
    except Exception as exc:  # noqa: BLE001 - the type is the point of the check
        pytest.fail(f"a bad token raises StateError, not {type(exc).__module__}.{type(exc).__qualname__}")
    return False


def forge(version: int, key_id: int, key: bytes, payload: bytes = b'{"phase":"pick"}') -> str:
    body = struct.pack(">BBQI", version, key_id, 1_800_000_300, len(payload)) + payload
    return b64(body + hmac.new(key, body, hashlib.sha256).digest())


@pytest.mark.skip("Part 2")
def test_state_token_roundtrip() -> None:
    """Version 1 requestState tokens: an exact round trip, an exact byte layout, and nothing else gets in."""
    old, new, staged = b"k" * 32, bytes(range(32)), bytes(range(32, 64))
    ring = Keyring({2: old, 7: new, 9: staged}, current=7)  # 9 is staged for the next rotation
    states = [
        {"phase": "pick", "round": 1, "picked": []},
        {
            "phase": "summarize",
            "round": 2,
            "picked": ["docs/设计.md", "naïve café.txt", "📄 notes.md", "e\u0301.md"],
            "scores": [0.1 + 0.2, 1e-310, -0.0, 1.7976931348623157e308, 2.0, 2],
            "nested": [[1, [2, [3, []]]], {"z": None, "a": True}],
        },
        {"big": 2**70, "empty": {}, "text": 'line\u2028break "quoted" \\ back'},
    ]
    for state in states:
        token = seal_state(state, ring, expires_at=1_800_000_300)
        assert re.fullmatch(r"[A-Za-z0-9_-]+", token), "a token is base64url without padding"
        assert exact(open_state(token, ring, now=1_800_000_000)) == exact(state), (
            "a state comes back exactly as it was sealed"
        )
        raw = unb64(token)
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        assert struct.unpack(">BBQI", raw[:14]) == (1, 7, 1_800_000_300, len(payload)), (
            "header: version 1, the current key id, expiresAt, payload length in bytes"
        )
        assert raw[14:-32] == payload, "the payload is canonical JSON in UTF-8"
        assert raw[-32:] == hmac.new(new, raw[:-32], hashlib.sha256).digest(), (
            "HMAC-SHA256 covers the header and the payload"
        )

    token = seal_state(states[1], ring, expires_at=1_800_000_300)
    assert not rejected(token, ring, now=1_800_000_300), "a token is valid at its expiresAt second"
    assert rejected(token, ring, now=1_800_000_301), "and expired one second later"

    raw = unb64(token)
    for i in range(len(raw)):
        for bit in (0x01, 0x80):
            assert rejected(b64(raw[:i] + bytes([raw[i] ^ bit]) + raw[i + 1 :]), ring), f"a change to byte {i} is caught"
    for cut in range(len(raw)):
        assert rejected(b64(raw[:cut]), ring), f"a token cut to {cut} bytes is caught"
    assert rejected(b64(raw + b"\x00"), ring), "a token with bytes added is caught"

    assert not rejected(forge(1, 2, old), ring), "tokens signed with an older key in the ring still open"
    assert open_state(forge(1, 2, old), ring, now=1_800_000_000) == {"phase": "pick"}
    assert rejected(forge(2, 7, new), ring), "an unknown version is rejected, even with a valid MAC"
    assert rejected(forge(1, 5, new), ring), "an unknown key id is rejected"
    assert rejected(token.replace("-", "+").replace("_", "/"), ring), "only base64url text opens"
    for bad in ({"score": float("nan")}, {"scores": [[1.0, float("inf")]]}):
        with pytest.raises(ValueError):
            seal_state(bad, ring, expires_at=1_800_000_300)


class Scripted:
    """A server that plays canned results in order, then completes, and records every request it gets."""

    def __init__(self, results: list) -> None:
        self.results = list(results)
        self.requests: list = []

    def __call__(self, request: dict) -> dict:
        self.requests.append(copy.deepcopy(request))
        result = self.results.pop(0) if self.results else complete(content=[])
        return {"jsonrpc": "2.0", "id": request["id"], "result": result}


HINTS = {"costPriority": 0.9, "speedPriority": 0.9, "intelligencePriority": 0.9}


def asking(*keys: str, state: str = "opaque", **params) -> dict:
    """An input_required result with one sampling request per key."""
    requests = {}
    for key in keys:
        request = sampling_request(f"Write the {key}.", HINTS)
        request["params"].update(params)
        requests[key] = request
    return input_required(requests, state)


ELICIT = {
    "method": "elicitation/create",
    "params": {"mode": "form", "message": "Choose a branch.", "requestedSchema": {"type": "object", "properties": {}}},
}


@pytest.mark.skip("Part 3")
def test_host_driver(tmp_path) -> None:
    """The host drives MRTR rounds to the end, and refuses what it must not fulfil."""
    server = SummarizeServer(make_repo(tmp_path), SECRET, clock=Clock())
    sent, answered, shown, seen = [], [], [], []

    def send(request):
        sent.append(copy.deepcopy(request))
        answered.append(server.handle(request, principal="user-42"))
        return answered[-1]

    def approve(key, request):
        shown.append((key, request["method"]))
        return True

    def model(params):
        seen.append(copy.deepcopy(params))
        if "Choose" in params["messages"][-1]["content"]["text"]:
            return reply(json.dumps(["README.md", "docs/intro.md"]))
        return reply("A stateless MCP server and its retry loop.")

    params = call()
    original = copy.deepcopy(params)
    result = drive(send, "tools/call", params, approve=approve, model=model, ids=itertools.count(41))
    assert result["structuredContent"] == {
        "picked": ["README.md", "docs/intro.md"],
        "summary": "A stateless MCP server and its retry loop.",
    }
    assert [request["id"] for request in sent] == [41, 42, 43], "every round is a new request with the next id"
    assert all(r["method"] == "tools/call" and {k: r["params"][k] for k in original} == original for r in sent), (
        "a retry repeats the original method and params"
    )
    assert [sorted(r["params"].get("inputResponses", {})) for r in sent] == [[], ["pick_files"], ["summary"]], (
        "a retry carries only this round's answers"
    )
    assert [r["params"].get("requestState") for r in sent] == [None] + [
        a["result"]["requestState"] for a in answered[:2]
    ], "a retry echoes the requestState of the round it answers"
    assert params == original, "the caller's params are left as they were"
    assert shown == [("pick_files", "sampling/createMessage"), ("summary", "sampling/createMessage")]
    assert seen == [answered[0]["result"]["inputRequests"]["pick_files"]["params"],
                    answered[1]["result"]["inputRequests"]["summary"]["params"]], (
        "the model gets each request's params as the server sent them"
    )

    calls = []

    def counting(params):
        calls.append(params)
        return reply("ok")

    odd = '{"phase":"pick","files":["a.md"]}'
    bare = asking("draft", state=odd + " ")
    del bare["inputRequests"]["draft"]["params"]["includeContext"]  # the lesson's own example leaves it out
    script = Scripted([asking("outline", "title", state=odd), bare, complete(messages=[])])
    out = drive(script, "prompts/get", {"name": "brief", "_meta": request_meta()},
                approve=lambda key, request: True, model=counting, ids=itertools.count(1), max_rounds=2)
    assert out["resultType"] == "complete", "prompts/get may ask for input too, and no includeContext means none"
    assert [r["params"].get("requestState") for r in script.requests] == [None, odd, odd + " "], (
        "requestState goes back byte for byte, whatever it looks like"
    )
    assert sorted(script.requests[1]["params"]["inputResponses"]) == ["outline", "title"]
    assert calls[0]["modelPreferences"] == HINTS, "modelPreferences are independent hints and pass through as sent"

    calls.clear()
    shown.clear()
    endless = Scripted([asking("more", state=f"s{i}") for i in range(10)])
    with pytest.raises(HostError) as stopped:
        drive(endless, "tools/call", call(), approve=approve, model=counting, ids=itertools.count(1), max_rounds=3)
    assert stopped.value.reason == "rounds"
    assert len(calls) == len(shown) == 3 and len(endless.requests) == 4, (
        "the host fulfils at most max_rounds rounds, and never asks the user about one past the cap"
    )

    calls.clear()

    refusals = [
        ("tools/list", {"_meta": request_meta()}, asking("tools"), "method"),
        ("tools/call", {**call(), "_meta": request_meta(sampling=False)}, asking("pick_files"), "capability"),
        ("tools/call", call(), input_required({**asking("pick_files")["inputRequests"], "branch": ELICIT}, "s"),
         "capability"),
        ("tools/call", call(), input_required({**asking("outline")["inputRequests"],
                                               **asking("title", includeContext="allServers")["inputRequests"]}, "s"),
         "context"),
    ]
    for method, params, canned, reason in refusals:
        script, shown = Scripted([canned]), []
        with pytest.raises(HostError) as refused:
            drive(script, method, params, approve=approve, model=counting, ids=itertools.count(1))
        assert refused.value.reason == reason, f"refused for the right reason: {reason}"
        assert shown == [] and calls == [] and len(script.requests) == 1, (
            "a refused round reaches neither the user nor the model"
        )

    script = Scripted([asking("outline", "title")])
    with pytest.raises(HostError) as denied:
        drive(script, "tools/call", call(), approve=lambda key, request: key != "title", model=counting,
              ids=itertools.count(1))
    assert denied.value.reason == "denied"
    assert calls == [] and len(script.requests) == 1, "the model runs only once the whole round is approved"

    def failing(request):
        return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32602, "message": "requestState expired"}}

    with pytest.raises(McpError) as failed:
        drive(failing, "tools/call", call(), approve=approve, model=counting, ids=itertools.count(1))
    assert failed.value.code == -32602


@pytest.mark.skip("Part 4")
def test_concurrent_approvals(tmp_path) -> None:
    """Interactions run side by side, approvals come in any order, a budget per principal, a CSV row per decision."""
    server = SummarizeServer(make_repo(tmp_path, {"docs/guide.md": "Guide. " * 450}), SECRET, clock=Clock())
    log, prompts = [], []

    async def send(request, principal):
        await asyncio.sleep(0)
        response = server.handle(request, principal=principal)
        log.append((request["id"], request["params"]["arguments"]["audience"], response))
        return response

    def model(params):
        text = params["messages"][-1]["content"]["text"]
        prompts.append(text)
        if "Choose" not in text:
            return reply("Summary.")
        audience = text.splitlines()[0].removeprefix("Audience: ")
        return reply(json.dumps({"docs": ["docs/guide.md"], "ops": ["LICENSE"]}.get(audience, ["README.md"])))

    c = 'C, "the docs"'
    interactions = [
        Interaction("A", "user-42", "tools/call", call("dev-a")),
        Interaction("B", "user-42", "tools/call", call("dev-b")),
        Interaction(c, "user-7", "tools/call", call("docs")),
        Interaction("D", "user-7", "tools/call", call("ops")),
    ]
    budgets = {"user-42": Budget(tokens=800, bytes=100_000), "user-7": Budget(tokens=100_000, bytes=3_300)}
    script = [  # each approval, and how many rows are out before the user gives it
        (Approval("B", 2, False), 0),  # before B has even been asked round 2
        (Approval("B", 1, True), 0),
        (Approval(c, 1, True), 2),
        (Approval(c, 2, True), 3),
        (Approval("A", 1, True), 4),
        (Approval("D", 1, True), 5),
        (Approval("D", 2, True), 6),
        (Approval("A", 2, True), 7),
    ]
    chunks: list[str] = []

    async def run(interactions, user, budgets, ids, **options):
        progress = asyncio.Condition()

        async def approvals():
            async for approval, after in user():
                async with progress:
                    await progress.wait_for(lambda: max(len(chunks) - 1, 0) >= after)
                if approval is not None:
                    yield approval

        async def consume():
            async for chunk in run_interactions(interactions, send=send, approvals=approvals(), model=model,
                                                budgets=budgets, ids=ids, **options):
                async with progress:
                    chunks.append(chunk)
                    progress.notify_all()

        try:
            await asyncio.wait_for(consume(), 3)
            stalled = False
        except (asyncio.TimeoutError, TimeoutError):
            stalled = True
        if stalled:
            pytest.fail(f"the run stalled: rows stream out as rounds are decided, no interaction waits on another, "
                        f"and the run ends with its last interaction; got {chunks}")

    async def user():
        for step in script:
            yield step
        await asyncio.Event().wait()  # then the user goes quiet

    asyncio.run(run(interactions, user, budgets, itertools.count(1)))
    rows = list(csv.reader(io.StringIO("".join(chunks))))
    assert rows[0] == ["interaction", "round", "request_id", "method", "input_key", "decision", "tokens"], (
        "the header names the columns, in order"
    )
    assert all(len(list(csv.reader(io.StringIO(chunk)))) == 1 for chunk in chunks), "each chunk is one CSV record"
    assert [(r[0], r[1], r[4], r[5], r[6]) for r in rows[1:]] == [
        ("B", "1", "pick_files", "approved", "400"),
        ("B", "2", "summary", "denied", "0"),
        (c, "1", "pick_files", "approved", "400"),
        (c, "2", "summary", "over_budget", "0"),
        ("A", "1", "pick_files", "approved", "400"),
        ("D", "1", "pick_files", "approved", "400"),
        ("D", "2", "summary", "approved", "400"),
        ("A", "2", "summary", "over_budget", "0"),
    ], "one row per decision, in the order the decisions are made"
    ids = [request_id for request_id, _, _ in log]
    assert len(ids) == len(set(ids)), "request ids are unique across interactions"
    audience = {"A": "dev-a", "B": "dev-b", c: "docs", "D": "ops", "E": "e", "F": "f"}

    def check_ids(rows):
        asked = {}
        for request_id, who, response in log:
            if response["result"]["resultType"] == "input_required":
                asked[(who, sum(1 for key in asked if key[0] == who) + 1)] = request_id
        for row in rows:
            assert (row[3], int(row[2])) == ("tools/call", asked[(audience[row[0]], int(row[1]))]), (
                "request_id is the request whose result asked for the round"
            )

    check_ids(rows[1:])
    assert Counter(who for _, who, _ in log) == {"dev-a": 2, "dev-b": 2, "docs": 2, "ops": 3}, (
        "a round that is not approved ends its interaction"
    )
    assert [r for _, who, r in log if who == "ops"][-1]["result"]["resultType"] == "complete"
    assert len(prompts) == 5, "the model runs for approved rounds only"
    assert "Choose" not in "".join(chunks), "the log never carries prompt text"

    chunks.clear()

    async def closing():
        yield Approval("E", 1, True), 0
        yield None, 2  # the approval window closes once two rows are out

    quick = [Interaction("E", "user-7", "tools/call", call("e")), Interaction("F", "user-7", "tools/call", call("f"))]
    asyncio.run(run(quick, closing, {"user-7": Budget(400, 10_000)}, itertools.count(500), max_rounds=1))
    rows = list(csv.reader(io.StringIO("".join(chunks))))[1:]
    assert [(r[0], r[1], r[4], r[5], r[6]) for r in rows] == [
        ("E", "1", "pick_files", "approved", "400"),
        ("E", "2", "summary", "refused", "0"),
        ("F", "1", "pick_files", "denied", "0"),
    ], "a round past max_rounds is refused; when approvals end, waiting rounds are denied, whatever the budget"
    check_ids(rows)


FLOW = {
    "pick": Phase("pick_files", {"few": "summarize", "many": "narrow"}),
    "narrow": Phase("narrow_files", {"few": "summarize"}),
    "summarize": Phase("summary", {"plain": DONE, "review": "critique"}),
    "critique": Phase("critique", {"ok": DONE}),
}
FILES = ["a.md", "b.md", "c.md", "d.md", "e.md"]
DIAMOND = {
    "pick": Phase("pick_files", {"code": "code", "docs": "docs"}),
    "code": Phase("code_notes", {"ok": "summarize"}),
    "docs": Phase("doc_notes", {"ok": "summarize"}),
    "summarize": Phase("summary", {"ok": DONE}),
}


def review(phase: str, text: str, data: dict):
    """summarize_repo's checks for each phase of FLOW."""
    if phase in ("pick", "narrow"):
        files = json.loads(text)
        pool = data["pick"] if phase == "narrow" else FILES
        if not isinstance(files, list) or not files or not set(files) <= set(pool):
            raise McpError(-32602, f"{phase} must choose from {pool}")
        files = sorted(set(files))
        if phase == "narrow" and len(files) > 3:
            raise McpError(-32602, "narrow to three files at most")
        return files, "few" if len(files) <= 3 else "many"
    if phase == "summarize":
        return text.strip(), "review" if "TODO" in text else "plain"
    return text.strip(), "ok"


def answer(key: str, text: str) -> dict:
    return {key: reply(text)}


def carry(state: dict) -> dict:
    """What comes back after the state travelled as a requestState."""
    return json.loads(canonical(state))


@pytest.mark.skip("Part 5")
def test_phase_graph() -> None:
    """Multi-round flows as a phase graph: checked once at start, then walked one verified round at a time."""
    assert plan("pick", FLOW, max_rounds=4) == 4, "the longest run takes four rounds"
    with pytest.raises(ValueError):
        plan("pick", FLOW, max_rounds=3)
    assert plan("narrow", {k: v for k, v in FLOW.items() if k != "pick"}, max_rounds=3) == 3
    assert plan("pick", DIAMOND, max_rounds=5) == 3, (
        "two routes into one phase are not a cycle, and a run counts only the phases it visits"
    )
    broken = [
        ("start", FLOW),
        ("pick", {**FLOW, "narrow": Phase("narrow_files", {"few": "sumarize"})}),
        ("pick", {**FLOW, "critique": Phase("critique", {"ok": DONE, "again": "summarize"})}),
        ("pick", {**FLOW, "legacy": Phase("outline", {"ok": DONE})}),
        ("pick", {**FLOW, "legacy": Phase("outline", {"ok": "summarize", "retry": "legacy"})}),
        ("pick", {**FLOW, "critique": Phase("critique", {})}),
    ]
    for start, phases in broken:
        with pytest.raises(ValueError):
            plan(start, phases, max_rounds=10)

    s1 = first_round("pick")
    s2 = carry(advance(FLOW, s1, answer("pick_files", '["e.md", "a.md", "c.md", "b.md", "a.md"]'), review))
    assert s2 == {"phase": "narrow", "round": 2, "data": {"pick": ["a.md", "b.md", "c.md", "e.md"]}}, (
        "the validated value moves on, and the outcome picks the next phase"
    )
    with pytest.raises(McpError) as err:
        advance(FLOW, s2, answer("narrow_files", '["d.md"]'), review)
    assert err.value.code == -32602, "a later round checks its answer against the values validated earlier"
    s3 = carry(advance(FLOW, s2, answer("narrow_files", '["c.md", "a.md"]'), review))
    assert s2 == {"phase": "narrow", "round": 2, "data": {"pick": ["a.md", "b.md", "c.md", "e.md"]}}, (
        "advance leaves the verified state as it was"
    )
    assert s3 == {"phase": "summarize", "round": 3, "data": {"pick": ["a.md", "b.md", "c.md", "e.md"],
                                                            "narrow": ["a.md", "c.md"]}}, (
        "every validated value travels on to later rounds"
    )
    assert advance(FLOW, s2, answer("narrow_files", '["c.md", "a.md"]'), review) == s3, (
        "a retried round gives the same next state"
    )

    stale = [
        (s1, answer("summary", "Two files.")),
        (s2, answer("summary", "Two files.")),
        (s3, {**answer("summary", "Two files."), **answer("narrow_files", '["a.md"]')}),
        (s3, {}),
        ({"phase": "polish", "round": 3, "data": {}}, answer("polish", "Done.")),
    ]
    for state, responses in stale:
        with pytest.raises(McpError) as err:
            advance(FLOW, state, responses, review)
        assert err.value.code == -32602, "a round answers exactly what its own phase asked"

    s4 = carry(advance(FLOW, s3, answer("summary", "Two files. TODO: tests"), review))
    assert (s4["phase"], s4["round"]) == ("critique", 4)
    end = advance(FLOW, s4, answer("critique", "Fine."), review)
    assert end == {"phase": DONE, "round": 4, "data": {**s4["data"], "critique": "Fine."}}, (
        "DONE ends the flow without starting another round"
    )
    with pytest.raises(McpError) as err:
        advance(FLOW, carry(end), answer("critique", "Again."), review)
    assert err.value.code == -32602, "a finished flow takes no more rounds"
    with pytest.raises(ValueError):  # an outcome the phase does not list: the flow itself is wrong
        advance(FLOW, s3, answer("summary", "Two files."), lambda phase, text, data: (text, "translate"))
