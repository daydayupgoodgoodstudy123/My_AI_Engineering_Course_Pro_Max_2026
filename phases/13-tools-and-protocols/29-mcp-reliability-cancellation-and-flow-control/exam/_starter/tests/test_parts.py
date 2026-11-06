import gc
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
import reliablerpc
from reliablerpc.buffer import BoundedSseBuffer
from reliablerpc.coordinator import RequestCoordinator
from reliablerpc.ledger import IdempotencyConflict, IdempotencyLedger
from reliablerpc.policy import (
    Call,
    CloseStream,
    NewRequest,
    Notify,
    RetryDecision,
    ToolContract,
    cancel_signal,
    classify_retry,
    server_cancel_signal,
)
from reliablerpc.race import EVENTS, Client, Counterexample, RaceModel, explore
from reliablerpc.stream import Budget, CallStream, Done, Progress, SimClock
from reliablerpc.tools import charge_account
from reliablerpc.wire import (
    CANCELLED,
    COMPLETED,
    STDIO,
    STREAMABLE_HTTP,
    ReliabilityError,
    notification,
    progress_notification,
    response,
)

RESULT = {"content": [{"type": "text", "text": "3 notes found"}]}
PACKAGE_ROOT = str(Path(reliablerpc.__file__).resolve().parents[1])


def cancelled(request_id, reason=None) -> dict:
    params = {"requestId": request_id}
    if reason is not None:
        params["reason"] = reason
    return notification("notifications/cancelled", params)


