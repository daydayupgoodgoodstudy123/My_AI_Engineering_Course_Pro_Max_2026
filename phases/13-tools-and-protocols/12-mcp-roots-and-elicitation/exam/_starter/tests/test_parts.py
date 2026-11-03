import asyncio
import base64
import json
import sqlite3
import threading
import time

import pytest
from scopegate.client import drive_url_elicitation
from scopegate.connect import ReportConnector
from scopegate.grants import Grant, GrantTree, WorkspaceList
from scopegate.notedb import NoteDB
from scopegate.notes import Note, NoteBook
from scopegate.protocol import McpError, request_meta, supports_form_elicitation
from scopegate.replay import ReplayStore
from scopegate.scope import uri_within_workspace
from scopegate.server import NotesServer

WS = "file:///work/notes"
FORM = {"elicitation": {"form": {}}}


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def tools_call(server, request_id, title, *, principal="alice", workspace=WS, state=None, responses=None) -> dict:
    """One notes_delete call; a retry passes the requestState and the inputResponses back."""
    params = {
        "name": "notes_delete",
        "arguments": {"workspaceUri": workspace, "title": title},
        "_meta": request_meta(FORM),
    }
    if state is not None:
        params["requestState"] = state
        params["inputResponses"] = responses
    request = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}
    return server.dispatch(request, principal=principal)


def accept(note_id: str) -> dict:
    return {"delete_choice": {"action": "accept", "content": {"note_id": note_id, "confirm": True}}}


def enum_of(result: dict) -> list:
    return result["inputRequests"]["delete_choice"]["params"]["requestedSchema"]["properties"]["note_id"]["enum"]


@pytest.mark.skip("Part 1")
def test_scope_and_replay() -> None:
    """Targets stay inside the workspace, forms go only where declared, and claims stay cheap."""
    book = NoteBook(
        [
            Note("note-1", "Q3 report", "file:///work/notes/q3-report.md"),
            Note("note-2", "Q3 report", "file:///work/notes-evil/q3-report.md"),
            Note("note-3", "q3 REPORT draft", "file:///work/notes/drafts/q3.md"),
            Note("note-4", "Q4 plan", "file:///work/notes/q4-plan.md"),
        ]
    )
    assert [note.note_id for note in book.matching(WS, "q3 report")] == ["note-1", "note-3"], (
        "only notes inside the workspace are candidates"
    )
    for hostile in (
        "file:///work/notes/%2e%2e/private.md",
        "file:///work/notes%2f..%2fprivate.md",
        "file:///work/notes/drafts/%2E%2E/%2e%2e/private.md",
    ):
        assert not uri_within_workspace(WS, hostile), f"{hostile} leaves the workspace once it is decoded"
    for inside in (
        WS,
        WS + "/",
        "file:///work/notes/drafts/../q4-plan.md",
        "file:///work/notes/q3%20plan.md",
        "file:///work/notes/%252e%252e/raw.md",
    ):
        assert uri_within_workspace(WS, inside), f"{inside} is inside the workspace: decode once, then normalize"
    for outside in (
        "file://nas/work/notes/q3.md",
        "file:///work/notes/q3.md?raw=1",
        "https://example.com/work/notes/q3.md",
        "file:///work",
    ):
        assert not uri_within_workspace(WS, outside), f"{outside} is outside the workspace"
    assert uri_within_workspace("file:///", "file:///etc/hosts"), "everything is inside the root workspace"

    assert not supports_form_elicitation({"elicitation": {"url": {}}}), "a URL-only client does not support form mode"
    for capabilities in ({"elicitation": {}}, FORM, {"elicitation": {"form": {}, "url": {}}}):
        assert supports_form_elicitation(capabilities), f"{capabilities} supports form mode"
    for capabilities in ({}, {"sampling": {}}, {"elicitation": None}):
        assert not supports_form_elicitation(capabilities), f"{capabilities} does not support form mode"

    clock = Clock(1000.0)
    store = ReplayStore(max_entries=2, clock=clock)
    ran: list[str] = []

    def claim(nonce: str, expires_at: float, operation=None) -> str:
        try:
            store.claim_and_consume(nonce, expires_at=expires_at, operation=operation or (lambda: ran.append(nonce)))
        except McpError as exc:
            return exc.message
        return "claimed"

    assert [claim("late", 1450.0), claim("early", 1300.0)] == ["claimed", "claimed"]
    assert [claim("third", 1500.0), claim("late", 1450.0)] == [
        "replay protection capacity exhausted",
        "requestState was already consumed",
    ], "a full store refuses new nonces and never forgets a live one"
    clock.now = 1300.0
    assert [claim("third", 1500.0), claim("late", 1450.0), claim("early", 1300.0)] == [
        "claimed",
        "requestState was already consumed",
        "requestState expired",
    ], "a nonce frees its slot when its state expires, whatever order it was claimed in"
    clock.now = 1450.0

    def gone() -> None:
        raise McpError(-32602, "selected note no longer exists")

    assert [claim("retry", 1600.0, gone), claim("retry", 1600.0)] == ["selected note no longer exists", "claimed"], (
        "a claim whose operation fails is not consumed"
    )
    assert ran == ["late", "early", "third", "retry"]

    clock.now = 5000.0
    busy = ReplayStore(max_entries=50_000, clock=clock)
    start = time.perf_counter()
    for i in range(10_000):
        clock.now = 5000.0 + i * 0.01
        busy.claim_and_consume(f"nonce-{i}", expires_at=clock.now + 300.0, operation=lambda: None)
    assert time.perf_counter() - start < 0.12, "claiming a nonce must not rescan every stored nonce"


