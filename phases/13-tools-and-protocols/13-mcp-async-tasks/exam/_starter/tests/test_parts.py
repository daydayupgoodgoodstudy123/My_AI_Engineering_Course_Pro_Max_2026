import asyncio
import gc
import itertools
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import pytest
from durabletask.lease import Leases
from durabletask.listen import listen
from durabletask.service import TaskService
from durabletask.store import MemoryStore, TaskStore
from durabletask.task import EXPIRED_ERROR, Task
from durabletask.tools import Done, NeedInput, Tool
from durabletask.wire import SERVER_INFO_META, SUBSCRIPTION_ID_META, McpError, make_request

T0 = datetime(2026, 8, 21, 10, 30, tzinfo=timezone.utc)
SERVER_META = {SERVER_INFO_META: {"name": "durabletask", "version": "1.0.0"}}
REQUEST_IDS = itertools.count(1)


class Clock:
    """A test clock, in whole seconds, that moves only when a test moves it."""

    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


def rpc(service: TaskService, method: str, principal: str = "user-42", **params) -> dict:
    """Send one request and return its result."""
    reply = service.dispatch(make_request(next(REQUEST_IDS), method, params), principal=principal)
    assert "result" in reply, f"{method} failed: {reply.get('error')}"
    return reply["result"]


def rpc_error(service: TaskService, method: str, principal: str = "user-42", **params) -> dict:
    """Send one request that must fail, and return its error object."""
    reply = service.dispatch(make_request(next(REQUEST_IDS), method, params), principal=principal)
    assert "error" in reply, f"{method} should have failed, got {reply.get('result')}"
    return reply["error"]


def move(store, clock: Clock, task_id: str, **fields) -> None:
    """Change a stored task the way its worker would, stamped with the clock's time."""
    task = store.get(task_id)
    for name, value in fields.items():
        setattr(task, name, value)
    task.last_updated_at = clock()
    store.save(task)


def form(message: str, name: str, schema: dict) -> dict:
    """An elicitation/create request for a form with one required field."""
    return {
        "method": "elicitation/create",
        "params": {
            "mode": "form",
            "message": message,
            "requestedSchema": {"type": "object", "properties": {name: schema}, "required": [name]},
        },
    }


def accept(**content) -> dict:
    return {"action": "accept", "content": content}


OUTLINE = form("Approve the generated report outline?", "approved", {"type": "boolean"})
REVISED = form("Approve the revised outline?", "approved", {"type": "boolean"})
FORMAT = form("Which format should the report use?", "format", {"type": "string", "enum": ["pdf", "html"]})
REPORT_RESULT = {
    "resultType": "complete",
    "content": [{"type": "text", "text": "Generated large report with approved outline."}],
    "structuredContent": {"size": "large", "approved": True},
    "isError": False,
    "_meta": SERVER_META,
}
WAITING = {
    "status": "input_required",
    "status_message": "Waiting for outline approval.",
    "input_requests": {"approve_outline": OUTLINE},
    "issued_keys": ["approve_outline"],
}


def played_by_hand(arguments: dict, answers: dict):
    raise AssertionError("this test moves its tasks itself")


TOOLS = {
    "generate_report": Tool(played_by_hand),
    "archive_logs": Tool(played_by_hand, ttl_ms=None),
    "quick_export": Tool(played_by_hand, ttl_ms=60_000),
}


