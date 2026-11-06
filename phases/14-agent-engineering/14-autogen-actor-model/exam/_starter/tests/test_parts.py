import asyncio
import itertools
import json
import random
import struct
import time

import pytest
from actorrt.journal import Journal
from actorrt.review import REVIEWS, ChecklistAgent, ReviewerAgent
from actorrt.runtime import Actor, Message, Runtime
from actorrt.teams import RoundRobinGroupChat, SelectorGroupChat
from actorrt.transport import Link


class Collect(Actor):
    """Keeps the body of every message it receives."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.got: list = []

    def receive(self, message: Message, runtime: Runtime) -> None:
        self.got.append(message.body)


class Audit(Actor):
    """Keeps a ledger of the verdicts it hears on the reviews topic."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.heard: list[tuple] = []

    def receive(self, message: Message, runtime: Runtime) -> None:
        verdict = message.body
        self.heard.append((verdict["id"], verdict["ok"], verdict["issues"]))


class Splitter(Actor):
    """Forwards each line of a batch to the indexer. A batch with a blank line is rejected."""

    def receive(self, message: Message, runtime: Runtime) -> None:
        for line in message.body:
            if not line.strip():
                raise ValueError("blank line in batch")
            runtime.send(self.name, "indexer", "line", line)


class Batcher(Actor):
    """Sends the indexer its lines in pairs, reusing one buffer."""

    def receive(self, message: Message, runtime: Runtime) -> None:
        buffer: list[str] = []
        for line in message.body:
            buffer.append(line)
            if len(buffer) == 2:
                runtime.send(self.name, "indexer", "pair", buffer)
                buffer.clear()


SNIPPETS = [
    "def add(a, b): return a + b",
    "def hazard(): eval('1+1')",
    "def silent():\n    try:\n        f()\n    except:\n        pass",
    "def worst(s):\n    try:\n        return eval(s)\n    except:\n        return None",
]


def review_runtime(**options) -> tuple[Runtime, ReviewerAgent, ChecklistAgent]:
    runtime = Runtime(**options)
    reviewer = ReviewerAgent("reviewer")
    checklist = ChecklistAgent("checklist", partner="reviewer")
    runtime.register(reviewer)
    runtime.register(checklist)
    runtime.subscribe(REVIEWS, "checklist")
    return runtime, reviewer, checklist