@pytest.mark.skip("Part 2")
def test_replay_db_roundtrip(tmp_path) -> None:
    """Server processes share one SQLite file: each nonce is claimed once, together with its deletion."""
    path = str(tmp_path / "scopegate.sqlite3")
    clock = Clock(990.0)
    notes = [
        Note("note-1", "TPS report 2023", "file:///work/notes/tps-2023.md"),
        Note("note-2", "TPS report (shared)", "file:///work/notes-shared/tps.md"),
        Note("note-3", "TPS report 2024", "file:///work/notes/tps-2024.md"),
        Note("note-4", "TPS report 2025", "file:///work/notes/2025%20drafts/tps.md"),
        Note("note-5", "Q3 plan", "file:///work/notes/q3.md"),
        Note("note-6", "Q4 plan", "file:///work/notes/q4.md"),
    ]
    first = NoteDB(path, clock=clock)
    second = NoteDB(path, clock=clock)  # another server process, with its own connection
    for note in notes:
        first.add_note(note)
    assert second.notes() == notes

    def attempt(db: NoteDB, nonce: str, expires_at: float, note_id: str | None = None) -> str:
        try:
            if note_id is None:
                db.claim(nonce, expires_at=expires_at)
            else:
                db.claim_and_delete(nonce, expires_at=expires_at, note_id=note_id, workspace_uri=WS)
        except McpError as exc:
            return exc.message
        return "ok"

    assert attempt(first, "n-1", 1290.123456789, "note-1") == "ok"
    assert second.note("note-1") is None and "n-1" in second.claims(), (
        "a claim and its deletion reach the other process as soon as they return"
    )
    assert second.claims() == {"n-1": 1290.123456789}, "a claim keeps its expiry exactly"
    assert attempt(second, "n-1", 1290.123456789, "note-3") == "requestState was already consumed", (
        "a confirmation is claimed once across processes"
    )
    assert attempt(second, "n-1", 1290.123456789, "note-1") == "requestState was already consumed", (
        "the nonce is claimed first, then the note is re-checked"
    )
    assert second.note("note-3") == notes[2], "a replayed confirmation deletes nothing"

    assert attempt(second, "n-2", 1290.25, "note-1") == "selected note no longer exists", (
        "the live note is checked inside the claim"
    )
    assert "n-2" not in first.claims(), "a refused deletion rolls its claim back, so the confirmation can still be used"
    assert attempt(second, "n-2", 1290.25, "note-2") == "selected note is outside workspace", (
        "the live note must still be inside the workspace"
    )
    assert "n-2" not in first.claims() and first.note("note-2") == notes[1]
    assert attempt(first, "n-2", 1290.25, "note-3") == "ok"

    assert attempt(first, "n-3", 1000.5) == "ok"  # an explicit decline: consumed, nothing deleted
    assert "n-3" in second.claims(), "a decline reaches the other process as soon as it returns"
    assert attempt(second, "n-3", 1000.5, "note-4") == "requestState was already consumed", (
        "a declined confirmation cannot delete later"
    )
    assert [note.note_id for note in second.notes()] == ["note-2", "note-4", "note-5", "note-6"]
    assert [attempt(second, "n-4", 990.0, "note-4"), attempt(first, "n-4", 990.0)] == [
        "requestState expired",
        "requestState expired",
    ], "a state that expires now is expired"
    assert "n-4" not in second.claims() and second.note("note-4") == notes[3], "an expired state claims nothing"

    blocker = sqlite3.connect(path, isolation_level=None)
    opened, go = threading.Barrier(3, timeout=5), threading.Barrier(3, timeout=5)
    outcomes: dict[str, str] = {}

    def retry(note_id: str) -> None:
        db = NoteDB(path, clock=clock)
        try:
            opened.wait()
            go.wait()
            outcomes[note_id] = attempt(db, "n-race", 1290.0, note_id)
        except Exception as exc:  # report anything, not just McpError, to the main thread
            outcomes[note_id] = repr(exc)
        finally:
            db.close()

    workers = [threading.Thread(target=retry, args=(note_id,), daemon=True) for note_id in ("note-5", "note-6")]
    for worker in workers:
        worker.start()
    opened.wait()
    blocker.execute("BEGIN IMMEDIATE")  # another writer holds the file while both retries arrive
    go.wait()
    time.sleep(0.2)
    blocker.execute("ROLLBACK")
    for worker in workers:
        worker.join(timeout=10)
    blocker.close()
    assert sorted(outcomes.values()) == ["ok", "requestState was already consumed"], (
        f"of two simultaneous retries exactly one deletes, got {outcomes}"
    )
    assert sum(first.note(note_id) is not None for note_id in ("note-5", "note-6")) == 1

    assert [attempt(first, "n-5", 999.5), attempt(first, "n-6", 1000.0)] == ["ok", "ok"]
    clock.now = 1000.0
    assert first.prune() == 2, "prune drops exactly the claims whose state has expired"
    assert attempt(second, "n-3", 1000.5, "note-4") == "requestState was already consumed", (
        "a claim whose state is still valid survives pruning"
    )

    first.close()
    second.close()
    reopened = NoteDB(path, clock=clock)
    assert reopened.claims() == {"n-1": 1290.123456789, "n-2": 1290.25, "n-3": 1000.5, "n-race": 1290.0}, (
        "claims come back exactly after a restart"
    )
    assert attempt(reopened, "n-2", 1290.25, "note-4") == "requestState was already consumed", (
        "a used confirmation stays used after a restart"
    )
    assert attempt(reopened, "n-4", 1290.0, "note-4") == "ok", "an unused confirmation still works after a restart"
    assert reopened.note("note-4") is None
    reopened.close()