@pytest.mark.skip("Part 1")
def test_cancellation_races() -> None:
    """The first terminal state wins, progress strictly increases, and a slow consumer loses no response."""
    channel = BoundedSseBuffer(16)
    server = RequestCoordinator(channel)

    # Streamable HTTP, cancellation first: the client closes the request's response stream.
    http = server.start(7, "tools/call", transport=STREAMABLE_HTTP, progress_token="p-7")
    assert server.progress(7, 1) == progress_notification("p-7", 1), "a running request reports progress"
    assert http.stream.drain() == [progress_notification("p-7", 1)], "HTTP progress goes to the request's own stream"
    server.close_http_stream(7)
    assert server.complete(7, RESULT) is None, "a cancelled request gets no response"
    assert http.state == CANCELLED, "cancellation won"

    # stdio, completion first: the cancellation arrives after the response went out.
    server.start(8, "tools/call", transport=STDIO, progress_token="p-8")
    server.progress(8, 1, total=2)
    sent = server.complete(8, RESULT)
    assert sent == response(8, RESULT), "a running request completes with its response"
    server.receive_stdio_cancellation(cancelled(8, "user closed the dialog"))
    assert server.requests[8].state == COMPLETED, "a late cancellation changes nothing"
    assert server.complete(8, {"content": [], "retried": True}) == sent, (
        "completing again returns the response already sent"
    )
    late = server.start(10, "tools/call", transport=STREAMABLE_HTTP)
    answer = server.complete(10, RESULT)
    server.close_http_stream(10)
    assert late.state == COMPLETED and server.complete(10, RESULT) == answer, (
        "a late cancellation changes nothing, on Streamable HTTP too"
    )
    assert server.progress(8, 2) is None, "notifications stop once a request completes or is cancelled"
    assert server.progress(7, 2) is None, "notifications stop once a request completes or is cancelled"
    assert channel.drain() == [progress_notification("p-8", 1, total=2), sent], (
        "the channel carries each message once, in order"
    )

    # stdio, cancellation first.
    server.start(9, "tools/call", transport=STDIO, progress_token="p-9")
    server.receive_stdio_cancellation(cancelled(9))
    assert server.progress(9, 1) is None and server.complete(9, RESULT) is None, "a cancelled request sends nothing"
    assert server.requests[9].state == CANCELLED and channel.drain() == [], "a cancelled request sends nothing"

    # A live request's first value may be zero; rejected reports change nothing.
    progress_channel = BoundedSseBuffer(8)
    reporter = RequestCoordinator(progress_channel)
    tracked = reporter.start(11, "tools/call", transport=STDIO, progress_token=0)
    assert reporter.progress(11, 0) == progress_notification(0, 0), "zero is a valid first progress value"
    assert tracked.last_progress == 0 and progress_channel.drain() == [progress_notification(0, 0)], (
        "the first progress is recorded and sent once, even when its value and token are zero"
    )
    with pytest.raises(ReliabilityError, match="progress must increase"):
        reporter.progress(11, 0)
    assert tracked.last_progress == 0 and progress_channel.drain() == [], (
        "a repeated zero changes neither the last value nor the queue"
    )
    assert reporter.progress(11, 2) == progress_notification(0, 2), "a later greater value is sent"
    assert progress_channel.drain() == [progress_notification(0, 2)], "accepted progress is queued once"
    for value in (2, 1, 0):
        with pytest.raises(ReliabilityError, match="progress must increase"):
            reporter.progress(11, value)
        assert tracked.last_progress == 2, "rejected progress leaves the last accepted value unchanged"
        assert progress_channel.drain() == [], "rejected progress never reaches the queue"
    assert reporter.progress(11, 3.5) == progress_notification(0, 3.5), (
        "strictly greater progress still works after rejected reports"
    )
    assert tracked.last_progress == 3.5 and progress_channel.drain() == [progress_notification(0, 3.5)], (
        "the next accepted value replaces the last value and is sent once"
    )
    finished = reporter.complete(11, RESULT)
    assert progress_channel.drain() == [finished], "the running request still completes normally"
    assert reporter.progress(11, 3.5) is None and reporter.progress(11, 1) is None, (
        "a completed request ignores even repeated or decreasing progress"
    )
    assert tracked.last_progress == 3.5 and progress_channel.drain() == [], (
        "ignored progress changes neither the completed record nor the queue"
    )
    abandoned = reporter.start(12, "tools/call", transport=STDIO, progress_token="p-12")
    reporter.progress(12, 0)
    progress_channel.drain()
    reporter.receive_stdio_cancellation(cancelled(12))
    assert reporter.progress(12, 0) is None and reporter.progress(12, -1) is None, (
        "a cancelled request ignores even repeated or decreasing progress"
    )
    assert abandoned.last_progress == 0 and progress_channel.drain() == [], (
        "ignored progress changes neither the cancelled record nor the queue"
    )

    # A stalled consumer: 5000 responses wait ahead of two busy progress tokens.
    backlog = BoundedSseBuffer(5002)
    for n in range(5000):
        backlog.push_final(response(1000 + n, RESULT))
    updates = [progress_notification("a" if n % 2 == 0 else "b", n) for n in range(5000)]
    gc.collect()
    start = time.perf_counter()
    for update in updates:
        backlog.push_progress(update)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05, "a push takes constant time, however many responses wait ahead of it"
    queued = backlog.drain()
    assert queued[:5000] == [response(1000 + n, RESULT) for n in range(5000)], "every response stays queued, in order"
    assert queued[5000:] == updates[-2:], "the oldest progress makes room for the newest"
    assert (backlog.dropped_progress, backlog.needs_refetch) == (4998, True), (
        "every progress lost is counted and asks for a refetch"
    )

    p = progress_notification
    first, second, third = response(1, RESULT), response(2, RESULT), response(3, RESULT)
    merged = BoundedSseBuffer(6)
    for update in (p("a", 1), p("a", 2), p("b", 1), p("a", 3)):
        merged.push_progress(update)
    merged.push_final(first)
    merged.push_progress(p("a", 4))
    assert merged.drain() == [p("a", 2), p("b", 1), p("a", 3), first, p("a", 4)], (
        "progress replaces the newest message only when that is progress for the same token"
    )
    assert (merged.dropped_progress, merged.needs_refetch) == (1, True), "a replaced progress counts as lost"

    oldest = BoundedSseBuffer(3)
    for update in (p("a", 1), p("b", 1), p("c", 1), p("b", 2)):
        oldest.push_progress(update)
    assert oldest.drain() == [p("b", 1), p("c", 1), p("b", 2)], "the oldest progress makes room, whatever its token"
    for update in (p("a", 2), p("b", 3), p("c", 2), p("c", 3)):
        oldest.push_progress(update)
    assert oldest.drain() == [p("a", 2), p("b", 3), p("c", 3)], (
        "progress for the newest message's token replaces it, even in a full queue"
    )
    for update in (p("d", 1), p("e", 1), p("f", 1), p("g", 1)):
        oldest.push_progress(update)
    assert oldest.drain() == [p("e", 1), p("f", 1), p("g", 1)], "a drained buffer starts over empty"

    room = BoundedSseBuffer(3)
    room.push_final(first)
    room.push_progress(p("a", 1))
    room.push_progress(p("b", 1))
    room.push_final(second)
    room.push_progress(p("c", 1))
    assert room.drain() == [first, second, p("c", 1)], "a response is never dropped: the oldest progress makes room"

    full = BoundedSseBuffer(2)
    full.push_final(first)
    full.push_final(second)
    full.push_progress(p("a", 1))
    assert (full.dropped_progress, full.needs_refetch) == (1, True), "progress that finds only responses is lost"
    with pytest.raises(ReliabilityError):
        full.push_final(third)
    assert full.drain() == [first, second], "a buffer full of responses refuses another rather than drop one"


