import asyncio
import json
import time
from contextlib import aclosing
from datetime import datetime, timedelta, timezone

import pytest
from runshape.agent import answer
from runshape.chaos import ScriptedFaults
from runshape.cron import missed, next_fire, parse_cron
from runshape.events import Delivery, Event, EventBus
from runshape.jobstore import JobStore, StoredJob
from runshape.queue import DeadLettered, QueueRuntime
from runshape.stream import RunStream

UTC = timezone.utc
T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z in milliseconds


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self, now) -> None:
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, delta) -> None:
        self.now += delta


async def outcome(rt: QueueRuntime, job_id: str):
    """What a caller of rt.result(job_id) gets. No caller waits longer than 1 s."""
    try:
        return await asyncio.wait_for(rt.result(job_id), 1.0)
    except DeadLettered as dead:
        return ("dead letter", dead.job_id, dead.error)
    except asyncio.TimeoutError:
        raise TimeoutError(f"nothing came back for {job_id} within 1 s") from None


async def run_jobs(rt: QueueRuntime, payloads: list[str], workers: int) -> dict[str, asyncio.Task]:
    """Serve the queue until every job is done or dead, then stop the workers.

    Every job has a caller waiting on it before any worker starts. The callers come back
    finished: caller.result() is what that caller got.
    """
    ids = [rt.enqueue(payload) for payload in payloads]
    callers = {job_id: asyncio.create_task(outcome(rt, job_id)) for job_id in ids}
    everyone = asyncio.gather(*callers.values(), return_exceptions=True)
    server = asyncio.create_task(rt.serve(workers))
    try:
        done, _ = await asyncio.wait({server, everyone}, timeout=2.0, return_when=asyncio.FIRST_COMPLETED)
        if server in done:
            server.result()  # a worker crashed: show its error
        settled = {job_id for job_id, status in rt.log if status in ("done", "dead")}
        assert settled == set(ids), "every queued job finishes, even when jobs arrive together"
        rt.stop()
        stopped, _ = await asyncio.wait({server}, timeout=1.0)
        assert stopped, "serve() returns soon after stop()"
        server.result()
        return callers
    finally:
        server.cancel()
        everyone.cancel()
        await asyncio.gather(server, everyone, return_exceptions=True)