@pytest.mark.skip("Part 1")
def test_poll_and_cancel() -> None:
    """tasks/get and tasks/cancel report tasks the way the Tasks extension defines them."""
    clock = Clock()
    store = MemoryStore()
    service = TaskService(store, tools=TOOLS, clock=clock, rng=random.Random(13))
    handle = rpc(service, "tools/call", name="generate_report", arguments={"size": "large"})
    report = handle["taskId"]
    assert handle == {
        "resultType": "task",
        "taskId": report,
        "status": "working",
        "statusMessage": "Task accepted.",
        "createdAt": "2026-08-21T10:30:00Z",
        "lastUpdatedAt": "2026-08-21T10:30:00Z",
        "ttlMs": 900000,
        "pollIntervalMs": 1000,
        "_meta": SERVER_META,
    }, "tools/call answers with the task's handle, resultType task"
    archive = rpc(service, "tools/call", name="archive_logs", arguments={})["taskId"]
    slow = rpc(service, "tools/call", name="generate_report", arguments={"size": "small"})["taskId"]

    clock.advance(seconds=5)
    polled = rpc(service, "tasks/get", taskId=report)
    assert polled["resultType"] == "complete", "tasks/get itself completed; the task's own state is in status"
    assert polled == {**handle, "resultType": "complete"}, "a poll shows the task the handle described"

    clock.advance(seconds=5)
    move(store, clock, report, **WAITING)
    waiting = rpc(service, "tasks/get", taskId=report)
    assert (waiting["resultType"], waiting["status"], waiting["inputRequests"]) == (
        "complete",
        "input_required",
        {"approve_outline": OUTLINE},
    ), "tasks/get is complete whatever the task's status, input_required included"
    clock.advance(seconds=10)
    move(store, clock, report, status="completed", status_message="Report completed.", input_requests={}, result=REPORT_RESULT)
    done = rpc(service, "tasks/get", taskId=report)
    assert done["result"] == REPORT_RESULT and "inputRequests" not in done
    clock.advance(seconds=10)
    assert rpc(service, "tasks/cancel", taskId=report) == {"resultType": "complete", "_meta": SERVER_META}, (
        "tasks/cancel answers with an empty acknowledgement"
    )
    assert rpc(service, "tasks/get", taskId=report) == done, "a finished task never changes, not even its lastUpdatedAt"

    job = rpc(service, "tools/call", name="generate_report", arguments={})["taskId"]
    rpc(service, "tasks/cancel", taskId=job)
    running = rpc(service, "tasks/get", taskId=job)
    assert (running["status"], running["statusMessage"]) == ("working", "Cancellation requested."), (
        "cancellation is cooperative: a working task stops at its worker's next step"
    )
    clock.advance(seconds=5)
    rpc(service, "tasks/cancel", taskId=job)
    assert rpc(service, "tasks/get", taskId=job) == running, "a repeated cancel changes nothing"
    asked = rpc(service, "tools/call", name="generate_report", arguments={})["taskId"]
    move(store, clock, asked, **WAITING)
    rpc(service, "tasks/cancel", taskId=asked)
    stopped = rpc(service, "tasks/get", taskId=asked)
    assert (stopped["status"], stopped["statusMessage"]) == ("cancelled", "Task cancelled.") and (
        "inputRequests" not in stopped
    ), "a task waiting for input has no worker to wait for, so it is cancelled at once"

    clock.now = T0 + timedelta(minutes=10)
    move(store, clock, slow, **WAITING)
    clock.now = T0 + timedelta(minutes=15) - timedelta(seconds=1)
    assert rpc(service, "tasks/get", taskId=slow)["status"] == "input_required"
    clock.advance(seconds=1)
    expired = rpc(service, "tasks/get", taskId=slow)
    assert (expired["status"], expired.get("error")) == ("failed", EXPIRED_ERROR), (
        "a task expires ttlMs after it was created"
    )
    assert (expired["statusMessage"], expired["lastUpdatedAt"]) == ("Task expired.", "2026-08-21T10:45:00Z"), (
        "expiring a task is a change, stored when it happens"
    )
    clock.advance(days=2)
    assert rpc(service, "tasks/get", taskId=archive)["status"] == "working", "a task with ttlMs null never expires"
    late = rpc(service, "tools/call", name="generate_report", arguments={})["taskId"]
    move(store, clock, late, **WAITING)
    clock.advance(minutes=15)
    rpc(service, "tasks/cancel", taskId=late)
    assert rpc(service, "tasks/get", taskId=late)["status"] == "failed", "tasks/cancel fails an overdue task first, as tasks/get does"

    busy = TaskService(MemoryStore(), tools=TOOLS, clock=clock, rng=random.Random(14))
    many = [rpc(busy, "tools/call", name="generate_report", arguments={})["taskId"] for _ in range(3000)]
    gc.collect()
    start = time.perf_counter()
    for task_id in many[:20]:
        clock.advance(seconds=1)  # clients poll once per pollIntervalMs
        rpc(busy, "tasks/get", taskId=task_id)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.04, "tasks/get should not slow down as tasks pile up"


def record(task_id: str, **fields) -> Task:
    """A task record: the fields a test cares about, plain values for the rest."""
    values = {
        "task_id": task_id,
        "owner": "user-42",
        "tool": "generate_report",
        "arguments": {"size": "large"},
        "status": "working",
        "status_message": "Task accepted.",
        "created_at": T0,
        "last_updated_at": T0,
        "ttl_ms": 900_000,
    }
    values.update(fields)
    return Task(**values)