REPLICA = """
import json, sys
sys.path.insert(0, sys.argv[1])
from reliablerpc.ledger import IdempotencyLedger
ledger = IdempotencyLedger(sys.argv[2])
print("ready", flush=True)
request = json.loads(sys.stdin.readline())
try:
    print(json.dumps(ledger.call(request["name"], request["arguments"], rpc_id=request["rpc_id"])), flush=True)
except Exception as exc:
    print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), flush=True)
"""


def canonical(result) -> str:
    """Results compared as JSON: 1, 1.0 and True all differ."""
    return json.dumps(result, sort_keys=True)


@pytest.mark.skip("Part 2")
def test_idempotency_ledger(tmp_path) -> None:
    """One idempotency key runs its tool once: across new JSON-RPC ids, crashes, reopens and replicas."""
    path = str(tmp_path / "ledger.sqlite3")
    ledger = IdempotencyLedger(path, timeout_s=1.0)
    plain = {"account": "acct-7", "cents": 1200}
    once = ledger.call("charge_account", plain, rpc_id=1)
    twice = ledger.call("charge_account", plain, rpc_id=2)
    assert once["receipt"] != twice["receipt"] and ledger.executions() == 2, (
        "without an idempotency key, a new JSON-RPC id charges again"
    )

    checkout = {
        "account": "acct-7",
        "cents": 1200,
        "idempotencyKey": "checkout-7",
        "cart": {"items": ["tea", "cake"], "coupon": None},
        "memo": "Café ☕ 支付\u2028",
    }
    first = ledger.call("charge_account", checkout, rpc_id=41)
    stored = canonical(first)
    reordered = {
        "memo": "Café ☕ 支付\u2028",
        "cart": {"coupon": None, "items": ["tea", "cake"]},
        "idempotencyKey": "checkout-7",
        "cents": 1200,
        "account": "acct-7",
    }
    replay = ledger.call("charge_account", reordered, rpc_id=42)
    assert canonical(replay) == stored and replay["rpcId"] == 41, (
        "the same key with the same arguments, in any key order, returns the first call's result"
    )
    assert ledger.executions() == 3, "a replay charges nothing"
    replay["charged"]["cents"] = 1
    first["receipt"] = "forged"
    assert canonical(ledger.call("charge_account", checkout, rpc_id=43)) == stored, (
        "changing a returned result changes nothing that later replays return"
    )

    with pytest.raises(IdempotencyConflict):
        ledger.call("charge_account", {**checkout, "cents": 1300}, rpc_id=44)
    with pytest.raises(IdempotencyConflict):
        ledger.call("refund_account", checkout, rpc_id=45)
    assert ledger.executions() == 3, "a key reused for another call runs nothing"
    ledger.call("charge_account", {"account": "acct-9", "cents": 500, "idempotencyKey": "checkout-9"}, rpc_id=46)
    assert ledger.executions() == 4, "the ledger keeps working after a conflict"

    def charge_then_crash(db, arguments, *, rpc_id):
        charge_account(db, arguments, rpc_id=rpc_id)
        raise RuntimeError("worker crashed after charging")

    crashing = IdempotencyLedger(path, tools={"charge_account": charge_then_crash}, timeout_s=1.0)
    order = {"account": "acct-3", "cents": 700, "idempotencyKey": "order-3"}
    with pytest.raises(RuntimeError):
        crashing.call("charge_account", order, rpc_id=50)
    assert ledger.executions() == 4 and ledger.lookup("order-3") is None, (
        "a call that crashed after charging keeps neither the charge nor a record"
    )
    retried = ledger.call("charge_account", order, rpc_id=51)
    assert ledger.executions() == 5 and canonical(ledger.lookup("order-3")) == canonical(retried), (
        "the retry of a crashed call charges once"
    )
    crashing.close()
    ledger.close()

    reopened = IdempotencyLedger(path, timeout_s=1.0)
    assert canonical(reopened.lookup("checkout-7")) == stored, "a committed record survives a reopen"
    assert canonical(reopened.call("charge_account", checkout, rpc_id=60)) == stored, "and still replays"
    assert reopened.executions() == 5, "a replay after a reopen charges nothing"

    race = {"account": "acct-5", "cents": 900, "idempotencyKey": "race-5"}
    replica = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", REPLICA, PACKAGE_ROOT, path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    finished_early = []

    def charge_while_the_replica_retries(db, arguments, *, rpc_id):
        result = charge_account(db, arguments, rpc_id=rpc_id)
        replica.stdin.write(json.dumps({"name": "charge_account", "arguments": race, "rpc_id": 62}) + "\n")
        replica.stdin.flush()
        try:
            replica.wait(timeout=0.4)
            finished_early.append(True)
        except subprocess.TimeoutExpired:
            pass
        return result

    try:
        assert replica.stdout.readline().strip() == "ready", "the other replica opened the ledger"
        racer = IdempotencyLedger(path, tools={"charge_account": charge_while_the_replica_retries}, timeout_s=1.0)
        mine = racer.call("charge_account", race, rpc_id=61)
        theirs = json.loads(replica.communicate(timeout=30)[0])
    finally:
        if replica.poll() is None:
            replica.kill()
            replica.wait()
    assert not finished_early and canonical(theirs) == canonical(mine), (
        "a replica retrying the key while the first call runs waits for it, then replays its result"
    )
    assert racer.executions() == 6, "two replicas racing on one key charge once"
    racer.close()
    reopened.close()