@pytest.mark.skip("Part 1")
def test_queue_and_bus() -> None:
    """Retries and dead letters follow the docstrings, subscribers are isolated, idle workers wake at once."""
    calls: list[str] = []

    def agent(task: str) -> str:
        calls.append(task)
        return f"answered {task}"

    faults = ScriptedFaults(
        {
            "A": [None],
            "B": ["503 unavailable", "429 rate limited", None],
            "C": ["503 unavailable", "429 rate limited", "500 upstream"],
        }
    )
    rt = QueueRuntime(agent, faults, max_attempts=3)
    callers = asyncio.run(run_jobs(rt, ["A", "B", "C"], workers=1))
    assert rt.log == [
        ("j001", "done"),
        ("j002", "retry"),
        ("j003", "retry"),
        ("j002", "retry"),
        ("j003", "retry"),
        ("j002", "done"),
        ("j003", "dead"),
    ], "a job gets max_attempts attempts in total, and a retry goes to the back of the queue"
    assert faults.asked == [("A", 1), ("B", 1), ("C", 1), ("B", 2), ("C", 2), ("B", 3), ("C", 3)], (
        "fail_policy is asked once per attempt"
    )
    dead_letter = ("dead letter", "j003", "500 upstream")
    assert {job_id: caller.result() for job_id, caller in callers.items()} == {
        "j001": "answered A",
        "j002": "answered B",
        "j003": dead_letter,
    }, "a caller gets the answer, or DeadLettered with the job id and the error of the last attempt"
    # a caller that asks only after the job died
    assert asyncio.run(outcome(rt, "j003")) == dead_letter, "DeadLettered also reaches a caller that asks later"
    assert calls == ["A", "B"], "the agent runs once for every attempt that does not fail"
    assert [(job.job_id, job.attempts, job.error) for job in rt.dlq] == [("j003", 3, "500 upstream")], (
        "the dead-letter queue keeps the job and the error of its last attempt"
    )

    calls.clear()
    burst = [f"job {i}" for i in range(12)]
    flaky = ScriptedFaults({task: ["503 unavailable" if i % 4 == 0 else None, None] for i, task in enumerate(burst)})
    callers = asyncio.run(run_jobs(QueueRuntime(agent, flaky, max_attempts=3), burst, workers=3))
    assert {job_id: caller.result() for job_id, caller in callers.items()} == {
        f"j{i + 1:03d}": f"answered job {i}" for i in range(12)
    }
    assert sorted(calls) == sorted(burst), "with several workers, every job still runs exactly once"

    bus = EventBus()
    got: list[tuple[str, str]] = []

    def checks(event: Event) -> list[Event]:
        got.append(("checks", event.id))
        return [Event("checks.done", f"{event.id}/checks", event.payload)]

    def broken(event: Event) -> None:
        raise RuntimeError("boom")

    def labels(event: Event) -> None:
        got.append(("labels", event.id))

    bus.subscribe("pr.opened", "checks", checks)
    bus.subscribe("pr.opened", "broken", broken)
    bus.subscribe("pr.opened", "labels", labels)
    emitted = bus.publish(Event("pr.opened", "pr-7", "#7 add retries"))
    assert got == [("checks", "pr-7"), ("labels", "pr-7")], "a failing subscriber does not stop the others"
    assert bus.dead_letters == [("pr-7", "broken", "RuntimeError: boom")], "a failure is kept as a dead letter"
    assert emitted == [Event("checks.done", "pr-7/checks", "#7 add retries")]

    async def round_trips() -> float:
        rt = QueueRuntime()
        server = asyncio.create_task(rt.serve(workers=1))
        await asyncio.sleep(0.01)  # the worker is idle before the first job arrives
        start = time.perf_counter()
        for i in range(40):
            task = f"step {i}"
            assert await asyncio.wait_for(rt.result(rt.enqueue(task)), 1.0) == answer(task)
        elapsed = time.perf_counter() - start
        rt.stop()
        await asyncio.wait_for(server, 1.0)
        return elapsed

    assert asyncio.run(round_trips()) < 0.2, "an idle worker picks up new work at once"