GOLDEN = {
    "task_id": "tsk_0123456789ab",
    "owner": "user-42",
    "tool": "generate_report",
    "arguments": {"size": "large", "sections": ["summary", "appendix"]},
    "status": "input_required",
    "status_message": "Waiting for outline approval.",
    "created_at": "2026-08-21T10:30:00Z",
    "last_updated_at": "2026-08-21T10:31:00Z",
    "ttl_ms": None,
    "poll_interval_ms": 1000,
    "input_requests": {"approve_outline": OUTLINE},
    "answers": {"format": accept(format="pdf")},
    "issued_keys": ["format", "approve_outline"],
    "result": None,
    "error": None,
    "cancel_requested": False,
}
GOLDEN_TASK = record(
    "tsk_0123456789ab",
    arguments={"size": "large", "sections": ["summary", "appendix"]},
    status="input_required",
    status_message="Waiting for outline approval.",
    last_updated_at=T0 + timedelta(minutes=1),
    ttl_ms=None,
    input_requests={"approve_outline": OUTLINE},
    answers={"format": accept(format="pdf")},
    issued_keys=["format", "approve_outline"],
)


def raises(error: type, call, *args) -> bool:
    try:
        call(*args)
    except error:
        return True
    return False


@pytest.mark.skip("Part 2")
def test_task_files(tmp_path) -> None:
    """Tasks live in a directory every instance shares, one JSON file each, and read back exactly."""
    directory = tmp_path / "tasks"
    replica = TaskStore(directory)
    service = TaskService(TaskStore(directory), tools=TOOLS, clock=Clock(), rng=random.Random(2))
    first = rpc(service, "tools/call", name="generate_report", arguments={"size": "large"})["taskId"]
    fetched = replica.get(first)
    assert fetched is not None and (fetched.status, fetched.created_at) == ("working", T0), (
        "a handle resolves on every instance as soon as tools/call returns it"
    )
    fetched.status_message = "Collecting sources."
    fetched.last_updated_at = T0 + timedelta(seconds=2)
    replica.save(fetched)
    assert service.store.get(first) == fetched, "an instance sees another instance's writes"
    again = service.store.get(first)
    again.status_message = "Writing the report."
    again.last_updated_at = T0 + timedelta(seconds=4)
    service.store.save(again)
    assert replica.get(first) == again, "an instance sees another instance's writes, even of a task it has read"
    if os.name == "posix":  # Windows will not rename a file over one that is open
        with open(directory / f"{first}.json", encoding="utf-8") as reading:  # another instance is reading it
            newer = replica.get(first)
            newer.status_message = "Report written."
            newer.last_updated_at = T0 + timedelta(seconds=6)
            replica.save(newer)
            assert json.loads(reading.read())["status_message"] == "Writing the report.", (
                "a save puts a whole new file in place: a reader that already opened the old one reads the old record"
            )
        assert service.store.get(first) == newer

    tricky = [
        record(
            "tsk_00000000000a",
            status="input_required",
            status_message="Choose a format and approve the outline.",
            input_requests={"format": FORMAT, "approve_outline": OUTLINE},
            issued_keys=["format", "approve_outline"],
        ),
        record(
            "tsk_00000000000b",
            status="completed",
            status_message="Report completed.",
            last_updated_at=T0 + timedelta(minutes=4, seconds=12),
            result={
                "resultType": "complete",
                "content": [{"type": "text", "text": "Rapport généré ☕"}],
                "structuredContent": {"size": "large", "score": 0.1 + 0.2, "pages": [[1, 2.5], []]},
                "isError": False,
                "_meta": SERVER_META,
            },
            answers={"outline": accept(approved=True), "format": accept(format="pdf"), "budget": {"action": "decline"}},
            issued_keys=["outline", "format", "budget"],
        ),
        record(
            "tsk_00000000000c",
            status="failed",
            status_message="Warehouse unavailable",
            error={"code": -32000, "message": "Warehouse unavailable", "data": {"retryAfterMs": 30000}},
        ),
        record("tsk_00000000000d", ttl_ms=None, poll_interval_ms=5000, cancel_requested=True, last_updated_at=T0 + timedelta(days=3)),
    ]
    store = TaskStore(directory)
    for task in tricky:
        store.create(task)
    assert raises(ValueError, store.create, tricky[0]), "create never replaces an existing task"
    reopened = TaskStore(directory)
    assert [reopened.get(task.task_id) for task in tricky] == tricky, "every task reads back exactly"

    (directory / "tsk_0123456789ab.json").write_text(json.dumps(GOLDEN, indent=2), encoding="utf-8")
    golden = reopened.get("tsk_0123456789ab")
    assert golden == GOLDEN_TASK, "a record another instance wrote reads back"
    golden.last_updated_at = T0 + timedelta(minutes=2)
    store.save(golden)
    assert json.loads((directory / "tsk_0123456789ab.json").read_text(encoding="utf-8")) == {
        **GOLDEN,
        "last_updated_at": "2026-08-21T10:32:00Z",
    }, "every instance writes the shared record format: asdict fields, wire timestamps"
    ids = sorted([first, "tsk_0123456789ab", *(task.task_id for task in tricky)])
    assert sorted(os.listdir(directory)) == [f"{task_id}.json" for task_id in ids], (
        "one file per task, and nothing left behind"
    )

    (directory / "tsk_00000000beef.tmp").write_text('{"task_id": "tsk_00000000beef", "own', encoding="utf-8")
    (directory / ".tsk_00000000000a.json.swp").write_text("{", encoding="utf-8")
    assert TaskStore(directory).task_ids() == ids, "only <taskId>.json files are tasks"
    assert store.get("tsk_00000000beef") is None

    broken = store.get("tsk_00000000000b")
    broken.result["structuredContent"]["generatedAt"] = T0  # a datetime: JSON cannot hold it
    broken.last_updated_at = T0 + timedelta(hours=1)
    assert raises(TypeError, store.save, broken), "a task that cannot be written is an error"
    assert TaskStore(directory).get("tsk_00000000000b") == tricky[1], "a write that fails leaves the previous record"
    assert TaskStore(directory).task_ids() == ids

    TaskStore(tmp_path / "elsewhere").create(record("tsk_aaaaaaaaaaaa", owner="alice"))
    assert all(
        raises(ValueError, store.get, bad)
        for bad in ("../elsewhere/tsk_aaaaaaaaaaaa", "tsk_AAAAAAAAAAAA", "tsk_aaaaaaaaaaaa.json", "", 7)
    ), "a task id from a client never becomes a path of its choosing"

    replica.delete(first)
    replica.delete(first)
    assert store.get(first) is None and first not in store.task_ids(), "a deleted task is gone for every instance"

    bulk = TaskStore(tmp_path / "bulk")
    names = [f"tsk_{n:012x}" for n in range(2000)]
    for task_id in names:
        bulk.create(record(task_id))
    reader = TaskStore(tmp_path / "bulk")
    picks = random.Random(5).sample(names, 20)
    gc.collect()
    start = time.perf_counter()
    found = [reader.get(task_id) for task_id in picks]
    elapsed = time.perf_counter() - start
    assert [task.task_id for task in found] == picks
    assert elapsed < 0.04, "get reads one task's file, however many tasks there are"