CONTRACTS = {
    "search_notes": ToolContract(side_effect=False),
    "charge_account": ToolContract(side_effect=True, idempotency_key="idempotencyKey"),
    "deploy_service": ToolContract(side_effect=True, idempotency_key="releaseId"),
    "send_email": ToolContract(side_effect=True),
}
# What the server's tools/list says. Annotations are hints from the server, not guarantees.
SERVER_TOOLS = {
    "search_notes": {"name": "search_notes", "annotations": {"readOnlyHint": True}},
    "charge_account": {"name": "charge_account", "annotations": {"readOnlyHint": False}},
    "deploy_service": {"name": "deploy_service", "annotations": {"destructiveHint": True}},
    "send_email": {"name": "send_email", "annotations": {"readOnlyHint": True, "idempotentHint": True}},
    "rotate_keys": {"name": "rotate_keys", "annotations": {"readOnlyHint": True, "idempotentHint": True}},
}


def tool_call(request_id, name, arguments, transport=STDIO, task_id=None) -> Call:
    return Call(request_id, "tools/call", {"name": name, "arguments": arguments}, transport, task_id)


@pytest.mark.skip("Part 3")
def test_retry_and_cancel_signals() -> None:
    """Retry by the application's contract, and cancel with the signal each transport and lifetime uses."""
    search = tool_call(41, "search_notes", {"query": "cancellation"})
    assert classify_retry(search, CONTRACTS, SERVER_TOOLS) == RetryDecision(
        "safe", NewRequest("tools/call", search.params)
    ), "a call without side effects may simply be sent again"
    charge = tool_call(42, "charge_account", {"account": "acct-7", "cents": 1200, "idempotencyKey": "checkout-7"})
    assert classify_retry(charge, CONTRACTS, SERVER_TOOLS) == RetryDecision(
        "conditional", NewRequest("tools/call", charge.params)
    ), "a mutation the server deduplicates is retried with the same key and identical arguments"
    deploy = tool_call(43, "deploy_service", {"service": "api", "releaseId": "rel-12"})
    assert classify_retry(deploy, CONTRACTS, SERVER_TOOLS).classification == "conditional", (
        "the contract names the argument that carries the key"
    )
    unsafe = [
        (tool_call(44, "charge_account", {"account": "acct-7", "cents": 1200}), "a mutation without its key"),
        (tool_call(45, "charge_account", {"account": "acct-7", "cents": 1200, "idempotencyKey": ""}), "an empty key"),
        (tool_call(50, "charge_account", {"account": "acct-7", "cents": 1200, "idempotencyKey": 7}), "a key that is not a string"),
        (tool_call(46, "deploy_service", {"service": "api", "idempotencyKey": "rel-12"}), "a key in the wrong argument"),
        (tool_call(47, "send_email", {"to": "ops@example.com", "idempotencyKey": "mail-1"}), "a tool that deduplicates nothing"),
        (tool_call(48, "rotate_keys", {"scope": "all"}), "a tool without a contract"),
    ]
    for call, case in unsafe:
        assert classify_retry(call, CONTRACTS, SERVER_TOOLS) == RetryDecision("unsafe", None), (
            f"{case} is unsafe: reconcile, never retry automatically, whatever the annotations say"
        )
        assert classify_retry(call, CONTRACTS) == RetryDecision("unsafe", None), f"{case} is unsafe"

    assert cancel_signal(search, reason="User closed the operation") == Notify(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 41, "reason": "User closed the operation"},
        }
    ), "on stdio the client sends notifications/cancelled, a notification without an id"
    listen = Call("listen-1", "subscriptions/listen", {}, STDIO)
    assert cancel_signal(listen) == Notify(cancelled("listen-1")), (
        "requestId is the call's id as it was sent, and reason is left out when there is none"
    )
    http = tool_call(42, "charge_account", charge.params["arguments"], transport=STREAMABLE_HTTP)
    assert cancel_signal(http, reason="deadline") == CloseStream(42), (
        "on Streamable HTTP the client closes the call's response stream and posts nothing"
    )
    for transport in (STREAMABLE_HTTP, STDIO):
        task = tool_call(49, "deploy_service", deploy.params["arguments"], transport, task_id="tsk_786512e29e0d")
        assert cancel_signal(task, reason="user") == NewRequest("tasks/cancel", {"taskId": "tsk_786512e29e0d"}), (
            "a durable task is cancelled with tasks/cancel, an ordinary request naming the task"
        )

    assert server_cancel_signal(listen, reason="server shutting down") == Notify(
        cancelled("listen-1", "server shutting down")
    ), "a server may end a stdio subscriptions/listen with notifications/cancelled"
    for call in (search, Call("listen-2", "subscriptions/listen", {}, STREAMABLE_HTTP)):
        with pytest.raises(ReliabilityError):
            server_cancel_signal(call)