@pytest.mark.skip("Part 2")
def test_job_store(tmp_path) -> None:
    """Jobs survive a crash and a restart exactly; retries back off; an interrupted attempt still counts."""
    path = str(tmp_path / "jobs.sqlite3")
    clock = FakeClock(T0)
    prompt = 'Review PR #7:\r\n\t"tidy" the café menu ☕  \n'
    trace = 'Traceback (most recent call last):\n  File "agent.py", line 37, in step\nTimeoutError: step 37\n'

    store = JobStore(path, clock, max_attempts=3, backoff_ms=1000)
    a = store.add(prompt)
    b = store.add("nightly eval")
    assert isinstance(a, str) and a != b, "add returns a new id for every job"
    assert store.claim() == StoredJob(a, prompt, "running", 1, T0, (), None), (
        "claim takes the oldest due job and counts the attempt"
    )
    assert store.fail(a, trace) == StoredJob(a, prompt, "pending", 1, T0 + 1000, (trace,), None), (
        "a failed attempt waits backoff_ms before it is due again"
    )
    assert store.claim() == StoredJob(b, "nightly eval", "running", 1, T0, (), None)
    assert store.complete(b, "") == StoredJob(b, "nightly eval", "done", 1, T0, (), ""), (
        "an empty answer is still an answer"
    )
    clock.now = T0 + 999
    assert store.claim() is None, "a job is not handed out before it is due"
    c = store.add("cost report")
    clock.now = T0 + 1000
    assert store.claim().job_id == c, "the job that has been due longest goes first"
    assert store.claim() == StoredJob(a, prompt, "running", 2, T0 + 1000, (trace,), None), (
        "a job can be claimed as soon as it is due"
    )
    store.complete(c, "report: $0.30")
    with pytest.raises(ValueError):
        store.complete(b, "again")
    with pytest.raises(ValueError):
        store.fail(b, "late")
    with pytest.raises(KeyError):
        store.get("no-such-job")
    store.close()  # the worker dies while a is running

    clock.now = T0 + 5000
    store = JobStore(path, clock, max_attempts=3, backoff_ms=1000)
    assert store.get(a) == StoredJob(a, prompt, "pending", 2, T0 + 7000, (trace, "interrupted"), None), (
        "a job left running by a crash fails as interrupted when the store opens"
    )
    clock.now = T0 + 7000
    assert store.claim().attempts == 3
    store.close()  # and dies again

    clock.now = T0 + 8000
    store = JobStore(path, clock, max_attempts=3, backoff_ms=1000)
    dead = StoredJob(a, prompt, "dead", 3, T0 + 7000, (trace, "interrupted", "interrupted"), None)
    assert store.dead_letters() == [dead], "a job that keeps killing its worker still ends in the dead-letter queue"
    assert [store.get(job_id) for job_id in (a, b, c)] == [
        dead,
        StoredJob(b, "nightly eval", "done", 1, T0, (), ""),
        StoredJob(c, "cost report", "done", 1, T0 + 999, (), "report: $0.30"),
    ], "every job reads back exactly after a restart"
    assert store.claim() is None
    store.close()

    dlq_path = str(tmp_path / "dlq.sqlite3")
    one_shot = JobStore(dlq_path, clock, max_attempts=1)
    x = one_shot.add("x")
    y = one_shot.add("y")
    one_shot.claim()
    one_shot.claim()
    one_shot.fail(y, "429 rate limited")  # y dies first ...
    one_shot.fail(x, "500 upstream")  # ... then x, in the same millisecond
    one_shot.close()
    one_shot = JobStore(dlq_path, clock, max_attempts=1)
    assert [job.job_id for job in one_shot.dead_letters()] == [y, x], "dead letters come in the order the jobs died"
    with pytest.raises(ValueError):
        one_shot.complete(x, "too late")
    one_shot.close()

    patient = JobStore(str(tmp_path / "patient.sqlite3"), clock, max_attempts=4, backoff_ms=1000)
    z = patient.add("flaky tool")
    for wait in (1000, 2000, 4000):
        clock.now = patient.get(z).run_at_ms
        patient.claim()
        assert patient.fail(z, "503 unavailable").run_at_ms == clock.now + wait, (
            "each retry waits twice as long as the one before"
        )
    patient.close()