@pytest.mark.skip("Part 3")
def test_worker_and_input() -> None:
    """The worker moves tasks through their states, and tasks/update answers input by key."""
    clock = Clock()
    runs: list[dict] = []

    def report(arguments: dict, answers: dict):
        runs.append(answers)
        if not answers:
            return NeedInput({"format": FORMAT, "approve_outline": OUTLINE}, "Choose a format and approve the outline.")
        if answers["approve_outline"]["action"] != "accept" and "approve_outline_2" not in answers:
            return NeedInput({"approve_outline_2": REVISED}, "Approve the revised outline.")
        chosen = answers["format"]["content"]["format"]
        outlines = 2 if "approve_outline_2" in answers else 1
        return Done(
            {
                "content": [{"type": "text", "text": f"Generated {arguments['size']} {chosen} report."}],
                "structuredContent": {"size": arguments["size"], "format": chosen, "outlines": outlines},
                "isError": False,
            },
            "Report completed.",
        )

    def export(arguments: dict, answers: dict):
        return Done({"content": [{"type": "text", "text": "No rows in range."}], "isError": True}, "Export finished.")

    def sync(arguments: dict, answers: dict):
        raise McpError(-32000, "Warehouse unavailable", {"retryAfterMs": 30000} if arguments["region"] == "eu" else None)

    def purge(arguments: dict, answers: dict):
        confirm = form("Delete the archive?", "confirm", {"type": "boolean"})
        if "confirm" not in answers:
            return NeedInput({"confirm": confirm}, "Confirm the purge.")
        if "reason" not in answers:
            return NeedInput({"reason": form("Why purge it?", "reason", {"type": "string"})}, "Give a reason.")
        return NeedInput({"confirm": confirm}, "Confirm the purge again.")

    tools = {
        "generate_report": Tool(report),
        "export_rows": Tool(export),
        "sync_warehouse": Tool(sync),
        "purge_archive": Tool(purge),
    }
    service = TaskService(MemoryStore(), tools=tools, clock=clock, rng=random.Random(3))

    def poll(task_id: str) -> dict:
        return rpc(service, "tasks/get", taskId=task_id)

    def answer(task_id: str, **responses) -> dict:
        return rpc(service, "tasks/update", taskId=task_id, inputResponses=responses)

    task = rpc(service, "tools/call", name="generate_report", arguments={"size": "large"})["taskId"]
    clock.advance(seconds=2)
    assert service.step(task) is True
    first = poll(task)
    assert (first["status"], first["statusMessage"], first.get("inputRequests")) == (
        "input_required",
        "Choose a format and approve the outline.",
        {"format": FORMAT, "approve_outline": OUTLINE},
    ), "the tool's input requests become the task's inputRequests"
    assert first["lastUpdatedAt"] == "2026-08-21T10:30:02Z", "every change to a task stamps lastUpdatedAt"
    assert service.step(task) is False and len(runs) == 1, "a task waiting for input has no work for its worker"

    clock.advance(seconds=5)
    ack = answer(task, format=accept(format="html"), theme=accept(theme="dark"), approve_outline={"action": "accept", "approved": True})
    assert ack == {"resultType": "complete", "_meta": SERVER_META}, "tasks/update answers with an empty acknowledgement"
    partial = poll(task)
    assert (partial["status"], partial.get("inputRequests")) == ("input_required", {"approve_outline": OUTLINE}), (
        "a partial answer leaves the other keys outstanding"
    )
    assert partial["lastUpdatedAt"] == "2026-08-21T10:30:07Z", "every change to a task stamps lastUpdatedAt"
    answer(task, format=accept(format="pdf"), approve_outline={"action": "decline"})
    resumed = poll(task)
    assert (resumed["status"], resumed["statusMessage"]) == ("working", "Input received.") and (
        "inputRequests" not in resumed
    ), "once every key is answered the task is working again"

    assert service.step(task) is True
    revised = poll(task)
    assert revised.get("inputRequests") == {"approve_outline_2": REVISED}
    clock.advance(seconds=5)
    answer(task, approve_outline=accept(approved=True))
    assert poll(task) == revised, "a key that is no longer outstanding is ignored, and changes nothing"
    answer(task, approve_outline_2=accept(approved=True))
    assert service.step(task) is True
    assert runs == [
        {},
        {"format": accept(format="html"), "approve_outline": {"action": "decline"}},
        {"format": accept(format="html"), "approve_outline": {"action": "decline"}, "approve_outline_2": accept(approved=True)},
    ], "the tool sees the first answer to each key"
    done = poll(task)
    assert (done["status"], done.get("result")) == (
        "completed",
        {
            "resultType": "complete",
            "content": [{"type": "text", "text": "Generated large html report."}],
            "structuredContent": {"size": "large", "format": "html", "outlines": 2},
            "isError": False,
            "_meta": SERVER_META,
        },
    ), "a completed task carries the tool call's own result, with its resultType and serverInfo"
    assert done["statusMessage"] == "Report completed.", "a finished task's statusMessage is the message its tool gave"
    clock.advance(seconds=5)
    answer(task, approve_outline_2=accept(approved=False))
    assert service.step(task) is False and poll(task) == done, "a finished task never changes"

    exported = rpc(service, "tools/call", name="export_rows", arguments={})["taskId"]
    service.step(exported)
    rows = poll(exported)
    assert (rows["status"], rows.get("result", {}).get("isError")) == ("completed", True) and "error" not in rows, (
        "a tool result with isError: true still completes the task"
    )

    eu = rpc(service, "tools/call", name="sync_warehouse", arguments={"region": "eu"})["taskId"]
    us = rpc(service, "tools/call", name="sync_warehouse", arguments={"region": "us"})["taskId"]
    service.step(eu)
    service.step(us)
    failed = poll(eu)
    assert (failed["status"], failed["statusMessage"], failed.get("error")) == (
        "failed",
        "Warehouse unavailable",
        {"code": -32000, "message": "Warehouse unavailable", "data": {"retryAfterMs": 30000}},
    ) and "result" not in failed, "a JSON-RPC error during the work fails the task and is kept as its error"
    assert poll(us).get("error") == {"code": -32000, "message": "Warehouse unavailable"}, "an error without data has no data"

    purged = rpc(service, "tools/call", name="purge_archive", arguments={})["taskId"]
    service.step(purged)
    answer(purged, confirm=accept(confirm=True))
    service.step(purged)
    answer(purged, reason=accept(reason="retention ended"))
    service.step(purged)
    again = poll(purged)
    assert (again["status"], again.get("error", {}).get("code")) == ("failed", -32603) and "inputRequests" not in again, (
        "an input key is issued once in a task's lifetime"
    )

    before = len(runs)
    stopping = rpc(service, "tools/call", name="generate_report", arguments={"size": "small"})["taskId"]
    rpc(service, "tasks/cancel", taskId=stopping)
    assert poll(stopping)["status"] == "working", "a cancel request is not a stop"
    assert service.step(stopping) is True and poll(stopping)["status"] == "cancelled", (
        "the worker honours a cancel request at its next step"
    )
    assert len(runs) == before, "the tool of a cancelled task does not run"

    mine = rpc(service, "tools/call", name="generate_report", arguments={"size": "medium"})["taskId"]
    service.step(mine)
    unknown = rpc_error(service, "tasks/get", taskId="tsk_000000000000")
    for method, params in (
        ("tasks/get", {}),
        ("tasks/update", {"inputResponses": {"format": accept(format="pdf")}}),
        ("tasks/cancel", {}),
    ):
        assert rpc_error(service, method, principal="alice", taskId=mine, **params) == unknown, (
            f"{method} treats someone else's task exactly like a task that does not exist"
        )
    still = poll(mine)
    assert (still["status"], still.get("inputRequests")) == ("input_required", {"format": FORMAT, "approve_outline": OUTLINE})
    assert rpc_error(service, "tasks/update", taskId=mine, inputResponses=[accept(format="pdf")])["code"] == -32602
    assert service.step("tsk_000000000000") is False, "the worker leaves an unknown task alone"

    clock.advance(minutes=15)
    answer(mine, format=accept(format="pdf"), approve_outline=accept(approved=True))
    assert service.step(mine) is False and poll(mine)["status"] == "failed", (
        "tasks/update fails an overdue task first, as tasks/get does, and takes no input for it"
    )