@pytest.mark.skip("Part 3")
def test_delete_confirmation() -> None:
    """notes_delete asks which note through a form, then acts on accept, decline and cancel exactly once."""
    clock = Clock(1_000_000.0)
    book = NoteBook(
        [
            Note("note-3", "TPS report 2023", "file:///work/notes/tps-2023.md"),
            Note("note-7", "TPS report 2024", "file:///work/notes/tps-2024.md"),
            Note("note-14", "TPS report 2025", "file:///work/notes/drafts/tps-2025.md"),
            Note("note-21", "TPS report (shared)", "file:///work/notes-shared/tps.md"),
            Note("note-99", "shopping list", "file:///work/notes/shopping.md"),
        ]
    )
    grants = WorkspaceList({"alice": [WS]})
    replay = ReplayStore(clock=clock)
    server = NotesServer(book, grants, replay=replay, clock=clock)
    twin = NotesServer(book, grants, replay=replay, clock=clock)  # another instance behind the load balancer

    first = tools_call(server, 1, "tps REPORT")["result"]
    assert first["resultType"] == "input_required", "notes whose title contains the title, in any case, are offered"
    assert first["inputRequests"] == {
        "delete_choice": {
            "method": "elicitation/create",
            "params": {
                "mode": "form",
                "message": "Choose one matching note and confirm deletion.",
                "requestedSchema": {
                    "type": "object",
                    "properties": {
                        "note_id": {"type": "string", "enum": ["note-3", "note-7", "note-14"]},
                        "confirm": {"type": "boolean"},
                    },
                    "required": ["note_id", "confirm"],
                },
            },
        }
    }, "one flat form whose enum lists the matching notes inside the workspace"
    state = first["requestState"]
    for title in ("budget", "shared"):
        result = tools_call(server, 2, title).get("result", {})
        assert result.get("resultType") == "complete" and result.get("isError") is True, (
            "no candidate in the workspace is a tool error, and notes outside it stay hidden"
        )
        assert result["content"] == [{"type": "text", "text": "no match in authorized workspace"}]

    for answer in (
        {"action": "accept"},
        {"action": "accept", "content": None},
        {"action": "accept", "content": {"note_id": "note-7"}},
        {"action": "accept", "content": {"note_id": "note-7", "confirm": "true"}},
        {"action": "accept", "content": {"note_id": "note-7", "confirm": 1}},
        {"action": "accept", "content": {"note_id": "note-7", "confirm": False}},
        {"action": "accept", "content": {"note_id": "note-99", "confirm": True}},
        {"action": "accept", "content": {"note_id": ["note-7"], "confirm": True}},
        {"action": "approve", "content": {"note_id": "note-7", "confirm": True}},
        {"content": {"note_id": "note-7", "confirm": True}},
    ):
        reply = tools_call(server, 3, "tps REPORT", state=state, responses={"delete_choice": answer})
        assert reply.get("error", {}).get("code") == -32602, f"the server checks the answer itself: {answer}"
    body, signature = state.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["candidateIds"].append("note-99")
    forged = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    forged_state = f"{forged.decode().rstrip('=')}.{signature}"
    reply = tools_call(server, 4, "tps REPORT", state=forged_state, responses=accept("note-99"))
    assert reply.get("error", {}).get("code") == -32602, "the candidate list is signed: a client cannot add to it"
    for responses in (None, {}):
        reply = tools_call(server, 4, "tps REPORT", state=state, responses=responses)
        assert reply.get("error", {}).get("code") == -32602, f"inputResponses {responses!r} is not an answer"
    cancelled = tools_call(server, 5, "tps REPORT", state=state, responses={"delete_choice": {"action": "cancel"}})
    result = cancelled.get("result", {})
    assert (result.get("resultType"), result.get("isError"), result.get("structuredContent")) == (
        "complete",
        False,
        {"deleted": False},
    ), "a cancel is a complete, non-error result"
    assert len(book.all()) == 5, "invalid answers and a cancel delete nothing"

    book.move("note-7", "file:///work/notes/%2e%2e/outbox/tps-2024.md")
    book.add(Note("note-15", "TPS report 2026", "file:///work/notes/tps-2026.md"))
    added = tools_call(server, 6, "tps REPORT", state=state, responses=accept("note-15"))
    assert added.get("error", {}).get("code") == -32602, "only a note the user was shown can be chosen"
    moved = tools_call(server, 7, "tps REPORT", state=state, responses=accept("note-7"))
    assert moved.get("error", {}).get("message") == "selected note is outside workspace", (
        f"the live note is checked again just before the deletion, got {moved.get('error') or moved.get('result')}"
    )
    assert book.get("note-7") is not None and book.get("note-15") is not None

    deleted = tools_call(server, 8, "tps REPORT", state=state, responses=accept("note-14")).get("result", {})
    assert (deleted.get("isError"), deleted.get("structuredContent")) == (
        False,
        {"deleted": True, "noteId": "note-14"},
    ), "after invalid answers and a cancel the same state still confirms a deletion"
    assert book.get("note-14") is None
    replayed = tools_call(twin, 9, "tps REPORT", state=state, responses=accept("note-3"))
    assert replayed.get("error", {}).get("message") == "requestState was already consumed", (
        "a confirmation works once, whichever server instance gets the retry"
    )
    assert book.get("note-3") is not None, "a refused replay deletes nothing"

    second = tools_call(twin, 10, "TPS report 20")["result"]
    assert enum_of(second) == ["note-3", "note-15"]
    decline = {"delete_choice": {"action": "decline"}}
    declined = tools_call(server, 11, "TPS report 20", state=second["requestState"], responses=decline)
    result = declined.get("result", {})
    assert (result.get("resultType"), result.get("isError"), result.get("structuredContent")) == (
        "complete",
        False,
        {"deleted": False},
    ), "a decline is a complete, non-error refusal, not a new prompt"
    late = tools_call(twin, 12, "TPS report 20", state=second["requestState"], responses=accept("note-3"))
    assert late.get("error", {}).get("message") == "requestState was already consumed", "a decline is final"
    assert [note.note_id for note in book.all()] == ["note-3", "note-7", "note-21", "note-99", "note-15"]

    third = tools_call(server, 13, "tps REPORT")["result"]
    assert enum_of(third) == ["note-3", "note-15"]
    done = tools_call(server, 14, "tps REPORT", state=third["requestState"], responses=accept("note-15"))
    assert done.get("result", {}).get("structuredContent") == {"deleted": True, "noteId": "note-15"}, (
        f"every prompt carries a fresh nonce, got {done.get('error')}"
    )
    fourth = tools_call(server, 15, "TPS")["result"]
    assert enum_of(fourth) == ["note-3"]
    book.delete("note-3")  # someone else deletes it while the form is open
    vanished = tools_call(server, 16, "TPS", state=fourth["requestState"], responses=accept("note-3"))
    assert vanished.get("error", {}).get("message") == "selected note no longer exists", (
        "a note deleted while the form was open cannot be confirmed"
    )

    fifth = tools_call(server, 17, "shopping")["result"]
    clock.now += 300.0
    expired = tools_call(server, 18, "shopping", state=fifth["requestState"], responses=accept("note-99"))
    assert expired.get("error", {}).get("message") == "requestState expired", "a confirmation expires with its state"
    assert book.get("note-99") is not None