@pytest.mark.skip("Part 3")
def test_cron_schedule() -> None:
    """Parse cron expressions and find when they fire, in UTC, including after downtime."""
    cron = parse_cron("*/20 9-17/4 */10 */5 5-7")
    assert cron.minutes == {0, 20, 40}
    assert cron.hours == {9, 13, 17}, "a step counts from the start of its range"
    assert cron.days == {1, 11, 21, 31}, "a step over * starts at the field's lowest value"
    assert cron.months == {1, 6, 11}
    assert cron.weekdays == {5, 6, 0}, "day of week 7 is Sunday, like 0"
    assert (cron.days_restricted, cron.weekdays_restricted) == (True, True), (
        "a day field is restricted unless it is exactly *"
    )
    assert not parse_cron("0 3 * * *").days_restricted
    for bad in (
        "0 3 * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "5/15 * * * *",
        "10-5 * * * *",
        "*/0 * * * *",
        "1,,2 * * * *",
        "a * * * *",
    ):
        with pytest.raises(ValueError):
            parse_cron(bad)

    tuesday = datetime(2026, 11, 3, 2, 59, 30, tzinfo=UTC)
    fire = next_fire("0 3 * * *", tuesday)
    assert fire == datetime(2026, 11, 3, 3, 0, tzinfo=UTC), "fires fall on whole minutes"
    assert next_fire("0 3 * * *", fire) == datetime(2026, 11, 4, 3, 0, tzinfo=UTC), (
        "the next fire is strictly after the given time"
    )
    assert next_fire("0 0 31 * *", datetime(2026, 9, 1, tzinfo=UTC)) == datetime(2026, 10, 31, tzinfo=UTC), (
        "with day of week *, only the day of the month decides"
    )
    assert next_fire("30 9 * * 1,7", tuesday) == datetime(2026, 11, 8, 9, 30, tzinfo=UTC), (
        "cron counts weekdays from Sunday = 0"
    )
    assert next_fire("0 0 13 * 5", tuesday) == datetime(2026, 11, 6, tzinfo=UTC), (
        "with both day fields restricted, either one is enough"
    )
    beijing = timezone(timedelta(hours=8))
    fire = next_fire("0 3 * * *", datetime(2026, 11, 3, 9, 0, tzinfo=beijing))
    assert fire == datetime(2026, 11, 3, 3, 0, tzinfo=UTC), "the schedule runs on UTC"
    assert fire.utcoffset() == timedelta(0), "fire times are given in UTC"
    with pytest.raises(ValueError):
        next_fire("0 3 * * *", datetime(2026, 11, 3, 2, 0))

    leap_day = parse_cron("0 12 29 2 *")
    start = time.perf_counter()
    assert next_fire(leap_day, datetime(2026, 3, 1, tzinfo=UTC)) == datetime(2028, 2, 29, 12, 0, tzinfo=UTC)
    assert next_fire(leap_day, datetime(2096, 3, 1, tzinfo=UTC)) == datetime(2104, 2, 29, 12, 0, tzinfo=UTC), (
        "2100 is not a leap year"
    )
    assert time.perf_counter() - start < 0.01, (
        "find the next fire without stepping through every minute or every hour"
    )
    with pytest.raises(ValueError):
        next_fire("0 0 30 2 *", tuesday)
    assert next_fire("0 0 30 2 1", tuesday) == datetime(2027, 2, 1, tzinfo=UTC), (
        "30 February never comes, but Mondays in February do"
    )

    last = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)
    assert missed("*/30 * * * *", last, last, "latest") == ([], 0), "the last fire was already handled"
    after_downtime = datetime(2026, 11, 3, 3, 10, tzinfo=UTC)
    assert missed("*/30 * * * *", last, after_downtime, "latest") == (
        [datetime(2026, 11, 3, 3, 0, tzinfo=UTC)],
        3,
    ), "after downtime, catch up with the most recent missed fire only"
    assert missed("*/30 * * * *", last, after_downtime, "skip") == ([], 4), (
        "skip runs no late fire, and every missed fire counts as skipped"
    )
    assert missed("*/30 * * * *", last, datetime(2026, 11, 3, 3, 0, tzinfo=UTC), "latest") == (
        [datetime(2026, 11, 3, 3, 0, tzinfo=UTC)],
        3,
    ), "a fire exactly at now is due"
    assert missed("*/30 * * * *", last, datetime(2026, 11, 3, 3, 0, 20, tzinfo=UTC), "skip") == (
        [datetime(2026, 11, 3, 3, 0, tzinfo=UTC)],
        3,
    ), "a fire in the current minute is on time"
    assert missed("*/30 * * * *", last, datetime(2026, 11, 3, 3, 1, tzinfo=UTC), "skip") == ([], 4), (
        "a fire from the minute before is already late"
    )