@pytest.mark.skip("Part 1")
def test_runtime_delivery() -> None:
    """Sends wait in the inbox and a failure stays with its own message; actors share no memory,
    a handler that raises sends nothing, and the checklist waits for every verdict."""
    runtime, reviewer, checklist = review_runtime()
    audit = Audit("audit")
    runtime.register(audit)
    runtime.subscribe(REVIEWS, "audit")
    snippets = list(SNIPPETS)
    runtime.send("__user__", "checklist", "start", snippets)
    snippets.append("def late(): eval(x)")  # the caller goes on using its list
    assert runtime.run_until_idle() is True
    assert runtime.dead_letters == [], "a clean review leaves the dead-letter queue empty"
    assert len(reviewer.verdicts) == 4, "a message carries its body as it was when it was sent"
    published = [
        {"id": 0, "ok": True, "issues": []},
        {"id": 1, "ok": False, "issues": ["uses eval"]},
        {"id": 2, "ok": False, "issues": ["bare except"]},
        {"id": 3, "ok": False, "issues": ["uses eval", "bare except"]},
    ]
    assert reviewer.verdicts == published, "the reviewer's verdicts stay as it recorded them"
    assert audit.heard == [(v["id"], v["ok"], v["issues"]) for v in published], (
        "every subscriber hears a verdict as the reviewer published it"
    )
    assert (checklist.results, checklist.consensus) == (
        {
            0: {"ok": True, "issues": []},
            1: {"ok": False, "issues": ["uses eval"]},
            2: {"ok": False, "issues": ["bare except"]},
            3: {"ok": False, "issues": ["bare except", "uses eval"]},
        },
        False,
    ), "the checklist keeps each snippet's verdict, issues sorted"

    runtime, reviewer, checklist = review_runtime()
    audit = Audit("audit")
    runtime.register(audit)
    runtime.subscribe(REVIEWS, "audit")
    runtime.send("__user__", "checklist", "start", ["x = 1", None, "y = eval(s)"])
    assert runtime.run_until_idle() is True
    assert [(m.sender, m.recipient, m.topic, m.body, reason) for m, reason in runtime.dead_letters] == [
        ("checklist", "reviewer", "review", {"id": 1, "code": None}, "TypeError: snippet 1 is not text"),
    ], "the message whose handler raised is the one dead-lettered"
    assert ([v["id"] for v in reviewer.verdicts], audit.heard, checklist.results) == (
        [0, 2],
        [(0, True, []), (2, False, ["uses eval"])],
        {0: {"ok": True, "issues": []}, 2: {"ok": False, "issues": ["uses eval"]}},
    ), "one actor crashing does not crash another"

    runtime, reviewer, _ = review_runtime()
    runtime.send("__user__", "checklist", "start", ["x = 1", "y = 2"])
    assert runtime.run_until_idle(max_messages=1) is False, "a message sent from a handler waits in the inbox for its turn"
    assert ([(m.recipient, m.body) for m in runtime.pending()], reviewer.verdicts) == (
        [("reviewer", {"id": 0, "code": "x = 1"}), ("reviewer", {"id": 1, "code": "y = 2"})],
        [],
    ), "a message sent from a handler waits in the inbox for its turn"
    assert runtime.run_until_idle() is True

    runtime = Runtime()
    indexer = Collect("indexer")
    runtime.register(indexer)
    runtime.register(Batcher("batcher"))
    runtime.send("__user__", "batcher", "lines", ["a", "b", "c", "d"])
    assert runtime.run_until_idle() is True
    assert indexer.got == [["a", "b"], ["c", "d"]], "a message carries its body as it was when it was sent"

    runtime = Runtime()
    indexer = Collect("indexer")
    runtime.register(indexer)
    runtime.register(Splitter("splitter"))
    runtime.send("__user__", "splitter", "batch", ["alpha", "beta"])
    bad = runtime.send("__user__", "splitter", "batch", ["gamma", " ", "delta"])
    assert runtime.run_until_idle() is True
    assert "gamma" not in indexer.got, "a handler that raises sends nothing"
    assert indexer.got == ["alpha", "beta"], "messages from calls that returned are still delivered"
    assert [(m.mid, reason) for m, reason in runtime.dead_letters] == [(bad, "ValueError: blank line in batch")], (
        "the failed message is dead-lettered with its error"
    )
    worse = runtime.send("__user__", "splitter", "batch", ["\t"])
    assert runtime.run_until_idle() is True
    runtime.send("__user__", "splitter", "batch", ["epsilon"])
    assert runtime.run_until_idle() is True
    assert indexer.got == ["alpha", "beta", "epsilon"], "the runtime keeps delivering after a failure"
    assert [m.mid for m, _ in runtime.dead_letters] == [bad, worse]

    runtime, reviewer, checklist = review_runtime()
    runtime.send("__user__", "checklist", "start", ["x = 1", "y = 2", "z = 3", "w = eval(s)"])
    assert runtime.run_until_idle(max_messages=6) is False, "a run stops at max_messages"
    assert len(checklist.results) == 1
    assert checklist.consensus is None, "the checklist decides only once every verdict is in"
    assert runtime.run_until_idle() is True
    assert checklist.consensus is False, "one failed snippet means no consensus"
    for snippets, expected, why in [
        (["x = 1", None, "y = 2"], None, "a verdict that never comes back leaves the checklist undecided"),
        (["x = eval(s)", None], None, "a verdict that never comes back leaves the checklist undecided"),
        (["x = 1", "y = eval(s)"], False, "one failed snippet means no consensus"),
        (["a = 1", "b = 2", "c = 3", "d = 4"], True, "consensus once every snippet is ok"),
    ]:
        runtime.send("__user__", "checklist", "start", snippets)
        assert runtime.run_until_idle() is True
        assert checklist.consensus is expected, why

    runtime = Runtime()
    dashboard = Collect("dashboard")
    panels = [Collect(f"panel-{i}") for i in range(10)]
    for actor in [dashboard, *panels]:
        runtime.register(actor)
    start = time.perf_counter()
    for machine in range(8000):
        runtime.subscribe(f"alert.{machine}", "dashboard")
    for i in range(20000):
        runtime.publish("fleet", f"reading.{i % 5000}", i)  # telemetry nobody watches
    elapsed = time.perf_counter() - start
    assert (runtime.pending(), runtime.dead_letters) == ([], []), "a topic nobody subscribes to swallows the message"
    assert elapsed < 0.1, "publishing must not slow down as subscriptions grow"
    for panel in reversed(panels):
        runtime.subscribe("alert.7", panel.name)
    runtime.subscribe("alert.7", "dashboard")
    runtime.subscribe("alert.7", "panel-3")
    mids = runtime.publish("fleet", "alert.7", {"machine": 7, "temp": 91.5})
    assert [m.recipient for m in runtime.pending()] == ["dashboard"] + [p.name for p in reversed(panels)], (
        "subscribers hear a topic once each, in the order they first subscribed"
    )
    assert mids == [m.mid for m in runtime.pending()], "publish returns the mid of every message it sent"
    assert runtime.run_until_idle() is True
    assert dashboard.got == [{"machine": 7, "temp": 91.5}]


