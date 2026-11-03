import asyncio
import base64
import copy
import json
import random
import sqlite3
import struct
import time

import pytest
from agentcard.caller import ArtifactAssembler, read_report
from agentcard.cards import CardError, Choice, check_card, choose_skill, delegate, discover, sign_card, verify_card
from agentcard.delegation import caller_views
from agentcard.frames import MAX_FRAME, FrameReader, ModelError, encode_frame, stream_task
from agentcard.model import Artifact, Message, Part, Task, TaskError, data_part, file_part, text_part
from agentcard.store import TaskStore
from agentcard.writer import WRITER_CARD, WriterAgent

PAPER = (
    b"%PDF-1.7\r\n%\xe2\xe3\xcf\xd3\r\n"
    b"1 0 obj\r\n<< /Type /Catalog /Pages 2 0 R >>\r\nendobj\r\n"
    b"\x00\x01\x02\xfe\xff stream\r\n"
    b"%%EOF\r\n"
)


def paper_message(*data: dict) -> Message:
    """The lesson's request: an instruction, the paper as a file part, then any data parts."""
    return Message(
        "user",
        [
            text_part("Summarize the attached paper."),
            file_part("paper.pdf", "application/pdf", PAPER),
            *[data_part(payload) for payload in data],
        ],
    )


def fails_with_value_error(action, what: str) -> None:
    try:
        action()
    except ValueError:
        return
    pytest.fail(f"accepted {what}")


@pytest.mark.skip("Part 1")
def test_writer_lifecycle() -> None:
    """The writer reads every data part, rejects skills it doesn't have and never reopens a finished
    task; the caller gets the report back in one piece, and fast."""
    writer = WriterAgent()
    sent = writer.tasks_send(
        "draft_report",
        paper_message({"audience": "platform team"}, {"targetLength": "3 paragraphs"}, {"tone": "plain"}),
    )
    assert read_report(writer, sent.id, chunk_chars=7).decode() == (
        "# Report (3 paragraphs)\n\nSources: paper.pdf (application/pdf, 90 bytes).\n\n"
        "Topic identified, key points extracted, conclusion drafted.\n"
    ), "the caller gets the whole report"
    assert sent.history == ["submitted", "working", "completed"], "a targetLength in any data part completes the task"

    asked = writer.tasks_send("draft_report", paper_message())
    assert asked.state == "input_required", "without a targetLength the writer asks for one"
    assert asked.messages[-1] == Message("agent", [text_part("Please specify targetLength as a data part.")])
    writer.tasks_reply(asked.id, Message("user", [text_part("Any length is fine.")]))
    assert asked.state == "input_required", "a reply without a targetLength is asked again"
    writer.tasks_reply(asked.id, Message("user", [data_part({"tone": "plain"}), data_part({"targetLength": "1 page"})]))
    assert asked.history == [
        "submitted", "working", "input_required", "working", "input_required", "working", "completed",
    ], "input_required goes back to working with every reply"
    assert [m.role for m in asked.messages] == ["user", "agent", "user", "agent", "user"]

    rejected = writer.tasks_send("translate_paper", paper_message({"targetLength": "3 paragraphs"}))
    assert rejected.history == ["submitted", "rejected"], (
        "a skill the card doesn't list is rejected before any work starts"
    )
    assert rejected.artifact is None and rejected.messages[-1].role == "agent", "a rejection comes with an agent message"
    assert "translate_paper" in rejected.messages[-1].parts[0].text, "the rejection names the skill"
    renamed = WriterAgent({**WRITER_CARD, "skills": [{**WRITER_CARD["skills"][0], "id": "draft_brief"}]})
    for skill, state in (("draft_report", "rejected"), ("draft_brief", "completed")):
        assert renamed.tasks_send(skill, paper_message({"targetLength": "1 page"})).state == state, (
            "the writer serves the skills on its own card"
        )

    for finished in (sent, asked, rejected):
        before = copy.deepcopy(finished)
        with pytest.raises(TaskError):
            writer.tasks_reply(finished.id, Message("user", [data_part({"targetLength": "2 pages"})]))
        assert finished == before, "a task in a terminal state never changes"
    with pytest.raises(KeyError):
        writer.tasks_reply("task_9999", Message("user", [text_part("Hello?")]))

    assembler = ArtifactAssembler()
    for chunk, so_far in (("QUJ", b""), ("DRE", b"ABC"), ("VG", b"ABCDEF"), ("", b"ABCDEF"), ("Rw==", b"ABCDEFG")):
        assembler.add(chunk)
        assert assembler.received == so_far, "bytes are available as soon as their 4-character group is complete"
    assert assembler.finish() == b"ABCDEFG"
    corrupt = ArtifactAssembler()
    corrupt.add("QUJD")
    fails_with_value_error(lambda: (corrupt.add("R!"), corrupt.add("==")), "a group that isn't base64 once it is complete")
    fails_with_value_error(lambda: ArtifactAssembler().add("QUJD----"), "a group in base64url's alphabet")
    cut = ArtifactAssembler()
    cut.add("QUJDRA")
    fails_with_value_error(cut.finish, "an artifact that stopped inside a group")

    blob = random.Random(19).randbytes(135_000)
    encoded = base64.b64encode(blob).decode()
    chunks = [encoded[i : i + 9] for i in range(0, len(encoded), 9)]
    big = ArtifactAssembler()
    start = time.perf_counter()
    for chunk in chunks:
        big.add(chunk)
    elapsed = time.perf_counter() - start
    assert big.finish() == blob, "a long artifact comes back exactly"
    assert elapsed < 0.12, "adding a chunk must not decode everything that arrived before it again"