def parse_sse(text: str) -> list[dict]:
    """Read server-sent events the way EventSource does: field lines, and a blank line ends each event."""
    *lines, rest = text.split("\n")
    assert rest == "", "every line ends with a newline"
    events: list[dict] = []
    current: dict = {}
    data: list[str] = []
    for line in lines:
        if line == "":
            if current or data:
                if data:
                    current["data"] = json.loads("\n".join(data))
                events.append(current)
                current, data = {}, []
            continue
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "data":
            data.append(value)
        elif name in ("id", "event"):
            current[name] = value
        else:
            raise AssertionError(f"unexpected SSE line {line!r}")
    assert not current and not data, "every event ends with a blank line"
    return events


async def next_chunk(stream):
    """The next SSE message from the stream, or None once the stream has ended."""

    async def pull():
        try:
            return await stream.__anext__()
        except StopAsyncIteration:
            return None

    try:
        return await asyncio.wait_for(pull(), 1.0)
    except asyncio.TimeoutError:
        raise AssertionError("the stream stalls: no event and no end within 1 s") from None


async def settle() -> None:
    """Let every task that can run, run."""
    await asyncio.sleep(0.01)


@pytest.mark.skip("Part 4")
def test_run_stream() -> None:
    """A slow client pauses the agent without losing events; a reconnect resumes after Last-Event-ID."""

    async def paced() -> tuple[list[str], object]:
        clock = FakeClock(0.0)
        received: list[str] = []
        asked: list[int] = []

        async def agent():
            for i in range(1, 7):
                asked.append(i)
                clock.advance(1.0)  # one second of model time per step
                yield f"step {i}"

        run = RunStream(agent(), clock, ahead=2, budget_s=100.0)
        run.start()
        await settle()
        assert len(asked) == 2, "the run works ahead of the client by `ahead` events, then waits"
        async with aclosing(run.events()) as stream:
            for _ in range(2):
                received.append(await next_chunk(stream))
                await settle()
                assert len(asked) == len(received) + 2, (
                    "the run works ahead of the client by `ahead` events, then waits"
                )
        # leaving the block closes the stream: the connection drops, and event 2 never reaches the client
        received.pop()
        await settle()
        assert len(asked) == 4, "a client that disconnects leaves the run paused"
        async with aclosing(run.events(last_event_id="1")) as stream:
            while (chunk := await next_chunk(stream)) is not None:
                received.append(chunk)
                await settle()
                assert len(asked) <= len(received) + 2, "never more than `ahead` events wait for the client"
        async with aclosing(run.events(last_event_id="7")) as stream:
            return received, await next_chunk(stream)

    received, after_final = asyncio.run(paced())
    assert [len(parse_sse(chunk)) for chunk in received] == [1] * len(received), "one SSE message per chunk"
    events = parse_sse("".join(received))
    assert [event["id"] for event in events] == [str(i) for i in range(1, 8)], (
        "a reconnect resumes right after Last-Event-ID"
    )
    assert [event["event"] for event in events] == ["step"] * 6 + ["final"]
    assert [event["data"] for event in events] == [{"text": f"step {i}"} for i in range(1, 7)] + [
        {"status": "done", "steps": 6}
    ]
    assert after_final is None, "the final event is sent once"

    async def budget_run(steps: int, budget_s: float, pause_s: float) -> dict:
        clock = FakeClock(0.0)

        async def agent():
            for i in range(1, steps + 1):
                clock.advance(1.0)
                yield f"step {i}"

        run = RunStream(agent(), clock, ahead=1, budget_s=budget_s)
        run.start()
        stream = run.events()
        chunks = []
        while (chunk := await next_chunk(stream)) is not None:
            chunks.append(chunk)
            clock.advance(pause_s)  # the client takes this long over every event
        return parse_sse("".join(chunks))[-1]

    assert asyncio.run(budget_run(4, 5.0, 10.0))["data"] == {"status": "done", "steps": 4}, (
        "time paused for the client does not count against the budget"
    )
    assert asyncio.run(budget_run(20, 4.0, 0.0)) == {
        "id": "5",
        "event": "final",
        "data": {"status": "budget", "steps": 4},
    }, "the run stops once its work reaches budget_s"