def exact(value):
    """A comparable form that tells 1 from 1.0 and True, -0.0 from 0.0, and keeps dict key order."""
    if isinstance(value, Message):
        return ("Message", [(f, exact(getattr(value, f))) for f in ("sender", "recipient", "topic", "body", "mid")])
    if isinstance(value, dict):
        return ("dict", [(key, exact(item)) for key, item in value.items()])
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [exact(item) for item in value])
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


BODY = {
    "snippet": "def grüße():\n    return '東京 🚚'",
    "issues": ["uses eval", "bare except"],
    "lines": [1, 2.5, None, True, False, ""],
    "nested": {"z": {}, "a": [[]]},
    "order_id": 2**64 + 1,
    "ratio": 0.1 + 0.2,
    "offset": -0.0,
    "count": 1,
}


def records(data: bytes) -> list[tuple]:
    """(kind, mid, payload) for each record, read the way the ops tooling reads a journal."""
    out = []
    pos = 0
    while pos < len(data):
        kind, mid, size = struct.unpack_from(">cQI", data, pos)
        payload = data[pos + 13 : pos + 13 + size]
        assert len(payload) == size, "a record holds as many payload bytes as its header says"
        pos += 13 + size
        if kind == b"M":
            out.append(("M", mid, json.loads(payload.decode("utf-8"))))
        elif kind == b"D":
            out.append(("D", mid, payload.decode("utf-8")))
        else:
            assert (kind, payload) == (b"A", b""), "every record is M, A or D"
            out.append(("A", mid, None))
    return out


class Crash(BaseException):
    """Stands in for the process dying in the middle of a handler."""


class Fragile(Actor):
    """Sends a line to the indexer, then the process dies."""

    def receive(self, message: Message, runtime: Runtime) -> None:
        runtime.send(self.name, "indexer", "line", "half done")
        raise Crash()


def journaled(path) -> tuple[Runtime, Journal]:
    journal = Journal(path)
    runtime = Runtime(journal=journal)
    for actor in (Collect("indexer"), Splitter("splitter"), Fragile("fragile")):
        runtime.register(actor)
    return runtime, journal


def queued(sender: str, recipient: str, topic: str, body) -> dict:
    return {"sender": sender, "recipient": recipient, "topic": topic, "body": body}