def stored_values(path: str) -> list:
    """Every value in every table of an SQLite file, whatever its schema."""
    db = sqlite3.connect(path)
    try:
        tables = [name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return [value for table in tables for row in db.execute(f'SELECT * FROM "{table}"') for value in row]
    finally:
        db.close()


def typed(value):
    """A JSON value with every scalar's type spelled out and every object's keys in their order."""
    if isinstance(value, dict):
        return ["object", [(key, typed(item)) for key, item in value.items()]]
    if isinstance(value, list):
        return ["array", [typed(item) for item in value]]
    return [type(value).__name__, value]


@pytest.mark.skip("Part 2")
def test_task_store_roundtrip(tmp_path) -> None:
    """Tasks survive SQLite and a reopen byte for byte and type for type, and a save is all or nothing."""
    path = str(tmp_path / "tasks.sqlite3")
    settings = {
        "zone": "eu-west",
        "pages": 3,
        "ratio": 1.0,
        "draft": True,
        "seed": 12345678901234567890,
        "weights": [1, 2.5, None, False],
        "limits": {"max": 10, "min": 0.5},
    }
    writer = WriterAgent()
    task = writer.tasks_send(
        "draft_report",
        Message(
            "user",
            [
                data_part(settings),
                text_part("Summarize the attached paper.\r\nKeep the tables.\x00"),
                file_part("论文 v2 — final.pdf", "application/pdf", PAPER),
                file_part("empty.txt", "text/plain", b""),
                text_part("Thanks!"),
            ],
        ),
    )
    for _ in range(5):
        writer.tasks_reply(task.id, Message("user", [text_part("Any length is fine.")]))
    writer.tasks_reply(task.id, Message("user", [data_part({"targetLength": "1 page"})]))
    assert (len(task.messages), task.state) == (13, "completed")

    store = TaskStore(path)
    store.save(task)
    loaded = store.load(task.id)
    assert loaded.history == task.history, "the history keeps every state in order, repeats included"
    assert loaded.messages == task.messages, "messages come back exactly, in order, with their parts in order"
    assert typed(loaded.messages[0].parts[0].data) == typed(settings), (
        "a data part keeps its keys in order and every value's type"
    )
    assert loaded == task, "a task round-trips exactly"
    with pytest.raises(KeyError):
        store.load("task_9999")
    store.close()

    reopened = TaskStore(path)
    assert reopened.load(task.id) == task, "a reopened store has every task saved before"
    assert PAPER in stored_values(path), "a file part's bytes are stored as they are, in a BLOB"

    quick = writer.tasks_send("draft_report", Message("user", [data_part({"targetLength": "2 pages"})]))
    waiting = writer.tasks_send("draft_report", Message("user", [text_part("Draft something short.")]))
    reopened.save(waiting)
    reopened.save(quick)
    assert reopened.task_ids() == ["task_0001", "task_0002", "task_0003"], "task ids come back sorted"
    assert reopened.task_ids(state="input_required") == ["task_0003"], "task_ids can filter by current state"
    writer.tasks_reply(waiting.id, Message("user", [data_part({"targetLength": "1 page"})]))
    assert reopened.load(waiting.id).state == "input_required", "load returns the task as it was saved"
    reopened.save(waiting)
    assert reopened.load(waiting.id) == waiting, "saving a task again replaces what was stored for it"
    assert reopened.task_ids(state="input_required") == [], "task_ids sees the current state"

    broken = copy.deepcopy(waiting)
    broken.messages.append(Message("user", [text_part("One more thing."), Part("image", text="cat.png")]))
    with pytest.raises(ValueError):
        reopened.save(broken)
    assert waiting.id in reopened.task_ids() and reopened.load(waiting.id) == waiting, (
        "a save that fails leaves the stored task as it was"
    )
    reopened.close()


RESEARCH_CARD = {
    "schemaVersion": "1.0",
    "name": "research-agent",
    "description": "Summarizes academic papers and drafts citations (résumés, 引用).",
    "url": "https://research.example.com/a2a",
    "version": "1.2.0",
    "skills": [
        {
            "id": "triage_question",
            "name": "Triage a question",
            "description": "Answer a short question, or say which skill should take it.",
            "inputModes": ["text", "data"],
            "outputModes": ["text"],
        },
        {
            "id": "summarize_paper",
            "name": "Summarize a paper",
            "description": "Read a paper PDF and produce a 3-paragraph summary.",
            "inputModes": ["text", "file"],
            "outputModes": ["text", "artifact"],
        },
        {
            "id": "extract_tables",
            "name": "Extract tables",
            "description": "Pull every table out of a paper PDF.",
            "inputModes": ["file"],
            "outputModes": ["artifact"],
        },
        {
            "id": "draft_citations",
            "name": "Draft citations",
            "description": "Turn a paper and a citation style into a bibliography.",
            "inputModes": ["text", "file", "data"],
            "outputModes": ["artifact"],
        },
    ],
    "capabilities": {"streaming": True, "pushNotifications": True},
}
RESEARCH_KEY = b"research-agent card key"
KEYS = {"research-2026": RESEARCH_KEY}
# The card as the research agent's own tooling signed and published it.
PUBLISHED = json.dumps(
    {
        **RESEARCH_CARD,
        "signature": {"alg": "HS256", "kid": "research-2026", "value": "x79VdMj5XbJn6oVRS5OvHksfHwdnX6UypBs8VoX--VU"},
    },
    indent=2,
    ensure_ascii=False,
)


def changed(card: dict, change) -> dict:
    card = copy.deepcopy(card)
    change(card)
    return card


def ask(*types: str) -> Message:
    sample = {
        "text": text_part("Summarize this paper."),
        "file": file_part("paper.pdf", "application/pdf", PAPER),
        "data": data_part({"style": "APA"}),
    }
    return Message("user", [sample[kind] for kind in types])


class SpyAgent:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def tasks_send(self, skill_id: str, message: Message) -> Task:
        self.sent.append(skill_id)
        return Task(f"task_{len(self.sent):04d}", skill_id)


@pytest.mark.skip("Part 3")
def test_discover_and_choose() -> None:
    """Only a signed, well-formed card is used, and a message goes to the first skill that can take it."""
    published = json.loads(PUBLISHED)
    unsigned = {key: value for key, value in published.items() if key != "signature"}
    before = copy.deepcopy(unsigned)
    assert sign_card(unsigned, RESEARCH_KEY, "research-2026") == published, (
        "the signature is an HMAC of the card's canonical JSON, as the docstring defines it"
    )
    assert unsigned == before, "sign_card leaves the card as it was"
    stale = {**unsigned, "signature": {"alg": "HS256", "kid": "research-2026", "value": "stale"}}
    assert sign_card(stale, RESEARCH_KEY, "research-2026") == published, "signing again replaces the old signature"
    assert verify_card(published, KEYS), "a card signed by its publisher verifies"
    assert verify_card(json.loads(json.dumps(published, sort_keys=True, indent=4)), KEYS), (
        "the same card in another key order and layout still verifies"
    )
    for problem, change in (
        ("a new url", lambda c: c.update(url="https://evil.example.com/a2a")),
        ("a skill that now takes data", lambda c: c["skills"][2]["inputModes"].append("data")),
        ("streaming switched off", lambda c: c["capabilities"].update(streaming=False)),
        ("an extra field", lambda c: c.update(provider="evil.example.com")),
        ("a skill removed", lambda c: c["skills"].pop()),
        ("an unknown key id", lambda c: c["signature"].update(kid="research-2025")),
        ("alg none", lambda c: c["signature"].update(alg="none")),
        ("no key id", lambda c: c["signature"].pop("kid")),
        ("no signature", lambda c: c.pop("signature")),
    ):
        assert not verify_card(changed(published, change), KEYS), f"a card with {problem} must not verify"
    assert not verify_card(published, {"research-2026": b"another key"}), "a card checked with another key must not verify"

    check_card(RESEARCH_CARD)
    check_card(WRITER_CARD)
    for problem, change in (
        ("an http url", lambda c: c.update(url="http://research.example.com/a2a")),
        ("a relative url", lambda c: c.update(url="/a2a")),
        ("a url without a host", lambda c: c.update(url="https:///a2a")),
        ("no name", lambda c: c.pop("name")),
        ("an empty description", lambda c: c.update(description="")),
        ("a version that is a number", lambda c: c.update(version=1.2)),
        ("no skills", lambda c: c.update(skills=[])),
        ("a skill without an id", lambda c: c["skills"][1].pop("id")),
        ("a skill with an empty name", lambda c: c["skills"][0].update(name="")),
        ("two skills with one id", lambda c: c["skills"][3].update(id="summarize_paper")),
        ("a skill without outputModes", lambda c: c["skills"][1].pop("outputModes")),
        ("a skill with empty inputModes", lambda c: c["skills"][0].update(inputModes=[])),
        ("a skill that takes images", lambda c: c["skills"][2]["inputModes"].append("image")),
        ("a skill that outputs files", lambda c: c["skills"][2].update(outputModes=["file"])),
        ("streaming as a string", lambda c: c["capabilities"].update(streaming="false")),
        ("pushNotifications as a number", lambda c: c["capabilities"].update(pushNotifications=1)),
        ("no capabilities", lambda c: c.pop("capabilities")),
    ):
        try:
            check_card(changed(RESEARCH_CARD, change))
        except CardError:
            continue
        pytest.fail(f"check_card accepts a card with {problem}")

    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return PUBLISHED.encode()

    card = discover(fetch, "https://research.example.com/", KEYS)
    assert fetched == ["https://research.example.com/.well-known/agent.json"]
    assert card == published, "discover returns the published card"
    for problem, body in (
        ("an unsigned card", json.dumps(unsigned)),
        ("a tampered card", json.dumps({**published, "url": "https://evil.example.com/a2a"})),
        ("a signed card with an http url", json.dumps(sign_card(
            {**unsigned, "url": "http://research.example.com/a2a"}, RESEARCH_KEY, "research-2026"
        ))),
    ):
        with pytest.raises(CardError):
            discover(lambda url: body.encode(), "https://research.example.com", KEYS)

    for types, wants, skill in (
        (("text", "file"), "artifact", "summarize_paper"),
        (("text", "file", "data"), "artifact", "draft_citations"),
        (("file",), "artifact", "summarize_paper"),
        (("file", "file"), "text", "summarize_paper"),
        (("text",), "text", "triage_question"),
        (("data", "text"), "text", "triage_question"),
        (("data", "text"), "artifact", "draft_citations"),
        (("data",), "artifact", "draft_citations"),
        (("file", "data"), "text", None),
    ):
        choice = choose_skill(card, ask(*types), wants)
        assert (choice.skill if choice else None) == skill, (
            f"{'+'.join(types)} wanting {wants}: the first skill in card order that takes every part type "
            f"and offers the output, or None"
        )
    with pytest.raises(ValueError):
        choose_skill(card, Message("user", []), "text")
    assert choose_skill(card, ask("text"), "text") == Choice("triage_question", "stream"), (
        "an agent that can stream is followed by streaming"
    )
    polled = {**card, "capabilities": {"streaming": False, "pushNotifications": True}}
    assert choose_skill(polled, ask("text"), "text") == Choice("triage_question", "poll"), (
        "an agent that can't stream is polled"
    )

    spy = SpyAgent()
    assert delegate(spy, card, ask("file", "data"), "text") is None
    assert spy.sent == [], "no task is sent when no skill fits"
    assert delegate(spy, card, ask("text", "file"), "artifact").skill == "summarize_paper"
    assert spy.sent == ["summarize_paper"]

    writer_card = sign_card(WRITER_CARD, b"writer-agent card key", "writer-2026")
    found = discover(lambda url: json.dumps(writer_card).encode(), "https://writer.example.com", {
        "writer-2026": b"writer-agent card key"
    })
    task = delegate(WriterAgent(found), found, paper_message({"targetLength": "1 page"}), "artifact")
    assert (task.skill, task.state) == ("draft_report", "completed"), "discover, choose and delegate end to end"


REPORT_PIECES = ["## 摘要\n", "", "本文提出一种多跳委托的方法。\n", "结论：可行。\n"]


def events_in(raw: bytes) -> list[dict]:
    """The test's own reading of a stream: a 4-byte big-endian length, then that many bytes of JSON."""
    events, pos = [], 0
    while pos < len(raw):
        assert len(raw) - pos >= 4, "every frame starts with a 4-byte length"
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        body = raw[pos + 4 : pos + 4 + length]
        assert len(body) == length, "a frame is a 4-byte big-endian length, then exactly that many bytes of JSON"
        events.append(json.loads(body.decode("utf-8")))
        pos += 4 + length
    return events


def frame(event: dict) -> bytes:
    """A frame the way another implementation writes it, with UTF-8 as is instead of \\u escapes."""
    body = json.dumps(event, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


async def model(pieces: list[str], pulled: list[str], closed: list[bool] | None = None):
    """A fake model that writes the report piece by piece."""
    try:
        for piece in pieces:
            pulled.append(piece)
            yield piece
            await asyncio.sleep(0)
    finally:
        if closed is not None:
            closed.append(True)


def drain(agen) -> list:
    async def run() -> list:
        return [item async for item in agen]

    return asyncio.run(run())


STREAM = [
    {"kind": "status", "taskId": "task_0050", "state": "working", "final": False},
    {"kind": "artifact", "taskId": "task_0050", "name": "report", "seq": 0, "text": "## 摘要\n"},
    {"kind": "artifact", "taskId": "task_0050", "name": "citations", "seq": 0, "text": "[1] A2A v1.0，2026 年 4 月。\n"},
    {"kind": "artifact", "taskId": "task_0050", "name": "report", "seq": 1, "text": "结论：可行。\n"},
    {"kind": "status", "taskId": "task_0050", "state": "completed", "final": True},
]


@pytest.mark.skip("Part 4")
def test_stream_frames() -> None:
    """A streamed task goes out frame by frame as it happens, and the reader takes any chunking."""
    task = Task("task_0042", "draft_report")
    frames = drain(stream_task(task, model(REPORT_PIECES, [])))
    events = events_in(b"".join(frames))
    assert events == [
        {"kind": "status", "taskId": "task_0042", "state": "working", "final": False},
        {"kind": "artifact", "taskId": "task_0042", "name": "report", "seq": 0, "text": "## 摘要\n"},
        {"kind": "artifact", "taskId": "task_0042", "name": "report", "seq": 1, "text": "本文提出一种多跳委托的方法。\n"},
        {"kind": "artifact", "taskId": "task_0042", "name": "report", "seq": 2, "text": "结论：可行。\n"},
        {"kind": "status", "taskId": "task_0042", "state": "completed", "final": True},
    ], "working, then the numbered pieces, then the final status"
    assert [events_in(f) for f in frames] == [[event] for event in events], "every frame is yielded on its own"
    assert task.history == ["submitted", "working", "completed"], "the task moves to working, then completes"
    assert task.artifact == Artifact("report", "text/markdown", [text_part("".join(REPORT_PIECES))]), (
        "the completed task keeps the whole text as its artifact"
    )

    async def first_two_frames() -> tuple[int, int]:
        pulled: list[str] = []
        agen = stream_task(Task("task_0043", "draft_report"), model(REPORT_PIECES, pulled))
        await agen.__anext__()
        at_working = len(pulled)
        await agen.__anext__()
        at_piece = len(pulled)
        await agen.aclose()
        return at_working, at_piece

    at_working, at_piece = asyncio.run(first_two_frames())
    assert at_working == 0, "the working status goes out before the model is asked for anything"
    assert at_piece == 1, "each piece goes out as soon as the model writes it"

    async def close_after(frames_read: int) -> tuple[list[str], list[bool]]:
        closed: list[bool] = []
        stopped = Task("task_0044", "draft_report")
        agen = stream_task(stopped, model(REPORT_PIECES, [], closed))
        for _ in range(frames_read):
            await agen.__anext__()
        await agen.aclose()
        return stopped.history, list(closed)

    async def close_after_final() -> tuple[str, Artifact | None, list[str]]:
        done = Task("task_0047", "draft_report")
        agen = stream_task(done, model(REPORT_PIECES, []))
        for _ in range(5):
            await agen.__anext__()
        at_final = (done.state, done.artifact)
        await agen.aclose()
        return (*at_final, done.history)

    state, kept, history = asyncio.run(close_after_final())
    assert (state, kept is not None) == ("completed", True), "the task has completed by the time its final frame goes out"
    assert history == ["submitted", "working", "completed"], "closing a stream after its final status changes nothing"

    history, closed = asyncio.run(close_after(2))
    assert closed == [True], "closing the stream closes the model's stream at once"
    assert history == ["submitted", "working", "canceled"], "a stream the caller closes cancels its task"
    assert asyncio.run(close_after(1))[0] == ["submitted", "working", "canceled"], (
        "a stream closed right after its working status cancels its task too"
    )

    async def broken_model():
        yield "## 摘要\n"
        raise ModelError("the model timed out after 30 s")

    failed = Task("task_0045", "draft_report")
    assert events_in(b"".join(drain(stream_task(failed, broken_model())))) == [
        {"kind": "status", "taskId": "task_0045", "state": "working", "final": False},
        {"kind": "artifact", "taskId": "task_0045", "name": "report", "seq": 0, "text": "## 摘要\n"},
        {
            "kind": "status",
            "taskId": "task_0045",
            "state": "failed",
            "final": True,
            "message": "the model timed out after 30 s",
        },
    ], "a model error ends the stream with a final failed status"
    assert (failed.history, failed.artifact) == (["submitted", "working", "failed"], None), (
        "a task whose model fails ends failed, without an artifact"
    )
    fails_with_value_error(
        lambda: encode_frame({"kind": "artifact", "taskId": "t", "name": "report", "seq": 0, "text": "x" * MAX_FRAME}),
        "an event over MAX_FRAME",
    )

    raw = b"".join(frame(event) for event in STREAM)
    for sizes in ([len(raw)], [1] * len(raw), [3, 0, 1, 70, 2, 0, 5, 200, 9, len(raw)]):
        reader = FrameReader()
        got, pos = [], 0
        for size in sizes:
            got += reader.feed(raw[pos : pos + size])
            pos += size
        assert got == STREAM, f"the same events whatever the chunk sizes, e.g. {sizes[:6]}"
        reader.close()
    reader = FrameReader()
    first = frame(STREAM[0])
    assert reader.feed(first[:2]) == [], "half a length is not a frame yet"
    assert reader.feed(first[2:-1]) == [], "a frame without its last byte is not a frame yet"
    assert reader.feed(first[-1:] + frame(STREAM[1])[:5]) == [STREAM[0]], (
        "a frame comes out as soon as its last byte arrives"
    )
    fails_with_value_error(reader.close, "a stream that stopped inside a frame")

    fails_with_value_error(lambda: FrameReader().feed(struct.pack(">I", MAX_FRAME + 1)), "a length over MAX_FRAME")
    largest = {"kind": "artifact", "taskId": "task_0050", "name": "report", "seq": 0, "text": ""}
    largest["text"] = "x" * (MAX_FRAME + 4 - len(frame(largest)))
    assert len(frame(largest)) == 4 + MAX_FRAME
    assert FrameReader().feed(frame(largest)) == [largest], "a frame of exactly MAX_FRAME bytes is fine"

    finished = FrameReader()
    finished.feed(raw)
    finished.close()
    fails_with_value_error(lambda: finished.feed(frame(STREAM[1])), "a frame after the final status")
    fails_with_value_error(lambda: FrameReader().feed(raw + frame(STREAM[0])), "a frame after the final status")
    gap = FrameReader()
    gap.feed(b"".join(frame(event) for event in STREAM[:2]))
    fails_with_value_error(lambda: gap.feed(frame({**STREAM[3], "seq": 2})), "a piece that skips a seq")
    repeat = FrameReader()
    repeat.feed(b"".join(frame(event) for event in STREAM[:2]))
    fails_with_value_error(lambda: repeat.feed(frame(STREAM[1])), "a piece sent twice")
    unfinished = FrameReader()
    unfinished.feed(b"".join(frame(event) for event in STREAM[:-1]))
    fails_with_value_error(unfinished.close, "a stream that stopped before its final status")

    summarized = Task("task_0046", "draft_report")
    stream = b"".join(drain(stream_task(summarized, model(REPORT_PIECES, []), artifact="summary")))
    reader, got = FrameReader(), []
    for pos in range(0, len(stream), 7):
        got += reader.feed(stream[pos : pos + 7])
    assert [event["kind"] for event in got] == ["status", "artifact", "artifact", "artifact", "status"], (
        "the reader takes back what the writer streams"
    )
    assert {event.get("name") for event in got[1:4]} == {"summary"} and summarized.artifact.name == "summary", (
        "pieces and the artifact carry the artifact name stream_task is given"
    )
    reader.close()


def note(name: str, text: str, **internal) -> dict:
    """An artifact as the agent that made it keeps it, internal fields included."""
    return {"name": name, "mimeType": "text/markdown", "parts": [{"type": "text", "text": text}], **internal}


def shown(name: str, text: str) -> dict:
    """The same artifact as a caller sees it."""
    return {"name": name, "mimeType": "text/markdown", "parts": [{"type": "text", "text": text}]}


PLAN = {
    "task": "t-coord",
    "agent": "coordinator",
    "steps": ["split the report into research and writing", "tool: calendar.lookup"],
    "artifacts": [note("brief", "Quarterly report on agent protocols.")],
    "delegates": [
        {
            "task": "t-research",
            "agent": "researcher",
            "forward": True,
            "steps": ["tool: arxiv.search('A2A')"],
            "artifacts": [note("notes", "Three papers on A2A.", source="arxiv.search")],
            "delegates": [
                {
                    "task": "t-cite",
                    "agent": "citation-finder",
                    "forward": True,
                    "steps": ["tool: crossref.lookup"],
                    "artifacts": [note("refs", "[1] A2A v1.0, April 2026.")],
                },
                {
                    "task": "t-pdf-1",
                    "agent": "pdf-reader",
                    "forward": True,
                    "artifacts": [note("figures", "Fig. 2: the task lifecycle.", source="pdf.extract")],
                    "delegates": [
                        {
                            "task": "t-ocr-1",
                            "agent": "ocr",
                            "required": False,
                            "artifacts": [note("scan", "OCR text of page 4.")],
                        }
                    ],
                },
                {
                    "task": "t-web",
                    "agent": "web-search",
                    "required": False,
                    "forward": True,
                    "fails": True,
                    "artifacts": [note("links", "Two blog posts.")],
                },
            ],
        },
        {
            "task": "t-write",
            "agent": "writer",
            "steps": ["outline", "draft"],
            "artifacts": [note("draft", "Draft of the report.")],
            "delegates": [
                {
                    "task": "t-pdf-2",
                    "agent": "pdf-reader",
                    "required": False,
                    "forward": True,
                    "artifacts": [note("figures", "Fig. 5: a delegation tree.", source="pdf.extract")],
                    "delegates": [
                        {"task": "t-ocr-2", "agent": "ocr", "artifacts": [note("scan", "OCR text of page 9.")]}
                    ],
                }
            ],
        },
    ],
}


def view(task: str, agent: str, state: str, *artifacts: dict) -> dict:
    return {"task": task, "agent": agent, "state": state, "artifacts": list(artifacts)}


@pytest.mark.skip("Part 5")
def test_delegation_views() -> None:
    """Each caller sees its own delegates' states and what they return, and nothing deeper."""
    before = copy.deepcopy(PLAN)
    figures_2 = shown("figures", "Fig. 2: the task lifecycle.")
    refs = shown("refs", "[1] A2A v1.0, April 2026.")
    views = caller_views(PLAN, max_hops=3)
    assert views.get("client") == [
        view(
            "t-coord", "coordinator", "completed",
            shown("brief", "Quarterly report on agent protocols."), shown("notes", "Three papers on A2A."), refs, figures_2,
        )
    ], "a caller sees the task's own artifacts, then what it forwards, and no internal fields"
    assert views.get("t-pdf-1") == [view("t-ocr-1", "ocr", "rejected")], "a task past max_hops is rejected"
    assert views.get("t-pdf-2") == [view("t-ocr-2", "ocr", "rejected")], "a task past max_hops is rejected"
    assert views.get("t-write") == [view("t-pdf-2", "pdf-reader", "failed")], (
        "a task fails when a delegate it requires doesn't complete"
    )
    assert views.get("t-research") == [
        view("t-cite", "citation-finder", "completed", refs),
        view("t-pdf-1", "pdf-reader", "completed", figures_2),
        view("t-web", "web-search", "failed"),
    ], "a delegate that fails returns nothing, and an optional one doesn't fail its caller"
    assert views.get("t-coord") == [
        view("t-research", "researcher", "completed", shown("notes", "Three papers on A2A."), refs, figures_2),
        view("t-write", "writer", "completed", shown("draft", "Draft of the report.")),
    ], "artifacts travel up only through tasks that forward them, in delegate order"
    assert set(views) == {"client", "t-coord", "t-research", "t-pdf-1", "t-write", "t-pdf-2"}, (
        "one entry per task that ran and delegated something, keyed by task id"
    )

    assert caller_views(PLAN, max_hops=1) == {
        "client": [view("t-coord", "coordinator", "failed")],
        "t-coord": [view("t-research", "researcher", "rejected"), view("t-write", "writer", "rejected")],
    }, "the client's own delegation is hop 1, and a rejected task never runs"
    deep = caller_views(PLAN, max_hops=4)
    assert deep.get("t-pdf-2") == [view("t-ocr-2", "ocr", "completed", shown("scan", "OCR text of page 9."))]
    assert deep.get("t-coord", [None, None])[1] == view(
        "t-write", "writer", "completed",
        shown("draft", "Draft of the report."), shown("figures", "Fig. 5: a delegation tree."),
    ), "a forwarded delegate's artifacts become its caller's"
    assert deep.get("client") == views["client"], "the client only sees what reaches it through forwarding"

    failing = changed(PLAN, lambda plan: plan.update(fails=True))
    on_its_own = caller_views(failing, max_hops=3)
    assert on_its_own.get("client") == [view("t-coord", "coordinator", "failed")], (
        "a task whose own work fails returns nothing"
    )
    assert on_its_own.get("t-coord") == views["t-coord"], "its delegates still ran"

    with pytest.raises(ValueError):
        caller_views(PLAN, max_hops=0)
    reused = changed(PLAN, lambda plan: plan["delegates"][1]["delegates"][0].update(task="t-pdf-1"))
    with pytest.raises(ValueError):
        caller_views(reused, max_hops=3)
    reused_deep = changed(PLAN, lambda plan: plan["delegates"][1]["delegates"][0]["delegates"][0].update(task="t-ocr-1"))
    with pytest.raises(ValueError):
        caller_views(reused_deep, max_hops=3)
    assert PLAN == before, "caller_views leaves the plan as it was"