def connect_request(capabilities=None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "reports_connect",
            "arguments": {},
            "_meta": request_meta(capabilities or {"elicitation": {"url": {}}}),
        },
    }


class Browser:
    """What the user does outside the MCP client: consent prompts, opened tabs, the connect page."""

    def __init__(self, connector: ReportConnector, answer: str) -> None:
        self.connector = connector
        self.answer = answer
        self.asked: list[tuple[str, str, list[str]]] = []
        self.opened: list[str] = []
        self.pulled = 0
        self.callbacks: list[bool] = []

    def consent(self, url: str, message: str) -> str:
        self.asked.append((url, message, list(self.opened)))
        return self.answer

    async def ticks(self, visits: list[str]):
        """Moments the client may retry. Before a tick, the named user may finish the flow in the browser."""
        for user in visits:
            self.connector.clock.now += 30.0
            if user:
                flow_id = self.opened[-1].rsplit("flow=", 1)[-1] if self.opened else ""
                self.callbacks.append(self.connector.browser_callback(flow_id, user))
            self.pulled += 1
            yield "the user is back"


def drive(connector: ReportConnector, principal: str, browser: Browser, capabilities=None, visits=("", "")):
    sent: list[dict] = []
    replies: list[dict] = []

    async def send(request: dict) -> dict:
        sent.append(request)
        if len(sent) > 12:
            raise RuntimeError("the client keeps retrying")
        reply = connector.dispatch(json.loads(json.dumps(request)), principal=principal)
        replies.append(reply)
        return reply

    async def run() -> tuple[list[str], list[int]]:
        lines, pulled = [], []
        agen = drive_url_elicitation(
            send,
            connect_request(capabilities),
            consent=browser.consent,
            open_url=browser.opened.append,
            ticks=browser.ticks(list(visits)),
        )
        async for line in agen:
            lines.append(line)
            pulled.append(browser.pulled)
        return lines, pulled

    lines, pulled = asyncio.run(run())
    text = "".join(lines)
    assert not text or text.endswith("\n"), "every line ends with a newline"
    for request, previous in zip(sent[1:], replies):
        assert request["params"].get("requestState") == previous.get("result", {}).get("requestState"), (
            "a retry echoes the requestState of the latest input_required result"
        )
    return [json.loads(line) for line in text.splitlines()], pulled, sent