@pytest.mark.skip("Part 2")
def test_journal_recovery(tmp_path) -> None:
    """After a crash the inbox comes back as it was: what was queued and the dead letters, never what was handled."""
    path = tmp_path / "inbox.journal"
    runtime, journal = journaled(path)
    assert runtime.send("__user__", "splitter", "batch", ["alpha", " "]) == 1
    runtime.send("__user__", "büro", "line", "lost")
    runtime.send("__user__", "splitter", "batch", ["beta", "Grüße aus 東京"])
    runtime.send("__user__", "indexer", "line", BODY)
    assert runtime.run_until_idle(max_messages=3) is False
    written = [
        ("M", 1, queued("__user__", "splitter", "batch", ["alpha", " "])),
        ("M", 2, queued("__user__", "büro", "line", "lost")),
        ("M", 3, queued("__user__", "splitter", "batch", ["beta", "Grüße aus 東京"])),
        ("M", 4, queued("__user__", "indexer", "line", BODY)),
        ("D", 1, "ValueError: blank line in batch"),
        ("D", 2, "no actor 'büro'"),
        ("M", 6, queued("splitter", "indexer", "line", "beta")),
        ("M", 7, queued("splitter", "indexer", "line", "Grüße aus 東京")),
        ("A", 3, None),
    ]
    assert records(path.read_bytes()) == written, (
        "the journal holds what was queued, handled and dead-lettered, in that order, as soon as it happens"
    )

    # the process died without closing the journal
    restored, journal = journaled(path)
    assert [exact(m) for m in restored.pending()] == [
        exact(Message("__user__", "indexer", "line", BODY, 4)),
        exact(Message("splitter", "indexer", "line", "beta", 6)),
        exact(Message("splitter", "indexer", "line", "Grüße aus 東京", 7)),
    ], "what was queued and never handled is queued again, exactly as it was"
    assert [(exact(m), reason) for m, reason in restored.dead_letters] == [
        (exact(Message("__user__", "splitter", "batch", ["alpha", " "], 1)), "ValueError: blank line in batch"),
        (exact(Message("__user__", "büro", "line", "lost", 2)), "no actor 'büro'"),
    ], "dead letters come back with their reasons"
    assert records(path.read_bytes()) == written, "opening a journal adds nothing to it"
    assert journal.recover().next_mid == 8, "mids keep counting across restarts"
    assert restored.run_until_idle() is True
    assert exact(restored.actors["indexer"].got) == exact([BODY, "beta", "Grüße aus 東京"])
    journal.close()

    calm, journal = journaled(path)
    assert (calm.pending(), len(calm.dead_letters)) == ([], 2), "nothing handled comes back"
    assert calm.send("__user__", "fragile", "line", "go") == 8, "mids keep counting across restarts"
    with pytest.raises(Crash):
        calm.run_until_idle()

    # the process died in the middle of a handler
    again, journal = journaled(path)
    assert [exact(m) for m in again.pending()] == [exact(Message("__user__", "fragile", "line", "go", 8))], (
        "a message whose handler never finished is queued again, without what it sent"
    )
    whole = path.read_bytes()
    assert again.send("__user__", "indexer", "line", "torn") == 9
    journal.close()
    record = path.read_bytes()[len(whole) :]
    for cut in range(1, len(record)):
        path.write_bytes(whole + record[:cut])
        torn, journal = journaled(path)
        assert [m.mid for m in torn.pending()] == [8], "a record cut short by a crash is dropped"
        journal.close()
    path.write_bytes(whole + record[:20])
    torn, journal = journaled(path)
    assert torn.send("__user__", "indexer", "line", "after the crash") == 9
    journal.close()
    assert records(path.read_bytes())[-1] == ("M", 9, queued("__user__", "indexer", "line", "after the crash")), (
        "records written after a torn one read back"
    )


class Speaker(Actor):
    """A scripted participant, standing in for a model: each speak request gets its next line."""

    def __init__(self, name: str, lines: list[str]) -> None:
        super().__init__(name)
        self.lines = list(lines)
        self.heard: list = []

    def receive(self, message: Message, runtime: Runtime) -> None:
        if message.topic == "speak":
            self.heard.append(message.body)
            runtime.send(self.name, message.sender, "said", self.lines.pop(0))


def chat_runtime(**lines: list[str]) -> tuple[Runtime, dict[str, Speaker]]:
    runtime = Runtime()
    speakers = {name: Speaker(name, said) for name, said in lines.items()}
    for speaker in speakers.values():
        runtime.register(speaker)
    return runtime, speakers


TASK = "Add retries to the HTTP client. Reply APPROVE when the patch is ready."