KEEPALIVE = "keepalive"


class SseReader:
    """An SSE client: a comment line is a keepalive; data lines are joined and decoded at a blank line."""

    def __init__(self) -> None:
        self.pending = ""
        self.data: list[str] = []

    def feed(self, chunk: bytes) -> list:
        assert isinstance(chunk, bytes), "the stream writes bytes"
        self.pending += chunk.decode("utf-8")
        seen = []
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            line = line.removesuffix("\r")
            if line.startswith(":"):
                seen.append(KEEPALIVE)
            elif line == "":
                if self.data:
                    seen.append(json.loads("\n".join(self.data)))
                    self.data = []
            else:
                name, _, value = line.partition(":")
                assert name == "data", f"events carry data lines only, got {line!r}"
                self.data.append(value.removeprefix(" "))
        return seen


def run_worker(script, pulled: list, closed: list):
    """A tool's worker: yields (at_ms, event) when the stream asks for its next event."""
    try:
        for at_ms, event in script:
            pulled.append(at_ms)
            yield at_ms, event
    finally:
        closed.append(True)


def timeline(stream: CallStream, clock: SimClock, limit: int = 40) -> list:
    """(clock time, what the client saw) for every message the stream writes, reading at most limit chunks."""
    reader = SseReader()
    return [(clock.now_ms, item) for chunk in itertools.islice(stream, limit) for item in reader.feed(chunk)]


def progress(token, value, **extra) -> dict:
    return progress_notification(token, value, extra.get("total"), extra.get("message"))