@pytest.mark.skip("Part 4")
def test_url_mode_flow() -> None:
    """URL mode: consent before opening, accept is not completion, retry until the server completes."""
    flow_ids = iter(["flow-a", "flow-b", "flow-c", "flow-d", "flow-e"])
    connector = ReportConnector(clock=Clock(5000.0), new_flow_id=flow_ids.__next__)
    page = "https://mcp.example.com/connect/report-service?flow="
    message = "Connect the report service to continue."

    started = connector.dispatch(connect_request(), principal="dave")["result"]
    assert started["inputRequests"]["connect"]["params"] == {"mode": "url", "message": message, "url": page + "flow-a"}
    finished = [
        connector.browser_callback("flow-a", "mallory"),
        connector.browser_callback("flow-zzz", "dave"),
        connector.browser_callback("flow-a", "dave"),
        connector.browser_callback("flow-a", "dave"),
    ]
    assert finished == [False, False, True, False], (
        "only the principal who started a pending flow can finish it in the browser, and only once"
    )

    browser = Browser(connector, "accept")
    events, pulled, sent = drive(connector, "alice", browser, visits=["", "mallory", "alice", "", ""])
    assert events == [
        {"event": "show_url", "id": 1, "url": page + "flow-b", "message": message},
        {"event": "open", "url": page + "flow-b"},
        {"event": "retry", "id": 2, "action": "accept"},
        {"event": "retry", "id": 3, "action": "accept"},
        {"event": "retry", "id": 4, "action": "accept"},
        {"event": "complete", "id": 4},
    ], "accept only means the user agreed to open the URL: keep retrying until the server completes"
    assert browser.callbacks == [False, True]
    assert browser.asked == [(page + "flow-b", message, [])] and browser.opened == [page + "flow-b"], (
        "ask once, with the full URL, and open it only after the user agrees"
    )
    assert pulled == [0, 0, 1, 2, 3, 3], "write each line as soon as its action happens, and stop once complete"
    assert all(request["params"]["inputResponses"] == {"connect": {"action": "accept"}} for request in sent[1:]), (
        "a URL-mode answer carries no content"
    )

    again = Browser(connector, "accept")
    events, pulled, _ = drive(connector, "alice", again)
    assert events == [{"event": "complete", "id": 1}] and again.asked == [] and pulled == [0], (
        "a connected principal is not asked again"
    )

    refusing = Browser(connector, "decline")
    events, pulled, sent = drive(connector, "bob", refusing)
    assert events == [
        {"event": "show_url", "id": 1, "url": page + "flow-c", "message": message},
        {"event": "retry", "id": 2, "action": "decline"},
        {"event": "refused", "id": 2, "action": "decline"},
    ], "a decline is sent once and ends the flow"
    assert refusing.opened == [] and refusing.pulled == 0, "a declined URL is never opened, and nothing waits after it"
    assert connector.browser_callback("flow-c", "bob") is False, "a declined flow cannot be finished later"

    dismissing = Browser(connector, "cancel")
    events, pulled, _ = drive(connector, "erin", dismissing)
    assert [event["action"] for event in events[1:]] == ["cancel", "cancel"] and dismissing.opened == [], (
        "a cancel is passed on as a cancel"
    )

    waiting = Browser(connector, "accept")
    events, pulled, _ = drive(connector, "frank", waiting, visits=["", ""])
    assert [event["event"] for event in events] == ["show_url", "open", "retry", "retry"] and pulled == [0, 0, 1, 2], (
        "when the ticks run out before the flow completes, stop without a complete line"
    )

    with pytest.raises(McpError) as caught:
        drive(connector, "carol", Browser(connector, "accept"), capabilities={"elicitation": {}})
    assert (caught.value.code, caught.value.data) == (-32021, {"requiredCapabilities": {"elicitation": {"url": {}}}}), (
        "an error response raises McpError"
    )