@pytest.mark.skip("Part 3")
def test_group_chat() -> None:
    """Teams on the runtime: a fixed rotation, and a selector whose bad picks fall back to the rotation."""
    runtime, speakers = chat_runtime(
        coder=["patch v1", "patch v2"],
        reviewer=["NOT APPROVED: no test", "approve once CI is green"],
        tester=["DISAPPROVE: flaky", "APPROVED by QA"],
    )
    team = RoundRobinGroupChat(runtime, ["coder", "reviewer", "tester"], max_messages=6, stop_word="APPROVE")
    runtime.send("tester", "team", "said", "a late answer from an earlier chat")
    result = team.run(TASK)
    assert result.messages == [
        ("user", TASK),
        ("coder", "patch v1"),
        ("reviewer", "NOT APPROVED: no test"),
        ("tester", "DISAPPROVE: flaky"),
        ("coder", "patch v2"),
        ("reviewer", "approve once CI is green"),
    ], "the rotation goes on until the chat holds max_messages messages, the task included"
    assert result.stop_reason == "max_messages", "a stop word counts only as a whole word, in its own case"
    assert result.selections == [(name, "rotation") for name in ["coder", "reviewer", "tester", "coder", "reviewer"]], (
        "a round-robin turn is chosen by rotation"
    )
    assert speakers["tester"].heard == [[["user", TASK], ["coder", "patch v1"], ["reviewer", "NOT APPROVED: no test"]]], (
        "a speaker hears the conversation so far"
    )

    runtime, speakers = chat_runtime(
        coder=["patch v1", "patch v2"], reviewer=["FIX: add a test", "Looks good. APPROVE!"], tester=["green", "green"]
    )
    team = RoundRobinGroupChat(runtime, ["coder", "reviewer", "tester"], max_messages=20, stop_word="APPROVE")
    result = team.run(TASK)
    assert (result.messages[-1], len(result.messages), result.stop_reason) == (
        ("reviewer", "Looks good. APPROVE!"),
        6,
        "stop_word",
    ), "the chat stops right after the message with the stop word"
    assert speakers["tester"].lines == ["green"], "nobody speaks after the stop word"

    runtime, _ = chat_runtime(coder=["patch"], reviewer=["APPROVE"])
    result = RoundRobinGroupChat(runtime, ["coder", "reviewer"], max_messages=3, stop_word="APPROVE").run("Go.")
    assert (len(result.messages), result.stop_reason) == (3, "stop_word"), "the stop word wins when both end the chat"

    runtime, speakers = chat_runtime(coder=["c1"])
    result = RoundRobinGroupChat(runtime, ["coder"], max_messages=1).run("Go.")
    assert (result.messages, result.stop_reason, speakers["coder"].heard) == ([("user", "Go.")], "max_messages", []), (
        "the task counts toward max_messages"
    )

    answers = iter(["reviewer", " coder\n", "the reviewer", "reviewer", "coder", "TESTER", "tester"])
    seen = []

    def selector(messages, participants) -> str:
        seen.append((messages, participants))
        return next(answers)

    runtime, speakers = chat_runtime(coder=["c1", "c2"], reviewer=["r1", "r2", "r3"], tester=["t1", "t2"])
    team = SelectorGroupChat(runtime, ["coder", "reviewer", "tester"], selector, max_messages=8, stop_word="APPROVE")
    result = team.run("Fix the flaky retry test.")
    assert result.selections == [
        ("reviewer", "selector"),
        ("coder", "selector"),
        ("reviewer", "unknown"),
        ("tester", "repeat"),
        ("coder", "selector"),
        ("reviewer", "unknown"),
        ("tester", "selector"),
    ], "a bad pick falls back to whoever follows the last speaker"
    assert [source for source, _ in result.messages] == [
        "user", "reviewer", "coder", "reviewer", "tester", "coder", "reviewer", "tester",
    ], "the chosen participant is the one who speaks"
    assert seen[2] == (
        [("user", "Fix the flaky retry test."), ("reviewer", "r1"), ("coder", "c1")],
        ["coder", "reviewer", "tester"],
    ), "the selector sees the conversation so far and the participants in order"

    answers = iter(["coder", "coder", "Bob"])
    runtime, _ = chat_runtime(coder=["c1", "c2"], reviewer=["r1"])
    team = SelectorGroupChat(
        runtime, ["coder", "reviewer"], lambda m, p: next(answers), allow_repeated_speaker=True, max_messages=4
    )
    assert team.run("Refactor the client.").selections == [
        ("coder", "selector"),
        ("coder", "selector"),
        ("reviewer", "unknown"),
    ], "allow_repeated_speaker lets the selector pick the last speaker again"

    runtime, _ = chat_runtime(coder=["c1"], reviewer=["LGTM"])
    result = RoundRobinGroupChat(runtime, ["coder", "reviewer"], stop_word="APPROVE").run("Ship it.")
    assert (result.messages, result.stop_reason) == (
        [("user", "Ship it."), ("coder", "c1"), ("reviewer", "LGTM")],
        "stalled",
    ), "a participant that fails leaves the chat stalled"
    assert [(m.recipient, m.topic) for m, _ in runtime.dead_letters] == [("coder", "speak")]

    runtime, _ = chat_runtime(coder=[f"patch v{n}" for n in range(1, 31)], reviewer=["FIX: add a test"] * 29)
    result = RoundRobinGroupChat(runtime, ["coder", "reviewer"], max_messages=60).run(TASK)
    assert (len(result.messages), result.stop_reason) == (60, "max_messages"), (
        "a chat stalls only when the runtime goes idle"
    )