@pytest.mark.skip("Part 4")
def test_two_clock_stream() -> None:
    """Progress resets the idle clock, never the maximum one; keepalives keep proxies quiet, not requests alive."""
    clock = SimClock(0)
    budget = Budget(idle_timeout_ms=500, max_timeout_ms=2000, keepalive_ms=300)
    script = [(400, Progress(1, total=5)), (800, Progress(2, total=5)), (1200, Progress(3, total=5))]
    script += [(1600, Progress(4, total=5)), (1999, Progress(5, total=5)), (2100, Done(RESULT))]
    pulled, closed = [], []
    stream = CallStream(41, run_worker(script, pulled, closed), clock=clock, budget=budget, progress_token="p-41")
    headers = {name.lower(): value for name, value in stream.headers().items()}
    assert {name: headers.get(name) for name in ("content-type", "cache-control", "x-accel-buffering")} == {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        "x-accel-buffering": "no",
    }, "an SSE response that proxies do not buffer"
    assert timeline(stream, clock) == [
        (300, KEEPALIVE),
        (400, progress("p-41", 1, total=5)),
        (700, KEEPALIVE),
        (800, progress("p-41", 2, total=5)),
        (1100, KEEPALIVE),
        (1200, progress("p-41", 3, total=5)),
        (1500, KEEPALIVE),
        (1600, progress("p-41", 4, total=5)),
        (1900, KEEPALIVE),
        (1999, progress("p-41", 5, total=5)),
    ], "progress at 1999 ms does not move the 2000 ms maximum deadline, and nothing follows it"
    assert (stream.outcome, clock.now_ms) == ("maximum timeout", 2000), "the maximum clock ran out at 2000 ms"
    assert closed, "a cancelled call stops its worker"

    clock = SimClock(0)
    quiet = CallStream(42, run_worker([], [], []), clock=clock, progress_token="p-42",
                       budget=Budget(idle_timeout_ms=500, max_timeout_ms=2000, keepalive_ms=200))
    assert timeline(quiet, clock) == [(200, KEEPALIVE), (400, KEEPALIVE)], (
        "a keepalive is not progress: a worker that goes silent still runs out of idle time"
    )
    assert (quiet.outcome, clock.now_ms) == ("idle timeout", 500), "the idle clock ran out at 500 ms"

    clock = SimClock(0)
    stuck = [(100, Progress(1)), (350, Progress(1)), (450, Progress(0.5)), (900, Done(RESULT))]
    repeats = CallStream(43, run_worker(stuck, [], []), clock=clock, budget=budget, progress_token="p-43")
    assert timeline(repeats, clock) == [(100, progress("p-43", 1)), (400, KEEPALIVE)], (
        "progress values must increase: a repeated or smaller value is neither sent nor activity"
    )
    assert (repeats.outcome, clock.now_ms) == ("idle timeout", 600), "a worker stuck at 1 runs out of idle time"

    clock = SimClock(0)
    busy = [(100, Progress(1)), (250, Progress(2)), (400, Progress(3)), (550, Done(RESULT))]
    tokenless = CallStream(44, run_worker(busy, [], []), clock=clock, budget=budget)
    assert timeline(tokenless, clock) == [(300, KEEPALIVE)], (
        "without a progress token nothing is sent as progress, and nothing restarts the idle clock"
    )
    assert (tokenless.outcome, clock.now_ms) == ("idle timeout", 500), "the idle clock runs from the start"

    clock = SimClock(10_000)
    pulled, closed = [], []
    script = [(10_100, Progress(1, message="indexing")), (11_050, Done(RESULT)), (11_060, Progress(2))]
    slow = CallStream(45, run_worker(script, pulled, closed), clock=clock, progress_token="p-45",
                      budget=Budget(idle_timeout_ms=1000, max_timeout_ms=5000, keepalive_ms=300))
    assert timeline(slow, clock) == [
        (10_100, progress("p-45", 1, message="indexing")),
        (10_400, KEEPALIVE),
        (10_700, KEEPALIVE),
        (11_000, KEEPALIVE),
        (11_050, response(45, RESULT)),
    ], "keepalives fill the silence every keepalive_ms; the response ends the stream"
    assert (slow.outcome, pulled, closed) == ("completed", [10_100, 11_050], [True]), (
        "nothing is read from the worker after its result, and the worker is closed"
    )
    clock = SimClock(0)
    brief = CallStream(47, run_worker([(100, Progress(1)), (200, Done(RESULT))], [], []), clock=clock, budget=budget)
    assert timeline(brief, clock) == [(200, response(47, RESULT))], "without a progress token the response still goes out"
    assert brief.outcome == "completed", "without a progress token the response still goes out"

    clock = SimClock(0)
    pulled, closed = [], []
    script = [(100, Progress(1)), (200, Progress(2)), (250, Done(RESULT))]
    lazy_call = CallStream(46, run_worker(script, pulled, closed), clock=clock, budget=budget, progress_token="p-46")
    lazy = iter(lazy_call)
    assert SseReader().feed(next(lazy)) == [progress("p-46", 1)], "the first progress comes first"
    assert pulled == [100], "the stream writes as the worker goes, not after it finishes"
    lazy.close()
    assert closed == [True], "closing the response stream stops the worker"