@pytest.mark.skip("Part 5")
def test_event_cascade() -> None:
    """Follow-up events fan out breadth first, each subscriber handles an event once, and depth is capped."""

    def emits(*kinds: str):
        def handler(event: Event) -> list[Event]:
            return [Event(kind, f"{event.payload}:{kind}", event.payload) for kind in kinds]

        return handler

    bus = EventBus()
    bus.subscribe("pr.opened", "reviewer", emits("review.done"))
    bus.subscribe("pr.opened", "labeler", emits("labels.set"))
    bus.subscribe("review.done", "notifier", emits("notify"))
    bus.subscribe("review.done", "merger", emits("merge.ready"))
    bus.subscribe("labels.set", "notifier", emits("notify", "stats"))
    bus.subscribe("notify", "pager", emits("stats"))
    bus.subscribe("merge.ready", "deployer", emits("deploy"))
    bus.subscribe("deploy", "smoke", emits())

    pr = Event("pr.opened", "pr7", "pr7")
    report = bus.cascade(pr, max_depth=2)
    assert report.deliveries == [
        Delivery(0, "pr7", "reviewer"),
        Delivery(0, "pr7", "labeler"),
        Delivery(1, "pr7:review.done", "notifier"),
        Delivery(1, "pr7:review.done", "merger"),
        Delivery(1, "pr7:labels.set", "notifier"),
        Delivery(2, "pr7:notify", "pager"),
        Delivery(2, "pr7:merge.ready", "deployer"),
    ], "deliver breadth first with depth counted from 0; an event reached twice is handled once"
    assert report.truncated == ["pr7:deploy"], "an event deeper than max_depth is recorded, not delivered"
    assert report.unhandled == ["pr7:stats"], "an event nobody subscribes to is recorded"

    bus.subscribe("pr.opened", "auditor", emits("audit"))
    replay = bus.cascade(pr, max_depth=2)
    assert replay.deliveries == [Delivery(0, "pr7", "auditor")], (
        "a replay reaches only the subscribers that have not handled the event"
    )
    assert replay.unhandled == ["pr7:audit"]

    flaky = EventBus()
    calls: list[str] = []

    def evaluator(event: Event) -> list[Event]:
        calls.append(event.id)
        if len(calls) == 1:
            raise TimeoutError("model call timed out")
        return [Event("eval.done", f"{event.id}:done")]

    flaky.subscribe("eval.nightly", "evaluator", evaluator)
    nightly = Event("eval.nightly", "2026-11-03")
    failed = flaky.cascade(nightly, max_depth=3)
    assert (failed.deliveries, failed.unhandled) == ([], []), (
        "a failed delivery is a dead letter, not a delivery or an unhandled event"
    )
    assert flaky.dead_letters == [("2026-11-03", "evaluator", "TimeoutError: model call timed out")]
    assert flaky.cascade(nightly, max_depth=3).deliveries == [Delivery(0, "2026-11-03", "evaluator")], (
        "a delivery that failed is tried again on replay"
    )
    flaky.subscribe("eval.nightly", "reporter", lambda event: None)
    assert flaky.cascade(nightly, max_depth=3).deliveries == [Delivery(0, "2026-11-03", "reporter")], (
        "deliveries lists every successful delivery, even one that emits nothing"
    )

    loop = EventBus()
    ids = iter(range(1, 100))
    loop.subscribe("ping", "ponger", lambda event: [Event("pong", f"pong-{next(ids)}")])
    loop.subscribe("pong", "pinger", lambda event: [Event("ping", f"ping-{next(ids)}")])
    report = loop.cascade(Event("ping", "ping-0"), max_depth=3)
    assert [d.event_id for d in report.deliveries] == ["ping-0", "pong-1", "ping-2", "pong-3"], (
        "a subscriber handles every new event id, even of a type it has handled before"
    )
    assert report.truncated == ["ping-4"], "a loop of fresh events stops at max_depth"