def frame(fields) -> bytes:
    payload = json.dumps(fields, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def unframe(item: bytes) -> dict:
    """Read one item of the outgoing stream: exactly one whole frame."""
    (size,) = struct.unpack(">I", item[:4])
    assert len(item) == 4 + size, "every item is one whole frame"
    return json.loads(item[4:].decode("utf-8"))


async def arrive(data: bytes, sizes: list[int], pulled: list[int]):
    """The stream as chunks of the given sizes; pulled records how many bytes have been read."""
    pos = 0
    for size in sizes:
        pos += size
        pulled.append(pos)
        yield data[pos - size : pos]
    if pos < len(data):
        pulled.append(len(data))
        yield data[pos:]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


class Echo(Actor):
    """Answers a ping with a pong that carries the same body."""

    def receive(self, message: Message, runtime: Runtime) -> None:
        runtime.send(self.name, message.sender, "pong", {"echo": message.body})


def host_b() -> tuple[Runtime, Link, ReviewerAgent]:
    runtime = Runtime()
    reviewer = ReviewerAgent("reviewer")
    runtime.register(reviewer)
    runtime.register(Echo("echo"))
    link = Link(runtime, remote=["checklist", "audit"])
    runtime.subscribe(REVIEWS, "checklist")
    runtime.subscribe(REVIEWS, "audit")
    return runtime, link, reviewer


HEARTBEAT = b"\x00\x00\x00\x00"
GREETING = "Grüß dich, 東京 🚚"
REQUESTS = [
    {"mid": 2, "sender": "checklist", "recipient": "reviewer", "topic": "review", "body": {"id": 0, "code": "def grüße(): eval('東京')"}},
    {"mid": 3, "sender": "checklist", "recipient": "echo", "topic": "ping", "body": GREETING},
    {"mid": 4, "sender": "checklist", "recipient": "ghost", "topic": "review", "body": None},
    {"mid": 5, "sender": "checklist", "recipient": "echo", "topic": "ping", "body": ""},
    {"mid": 6, "sender": "checklist", "recipient": "reviewer", "topic": "review", "body": {"id": 1, "code": "x = 1"}},
]
FLAGGED = {"id": 0, "ok": False, "issues": ["uses eval"]}
CLEAN = {"id": 1, "ok": True, "issues": []}
REPLIES = [
    {"mid": 2, "sender": "reviewer", "recipient": "checklist", "topic": "reviews", "body": FLAGGED},
    {"mid": 3, "sender": "reviewer", "recipient": "audit", "topic": "reviews", "body": FLAGGED},
    {"mid": 5, "sender": "echo", "recipient": "checklist", "topic": "pong", "body": {"echo": GREETING}},
    {"mid": 8, "sender": "echo", "recipient": "checklist", "topic": "pong", "body": {"echo": ""}},
    {"mid": 10, "sender": "reviewer", "recipient": "checklist", "topic": "reviews", "body": CLEAN},
    {"mid": 11, "sender": "reviewer", "recipient": "audit", "topic": "reviews", "body": CLEAN},
]


@pytest.mark.skip("Part 4")
def test_link_frames() -> None:
    """Frames from another host are delivered as they complete, and each reply goes back as a frame at once."""
    pieces = [HEARTBEAT, frame(REQUESTS[0]), frame(REQUESTS[1]), HEARTBEAT] + [frame(r) for r in REQUESTS[2:]]
    wire = b"".join(pieces)
    ends = list(itertools.accumulate(len(p) for p in pieces))
    answered = [ends[1], ends[1], ends[2], ends[5], ends[6], ends[6]]  # where the frame behind each reply ends
    rng = random.Random(14)
    jagged = []
    while sum(jagged) < len(wire):
        jagged.append(min(rng.choice([0, 1, 2, 3, 5, 8, 13, 40]), len(wire) - sum(jagged)))
    headers = [ends[0] + 4, ends[1] - ends[0] - 4, 4, ends[2] - ends[1] - 4, len(wire) - ends[2]]
    for sizes in ([len(wire)], [1] * len(wire), jagged, headers):
        runtime, link, reviewer = host_b()
        pulled: list[int] = []
        seen = []

        async def watch() -> None:
            async for item in link.serve(arrive(wire, sizes, pulled)):
                seen.append((item, pulled[-1], len(reviewer.verdicts)))

        asyncio.run(watch())
        replies = [unframe(item) for item, _, _ in seen]
        assert [{**r, "mid": 0} for r in replies] == [{**r, "mid": 0} for r in REPLIES], (
            f"one reply frame per answered message, sizes {sizes[:8]}"
        )
        assert GREETING.encode("utf-8") in seen[2][0], "non-ASCII text travels as UTF-8"
        boundaries = list(itertools.accumulate(sizes))
        assert [(read, verdicts) for _, read, verdicts in seen] == [
            (min(b for b in boundaries if b >= end), verdicts) for end, verdicts in zip(answered, [1, 1, 1, 1, 2, 2])
        ], f"a reply goes out right after the frame that caused it, sizes {sizes[:8]}"
        assert [r["mid"] for r in replies] == [r["mid"] for r in REPLIES], "a frame carries its mid on the host that sent it"
        assert [(m.recipient, reason) for m, reason in runtime.dead_letters] == [("ghost", "no actor 'ghost'")]

    runtime, link, _ = host_b()
    runtime.send("reviewer", "checklist", "hello", "ready")
    runtime.send("echo", "audit", "hello", "ready too")
    runtime.run_until_idle()
    pulled = []

    async def first_out() -> list[bytes]:
        agen = link.serve(arrive(wire, [len(wire)], pulled))
        items = [await agen.__anext__(), await agen.__anext__()]
        await agen.aclose()
        return items

    assert [(unframe(item)["body"], list(pulled)) for item in asyncio.run(first_out())] == [
        ("ready", []),
        ("ready too", []),
    ], "frames already waiting go out before anything is read"

    host_a = Runtime()
    checklist = ChecklistAgent("checklist", partner="reviewer")
    audit = Audit("audit")
    host_a.register(checklist)
    host_a.register(audit)
    link_a = Link(host_a, remote=["reviewer"])
    runtime, link_b, _ = host_b()
    host_a.send("__user__", "checklist", "start", ["x = 1", "def grüße(): eval(s)"])
    assert host_a.run_until_idle() is True
    requests = link_a.take()
    assert [unframe(f)["body"] for f in requests] == [{"id": 0, "code": "x = 1"}, {"id": 1, "code": "def grüße(): eval(s)"}]
    assert link_a.take() == [], "take() hands each frame out once"
    replies = collect(link_b.serve(arrive(b"".join(requests), [5, 0, 17, 1], [])))
    assert collect(link_a.serve(arrive(b"".join(replies), [3, 30], []))) == []
    assert (checklist.results, checklist.consensus, audit.heard) == (
        {0: {"ok": True, "issues": []}, 1: {"ok": False, "issues": ["uses eval"]}},
        False,
        [(0, True, []), (1, False, ["uses eval"])],
    ), "the same actors work across two hosts"

    pong = {"mid": 2, "sender": "echo", "recipient": "checklist", "topic": "pong", "body": {"echo": GREETING}}
    for broken in (
        frame(REQUESTS[4])[:-3],
        frame(REQUESTS[4])[:3],
        frame([1, 2]) + frame(REQUESTS[3]),
        frame({"sender": "checklist", "recipient": "echo", "body": 1}),
        frame({"sender": "checklist", "recipient": "echo", "topic": None, "body": 1}),
        struct.pack(">I", 2) + b"\xff\xfe",
    ):
        runtime, link, _ = host_b()
        got = []

        async def until_error(data: bytes) -> None:
            async for item in link.serve(arrive(data, [len(data)], [])):
                got.append(unframe(item))

        with pytest.raises(ValueError):
            asyncio.run(until_error(frame(REQUESTS[1]) + broken))
        assert got == [pong], "a broken frame is an error, after the frames before it are delivered"


class Node(Actor):
    """Grows the part of the tree it is sent, reports its work, and stops itself on shutdown."""

    def __init__(self, name: str, log: list) -> None:
        super().__init__(name)
        self.log = log

    def receive(self, message: Message, runtime: Runtime) -> None:
        if message.topic == "grow":
            for child, below in message.body.items():
                runtime.spawn(self.name, Node(child, self.log))
                runtime.send(self.name, child, "grow", below)
        elif message.topic == "work":
            self.log.append(("work", self.name))
            runtime.send(self.name, "monitor", "done", self.name)
        elif message.topic == "shutdown":
            stopped = runtime.stop(self.name)
            runtime.send(self.name, "monitor", "stopped", stopped)

    def on_stop(self, runtime: Runtime) -> None:
        self.log.append(("stop", self.name))


PLAN = {"ingest": {"parse": {"tokenize": {}}, "fetch": {}}, "index": {"shard-0": {}, "shard-1": {}}}


@pytest.mark.skip("Part 5")
def test_spawn_tree() -> None:
    """Actors spawn children; stopping one stops its subtree, children first, and its mail is dead-lettered."""
    log: list = []
    runtime = Runtime()
    monitor = Collect("monitor")
    runtime.register(Node("pool", log))
    runtime.register(monitor)
    runtime.send("__user__", "pool", "grow", PLAN)
    assert runtime.run_until_idle() is True
    assert runtime.tree() == {"pool": PLAN, "monitor": {}}, "children spawned by handlers, grandchildren too"
    assert [list(runtime.tree()), list(runtime.tree()["pool"]), list(runtime.tree()["pool"]["ingest"])] == [
        ["pool", "monitor"],
        ["ingest", "index"],
        ["parse", "fetch"],
    ], "actors in the order they started"

    runtime.send("__user__", "tokenize", "work", None)
    runtime.send("__user__", "ingest", "shutdown", None)
    runtime.send("__user__", "parse", "work", None)
    runtime.send("__user__", "nobody", "work", None)
    runtime.send("__user__", "index", "work", None)
    runtime.send("__user__", "parse", "shutdown", None)
    assert runtime.run_until_idle() is True
    assert [(m.recipient, m.topic, reason) for m, reason in runtime.dead_letters] == [
        ("parse", "work", "stopped"),
        ("nobody", "work", "no actor 'nobody'"),
        ("parse", "shutdown", "stopped"),
    ], "mail for a stopped actor is dead-lettered as stopped when its turn comes"
    assert log == [
        ("work", "tokenize"),
        ("stop", "fetch"),
        ("stop", "tokenize"),
        ("stop", "parse"),
        ("stop", "ingest"),
        ("work", "index"),
    ], "children stop before their parent, the youngest first"
    assert monitor.got == ["tokenize", ["fetch", "tokenize", "parse", "ingest"], "index"], (
        "mail from actors that have stopped is still delivered"
    )
    assert runtime.tree() == {"pool": {"index": {"shard-0": {}, "shard-1": {}}}, "monitor": {}}, (
        "the tree holds the live actors only"
    )

    for parent, name in [("pool", "index"), ("pool", "parse"), ("ingest", "retry"), ("nowhere", "retry")]:
        with pytest.raises(ValueError):
            runtime.spawn(parent, Node(name, log))
    with pytest.raises(KeyError):
        runtime.stop("nowhere")
    assert runtime.stop("parse") == [], "stopping a stopped actor does nothing"

    log.clear()
    runtime.send("__user__", "shard-1", "shutdown", None)
    runtime.send("__user__", "pool", "shutdown", None)
    runtime.send("__user__", "fetch", "work", None)
    assert runtime.run_until_idle() is True
    assert log == [("stop", "shard-1"), ("stop", "shard-0"), ("stop", "index"), ("stop", "pool")], (
        "every actor stops once"
    )
    assert monitor.got[-2:] == [["shard-1"], ["shard-0", "index", "pool"]], "stop() names the actors it stopped"
    assert runtime.dead_letters[-1][0].recipient == "fetch" and runtime.dead_letters[-1][1] == "stopped"
    assert runtime.tree() == {"monitor": {}}