def sse_messages(frames: list[str]) -> list[dict]:
    """Parse text/event-stream frames into JSON-RPC messages; each frame is one event."""
    messages = []
    for frame in frames:
        assert frame.endswith("\n\n") and "\n\n" not in frame[:-2], "each frame is one SSE event, ending in a blank line"
        data = []
        for line in frame[:-2].split("\n"):
            if line.startswith(":"):
                continue  # a comment, such as a keepalive
            name, colon, value = line.partition(":")
            assert colon and name, f"an SSE line is a field and a value, got {line!r}"
            if name == "data":
                data.append(value[1:] if value.startswith(" ") else value)
        if data:
            messages.append(json.loads("\n".join(data)))
    return messages


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def scripted(changes: list, pulled: list):
    """Ticks for listen: before each tick, the next change happens."""

    async def ticks():
        for change in changes:
            pulled.append(change)
            change()
            yield None

    return ticks()


def listen_request(request_id, task_ids: list, *, tasks: bool = True) -> dict:
    return make_request(request_id, "subscriptions/listen", {"notifications": {"taskIds": task_ids}}, tasks=tasks)


@pytest.mark.skip("Part 4")
def test_listen_stream() -> None:
    """subscriptions/listen streams task snapshots over SSE as they change, to their owner only."""
    clock = Clock()
    store = MemoryStore()
    service = TaskService(store, tools=TOOLS, clock=clock, rng=random.Random(4))
    report = rpc(service, "tools/call", name="generate_report", arguments={"size": "large"})["taskId"]
    export = rpc(service, "tools/call", name="quick_export", arguments={})["taskId"]
    theirs = rpc(service, "tools/call", principal="alice", name="generate_report", arguments={})["taskId"]
    seen = []

    def worker(**fields):
        def change():
            clock.advance(seconds=1)
            move(store, clock, report, **fields)
            seen.append(store.get(report).to_wire())

        return change

    def nothing():
        pass

    def cleanup():
        store.delete(report)  # the finished report is cleaned up while the stream is open

    def deadline():
        clock.now = T0 + timedelta(seconds=60)  # quick_export's ttl runs out

    changes = [
        worker(**WAITING),
        nothing,
        worker(status="completed", status_message="Report completed.", input_requests={}, result=REPORT_RESULT),
        cleanup,
        deadline,
        nothing,
        nothing,
    ]
    pulled: list = []
    request = listen_request(7, [report, theirs, "tsk_ffffffffffff", 42, export, report])
    messages = sse_messages(collect(listen(service, request, principal="user-42", ticks=scripted(changes, pulled))))
    tag = {SUBSCRIPTION_ID_META: 7}
    assert all(message.get("params", message.get("result", {}))["_meta"].get(SUBSCRIPTION_ID_META) == 7 for message in messages), (
        "every message carries the subscription id, the listen request's id"
    )
    assert messages[0] == {
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {"notifications": {"taskIds": [report, export]}, "_meta": tag},
    }, "acknowledge first, listing only the caller's own tasks, each once"
    notes = [message for message in messages if message.get("method") == "notifications/tasks"]
    assert [note["params"]["taskId"] for note in notes] == [report, report, export], "push every change once, and only changes"
    clock.advance(seconds=1)
    later = rpc(service, "tasks/get", taskId=export)
    assert [note["params"] for note in notes] == [
        {**seen[0], "_meta": tag},
        {**seen[1], "_meta": tag},
        {**{key: value for key, value in later.items() if key not in ("resultType", "_meta")}, "_meta": tag},
    ], "a notification carries the task exactly as tasks/get shows it at that moment"
    assert (later["status"], later["lastUpdatedAt"]) == ("failed", "2026-08-21T10:31:00Z")
    assert messages[-1] == {"jsonrpc": "2.0", "id": 7, "result": {"resultType": "complete", "_meta": {**SERVER_META, **tag}}}, (
        "the stream ends with the listen request's result"
    )
    assert len(pulled) == 5, "the stream ends as soon as no watched task is left unfinished"

    probe = rpc(service, "tools/call", name="generate_report", arguments={})["taskId"]
    ticked: list = []

    async def ticks():
        for n in range(10):
            ticked.append(n)
            if n == 0:
                move(store, clock, probe, status_message="Collecting sources.")  # in the second it was created
            yield None

    async def first_two():
        stream = listen(service, listen_request(8, [probe]), principal="user-42", ticks=ticks())
        received = []
        counts = []
        async for frame in stream:
            if sse_messages([frame]):
                received += sse_messages([frame])
                counts.append(len(ticked))
            if len(received) == 2:
                break
        await stream.aclose()
        return received, counts

    received, counts = asyncio.run(first_two())
    assert counts[0] == 0, "acknowledge before waiting for anything to change"
    assert (received[1].get("params", {}).get("statusMessage"), counts[1]) == ("Collecting sources.", 1), (
        "push a change at the first tick that sees it"
    )

    lonely_ticks: list = []
    lonely = sse_messages(
        collect(listen(service, listen_request(9, [theirs, export, "tsk_ffffffffffff", 42]), principal="user-42", ticks=scripted([nothing] * 3, lonely_ticks)))
    )
    assert lonely == [
        {
            "jsonrpc": "2.0",
            "method": "notifications/subscriptions/acknowledged",
            "params": {"notifications": {"taskIds": [export]}, "_meta": {SUBSCRIPTION_ID_META: 9}},
        },
        {"jsonrpc": "2.0", "id": 9, "result": {"resultType": "complete", "_meta": {**SERVER_META, SUBSCRIPTION_ID_META: 9}}},
    ] and lonely_ticks == [], (
        "ids the caller does not own are dropped without a trace; a finished task of its own is acknowledged, with nothing left to send"
    )

    with pytest.raises(McpError) as refused:
        collect(listen(service, listen_request(10, [probe], tasks=False), principal="user-42", ticks=scripted([], [])))
    assert refused.value.code == -32021, "subscriptions/listen needs the Tasks extension declared"