@pytest.mark.skip("Part 5")
def test_nested_grants() -> None:
    """The most specific workspace decides, deny wins on the same workspace, and nothing ungranted is allowed."""
    grants = [
        Grant("alice", "file:///work", "read"),
        Grant("alice", "file:///work/notes/", "delete"),
        Grant("alice", "file:///work/notes/archive", "deny"),
        Grant("alice", "file:///work/notes/archive/keep", "delete"),
        Grant("alice", "file:///work/notes/%70rivate", "deny"),
        Grant("alice", "file:///work/notes/team", "read"),
        Grant("alice", "file:///work/notes/team", "delete"),
        Grant("alice", "file:///work/notes/shared", "delete"),
        Grant("alice", "file:///work/notes/./shared", "deny"),
        Grant("bob", "file:///work/notes/archive", "delete"),
        Grant("bob", "file:///work/notes/q4", "read"),
        Grant("dave", "file:///", "read"),
    ]
    cases = [
        ("alice", "read", "file:///work/plan.md", True),
        ("alice", "delete", "file:///work/plan.md", False),
        ("alice", "delete", "file:///work/notes", True),
        ("alice", "delete", "file:///work/notes/q3.md", True),
        ("alice", "read", "file:///work/notes/q3.md", True),
        ("alice", "read", "file:///work/notes/archive/2019.md", False),
        ("alice", "delete", "file:///work/notes/archive/keep/2019.md", True),
        ("alice", "delete", "file:///work/notes/%61rchive/2019.md", False),
        ("alice", "delete", "file:///work/notes/archive%2F2019.md", False),
        ("alice", "delete", "file:///work/notes/archive/../q3.md", True),
        ("alice", "delete", "file:///work/notes/%2e%2e/plan.md", False),
        ("alice", "delete", "file:///work/notes/private/diary.md", False),
        ("alice", "delete", "file:///work/notes-evil/q3.md", False),
        ("alice", "read", "file:///work/notes-evil/q3.md", True),
        ("alice", "delete", "file:///work/notes/team/t.md", True),
        ("alice", "read", "file:///work/notes/shared/s.md", False),
        ("alice", "delete", "file:///work/notes/q4/plan.md", True),
        ("alice", "read", "file:///home/alice/todo.md", False),
        ("alice", "read", "file://nas/work/notes/q3.md", False),
        ("alice", "read", "file:///work/notes/q3.md?raw=1", False),
        ("bob", "delete", "file:///work/notes/archive/2019.md", True),
        ("bob", "read", "file:///work/notes/q3.md", False),
        ("bob", "delete", "file:///work/notes/q4/plan.md", False),
        ("carol", "read", "file:///work/notes/q3.md", False),
        ("dave", "read", "file:///etc/hosts", True),
        ("dave", "delete", "file:///work/notes/q3.md", False),
    ]
    for tree in (GrantTree(grants), GrantTree(reversed(grants))):
        for principal, action, uri, expected in cases:
            assert tree.allowed(principal, uri, action) is expected, (
                f"{principal} {'may' if expected else 'may not'} {action} {uri}"
            )
    for bad in (
        Grant("alice", WS, "write"),
        Grant("alice", "https://example.com/notes", "read"),
        Grant("alice", "file:///work?x=1", "read"),
    ):
        with pytest.raises(ValueError):
            GrantTree([bad])
    tree = GrantTree(grants)
    with pytest.raises(ValueError):
        tree.allowed("alice", "file:///work/notes/q3.md", "write")

    clock = Clock(1_000_000.0)
    book = NoteBook(
        [
            Note("note-1", "report 2024", "file:///work/notes/report-2024.md"),
            Note("note-2", "report 2019", "file:///work/notes/archive/report-2019.md"),
            Note("note-3", "report 2018", "file:///work/notes/archive/keep/report-2018.md"),
            Note("note-4", "report draft", "file:///work/notes/shared/report.md"),
        ]
    )
    server = NotesServer(book, tree, replay=ReplayStore(clock=clock), clock=clock)
    offered = tools_call(server, 1, "report")["result"]
    assert enum_of(offered) == ["note-1", "note-3"], "the form offers only notes the principal may delete"
    denied = tools_call(server, 2, "report", workspace="file:///work")
    assert denied.get("error", {}).get("message") == "workspace is not authorized", "read access is not enough to delete"
    server.grants = GrantTree([*grants, Grant("alice", "file:///work/notes/archive/keep", "deny")])
    revoked = tools_call(server, 3, "report", state=offered["requestState"], responses=accept("note-3"))
    assert revoked.get("error", {}).get("message") == "selected note is not authorized", (
        "authorization is checked again just before the deletion"
    )
    assert book.get("note-3") is not None