class LateCancelWins(RequestCoordinator):
    """A terminal-state violation: a late cancellation overrides a completed request."""

    def receive_stdio_cancellation(self, notification):
        request = self.requests.get(notification["params"]["requestId"])
        if request is not None and request.state == COMPLETED:
            request.state = CANCELLED
        return super().receive_stdio_cancellation(notification)


class RespondsAfterCancel(RequestCoordinator):
    """Part 1's first bug again: a cancelled request still sends its response."""

    def complete(self, request_id, result):
        if self.requests[request_id].state == CANCELLED:
            message = response(request_id, result)
            self.channel.push_final(message)
            return message
        return super().complete(request_id, result)


class ProgressAfterCancel(RequestCoordinator):
    """A terminal-state violation: a cancelled request still sends progress."""

    def progress(self, request_id, value, *, total=None, message=None):
        request = self.requests[request_id]
        if request.state == CANCELLED:
            note = progress_notification(request.progress_token, value, total, message)
            self.channel.push_progress(note)
            return note
        return super().progress(request_id, value, total=total, message=message)


class TrustingClient(Client):
    """A client that still uses a response that arrives after it gave up."""

    def receive(self, kind):
        if kind == "response" and self.status == "abandoned":
            return True
        return super().receive(kind)


class CountingModel(RaceModel):
    def __init__(self, budget: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.budget = budget
        self.steps = 0

    def step(self, world, event):
        self.steps += 1
        assert self.steps <= self.budget, "explore keeps expanding worlds it has already explored"
        return super().step(world, event)


@pytest.mark.skip("Part 5")
def test_race_explorer() -> None:
    """Every interleaving of the race keeps the invariants; a broken side is caught with its shortest story."""
    assert explore(RaceModel(), EVENTS, max_depth=12) is None, (
        "with Part 1's coordinator, no interleaving breaks an invariant"
    )
    assert explore(RaceModel(LateCancelWins), EVENTS, max_depth=12) == Counterexample(
        ("start", "cancel", "complete", "server_hears"), "the request went from completed to cancelled"
    ), "the shortest sequence that breaks an invariant, first in the order of events"
    assert explore(RaceModel(RespondsAfterCancel), EVENTS, max_depth=12) == Counterexample(
        ("start", "cancel", "server_hears", "complete"), "the server sent a response after cancelling the request"
    ), "the shortest sequence that breaks an invariant, first in the order of events"
    assert explore(RaceModel(ProgressAfterCancel), EVENTS, max_depth=12) == Counterexample(
        ("start", "cancel", "server_hears", "progress"), "the server sent a progress after cancelling the request"
    ), "the shortest sequence that breaks an invariant, first in the order of events"
    assert explore(RaceModel(client_class=TrustingClient), EVENTS, max_depth=12) == Counterexample(
        ("start", "cancel", "complete", "client_hears"), "the client used a response after abandoning the request"
    ), "the shortest sequence that breaks an invariant, first in the order of events"

    reordered = ("server_hears", "complete", "timeout", "cancel", "start", "progress", "client_hears")
    assert explore(RaceModel(LateCancelWins), reordered, max_depth=12).trace == (
        "timeout", "start", "complete", "server_hears"
    ), "events are tried in the order given"
    assert explore(RaceModel(LateCancelWins), ("start", "timeout", "complete", "server_hears"), max_depth=12) == (
        Counterexample(("start", "timeout", "complete", "server_hears"), "the request went from completed to cancelled")
    ), "only the given events happen"
    assert explore(RaceModel(LateCancelWins), ("start", "cancel", "complete", "client_hears"), max_depth=12) is None, (
        "a cancellation that never reaches the server breaks nothing"
    )
    assert explore(RaceModel(LateCancelWins), EVENTS, max_depth=3) is None, "no sequence is longer than max_depth"
    assert explore(RaceModel(LateCancelWins), EVENTS, max_depth=4) is not None, (
        "a sequence of exactly max_depth events is checked"
    )
    assert explore(CountingModel(2000), EVENTS, max_depth=12) is None, "every world is explored once"