@pytest.mark.skip("Part 5")
def test_leases_and_cleanup(tmp_path) -> None:
    """Two instances share a directory: leases keep their workers apart, and cleanup expires tasks."""
    directory = tmp_path / "tasks"
    clock = Clock()
    runs: list[int] = []
    hooks: list = []

    def job(arguments: dict, answers: dict):
        runs.append(len(runs) + 1)
        number = len(runs)
        if hooks:
            hooks.pop(0)()
        return Done({"content": [{"type": "text", "text": f"run {number}"}], "isError": False}, "Job finished.")

    tools = {"run_job": Tool(job), "quick_export": Tool(job, ttl_ms=60_000), "archive_logs": Tool(job, ttl_ms=None)}
    rng = random.Random(5)

    def instance(worker: str) -> TaskService:
        leases = Leases(directory, clock=clock, lease_ms=30_000)
        return TaskService(TaskStore(directory), tools=tools, clock=clock, rng=rng, leases=leases, worker=worker)

    a, b = instance("worker-a"), instance("worker-b")

    def text(task_id: str) -> str:
        return rpc(a, "tasks/get", taskId=task_id)["result"]["content"][0]["text"]

    crashed = rpc(a, "tools/call", name="run_job", arguments={})["taskId"]
    assert Leases(directory, clock=clock).acquire(crashed, "worker-c")  # worker-c took the task, then died
    assert a.step(crashed) is False and runs == [], "a task leased by another worker is left alone"
    clock.advance(seconds=29)
    assert b.step(crashed) is False, "a lease holds until lease_ms have passed on the clock"
    clock.advance(seconds=1)

    def late_release():
        Leases(directory, clock=clock).release(crashed, "worker-c")  # worker-c wakes up and lets go
        assert a.step(crashed) is False, "a lease taken over from a dead worker belongs to its new holder"

    hooks.append(late_release)
    assert b.step(crashed) is True, "an expired lease can be taken over"
    assert (text(crashed), runs) == ("run 1", [1])

    stalled = rpc(a, "tools/call", name="run_job", arguments={})["taskId"]

    def stall():
        clock.advance(seconds=31)  # worker-a stalls past the end of its lease
        assert b.step(stalled) is True, "a stalled worker's expired lease can be taken over"

    hooks.append(stall)
    assert a.step(stalled) is False, "a worker that lost its lease commits nothing"
    assert text(stalled) == "run 3", "the task keeps the result of the worker that held the lease"
    paused = rpc(a, "tools/call", name="run_job", arguments={})["taskId"]
    hooks.append(lambda: clock.advance(seconds=30))  # worker-a pauses until its lease runs out
    assert a.step(paused) is False, "a lease that has run out is lost, even if no one has taken it over"
    assert b.step(paused) is True and text(paused) == "run 5"
    assert a.step(paused) is False, "a finished task has no work for any worker"
    assert not list(directory.glob("*.lease")), "a worker gives its lease back when its step ends"

    overdue = rpc(a, "tools/call", name="quick_export", arguments={})["taskId"]
    waiting = rpc(a, "tools/call", name="quick_export", arguments={})["taskId"]
    move(a.store, clock, waiting, status="input_required", input_requests={"approve_outline": OUTLINE}, issued_keys=["approve_outline"])
    finished = rpc(a, "tools/call", name="quick_export", arguments={})["taskId"]
    clock.advance(seconds=10)
    assert a.step(finished) is True
    forever = rpc(a, "tools/call", name="archive_logs", arguments={})["taskId"]
    clock.advance(seconds=20)
    fresh = rpc(b, "tools/call", name="quick_export", arguments={})["taskId"]
    clock.advance(seconds=29)
    assert a.sweep() == [], "nothing is due before createdAt + ttlMs"
    clock.advance(seconds=1)
    assert a.sweep() == [finished], "an overdue task that had finished is deleted; one still running is not, yet"
    assert a.store.get(overdue).status == "failed", "a task still running when its ttl runs out is failed first"
    assert a.store.get(waiting).status == "failed", "a task waiting for input has not finished either"
    expired = rpc(b, "tasks/get", taskId=overdue)
    assert (expired.get("error"), expired["lastUpdatedAt"]) == (EXPIRED_ERROR, "2026-08-21T10:32:31Z"), (
        "failing an overdue task is a change, stamped when the sweep makes it"
    )
    assert b.sweep() == sorted([overdue, waiting]), "and deleted by a later sweep, on any instance"
    assert (a.store.get(forever).status, a.store.get(fresh).status) == ("working", "working"), (
        "cleanup leaves tasks that are not due, and tasks with ttlMs null"
    )

    unknown = rpc_error(a, "tasks/get", taskId="tsk_000000000000")
    assert unknown == {"code": -32602, "message": "task not found"}
    assert rpc_error(b, "tasks/get", taskId=finished) == unknown, "a deleted task answers like one that never existed"
    clock.advance(seconds=30)  # fresh is due now
    assert rpc_error(b, "tasks/get", principal="alice", taskId=fresh) == unknown, "someone else's task looks like no task"
    assert a.store.get(fresh).status == "working", "someone else's request never touches your task"
    assert rpc(a, "tasks/get", taskId=fresh)["status"] == "failed", "its owner sees it expire"
    TaskStore(tmp_path / "elsewhere").create(record("tsk_aaaaaaaaaaaa"))
    for bad in ("../elsewhere/tsk_aaaaaaaaaaaa", "tsk_0123", 7):
        assert rpc_error(a, "tasks/get", taskId=bad) == {"code": -32602, "message": "invalid taskId"}, (
            "a malformed task id is invalid params, never a lookup"
        )

    held = Leases(tmp_path / "held", clock=clock, lease_ms=30_000)
    assert held.acquire(fresh, "worker-a")
    clock.advance(seconds=20)
    assert held.acquire(fresh, "worker-a")
    clock.advance(seconds=20)
    assert held.holds(fresh, "worker-a") and not held.acquire(fresh, "worker-b"), "a holder that takes its lease again renews it"
