import asyncio
import dataclasses
import json
import os
import re
import threading
import time
from pathlib import Path

import pytest
from orchestra.budget import plan_hierarchy
from orchestra.routing import Route, route
from orchestra.rpc import ToolCall, ToolResult, supervise
from orchestra.supervisor import ESCALATE, Outcome, Supervisor, Worker
from orchestra.topology import INHERIT, TeamSpec, Topology, WorkerSpec, load_topology, save_topology


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class KeywordRouter:
    """Stands in for the routing LLM.

    It reads the member names off the prompt and picks the first member, in prompt order, that
    has one of its keywords in the task. Like a real model, it is loose about the reply's format.
    """

    def __init__(self, keywords: dict[str, list[str]]) -> None:
        self.keywords = keywords
        self.calls = 0
        self._read: dict[str, dict[str, tuple[int, str]]] = {}

    def __call__(self, prompt: str, task: str) -> str:
        self.calls += 1
        index = self._read.get(prompt)
        if index is None:
            index = {}
            header, *lines = prompt.rstrip("\n").split("\n")
            for position, line in enumerate(lines):
                assert line.startswith("- ") and ": " in line, f"prompt line is not a member: {line!r}"
                name = line[2:].split(": ", 1)[0]
                for keyword in self.keywords.get(name, ()):
                    index.setdefault(keyword, (position, name))
            self._read[prompt] = index
        hits = [index[w] for w in words(task) if w in index]
        return f"  {min(hits)[1]}\n" if hits else "none"


def answer(prefix: str):
    return lambda task: f"{prefix}: {task[:30]}"


def front_desk(router: KeywordRouter) -> Supervisor:
    ops = Supervisor("customer_ops", "Customer operations.\nRefunds, crashes and bug reports.", router)
    ops.register(Worker("refund", "Refunds for paid invoices", answer("refund handled")))
    ops.register(Worker("bug", "Bug triage:\n  crashes, errors,\n  stack traces", answer("bug logged")))
    commercial = Supervisor("commercial", "Pricing and quotes", router)
    commercial.register(Worker("sales", "Quotes and volume pricing", answer("quote sent")))
    desk = Supervisor("desk", "Front desk", router)
    desk.register(ops)
    desk.register(commercial)
    return desk


DESK_KEYWORDS = {
    "customer_ops": ["refund", "crashes", "bug", "invoice"],
    "commercial": ["pricing", "quote"],
    "refund": ["refund"],
    "bug": ["crashes", "bug"],
    "sales": ["pricing", "quote"],
}


@pytest.mark.skip("Part 1")
def test_supervisor_routing() -> None:
    """Supervisors send each task to the member the router names, escalate the rest, and stay fast."""
    desk = front_desk(KeywordRouter(DESK_KEYWORDS))
    crash = desk.run("the CLI crashes on ctrl-c")
    assert crash.worker == "bug", "the task goes to the member the router names"
    assert crash == Outcome("bug", ("desk", "customer_ops", "bug"), "bug logged: the CLI crashes on ctrl-c", 3), (
        "the path starts at the supervisor that got the task; every routing decision and worker call is one op"
    )
    assert desk.run("do you offer volume pricing?") == Outcome(
        "sales", ("desk", "commercial", "sales"), "quote sent: do you offer volume pricing?", 3
    ), "the task goes to the member the router names"
    assert desk.run("my parcel never arrived") == Outcome(ESCALATE, ("desk",), None, 1), (
        "a task no member fits goes to a human"
    )
    assert desk.run("a copy of invoice 4711, please") == Outcome(
        ESCALATE, ("desk", "customer_ops"), None, 2
    ), "a task no member fits goes to a human"
    stray = Supervisor("commercial", "Pricing and quotes", lambda prompt, task: "refund")
    stray.register(Worker("sales", "Quotes and volume pricing", answer("quote sent")))
    assert stray.run("refund my last quote") == Outcome(ESCALATE, ("commercial",), None, 1), (
        "a reply that names no member escalates, even one that names another team's worker"
    )
    assert desk.members["customer_ops"].prompt() == (
        "customer_ops: pick the member that should handle the task, or reply none.\n"
        "- refund: Refunds for paid invoices\n"
        "- bug: Bug triage: crashes, errors, stack traces\n"
    ), "one folded line per member, in registration order"

    size = 3000
    keywords = {f"w{i}": [f"topic{i}"] for i in range(size)}
    keywords["late"] = ["latecomer"]
    router = KeywordRouter(keywords)
    big = Supervisor("big", "Every topic", router)
    staff = [Worker(f"w{i}", f"Topic {i} questions.\nAsks for logs first.", answer(f"w{i}")) for i in range(size)]
    start = time.perf_counter()
    for worker in staff:
        big.register(worker)
    assert time.perf_counter() - start < 0.05, "registering a member stays cheap"
    tasks = [f"a question on topic{(i * 7919) % size}" for i in range(800)]
    big.route(tasks[0])
    start = time.perf_counter()
    chosen = [big.route(task) for task in tasks]
    elapsed = time.perf_counter() - start
    assert chosen == [f"w{(i * 7919) % size}" for i in range(800)], "the task goes to the member the router names"
    assert elapsed < 0.04, "routing many tasks through one supervisor should be fast"

    big.register(Worker("late", "Joined after the first batch", answer("late")))
    assert big.route("hello latecomer") == "late", "a member registered later takes its tasks"
    assert big.prompt().endswith("- late: Joined after the first batch\n"), "a member registered later is in the prompt"


V1 = Topology(
    root="desk",
    workers=(
        WorkerSpec("refund", "Refunds — remboursements, 退款.\n  Ask for the invoice.  ", 12, ("refund", "退款")),
        WorkerSpec("bug", "Bug triage\twith logs", 5, ()),
        WorkerSpec("sales", "Quotes and pricing\n", 4, ("quote", "pricing")),
    ),
    teams=(
        TeamSpec("ops", "Customer ops", ("refund", "bug"), ("refund", "crash")),
        TeamSpec("commercial", "Commercial", ("sales",), ("quote",), router=None),
        TeamSpec("desk", "Front desk", ("commercial", "ops"), (), router="router-small"),
    ),
)


@pytest.mark.skip("Part 2")
def test_topology_snapshot(tmp_path, monkeypatch) -> None:
    """The topology survives a snapshot exactly, and a failed save never damages the last good one."""
    path = tmp_path / "topology.json"
    save_topology(path, V1)
    assert load_topology(path) == V1, "a topology must round-trip exactly"
    teams = json.loads(path.read_text(encoding="utf-8"))["teams"]
    assert "router" not in teams[0] and teams[1]["router"] is None, (
        "an inheriting team has no router key; a keyword-routed team has router null"
    )

    hand = tmp_path / "hand.json"
    hand.write_text(
        json.dumps({
            "format": 1,
            "root": "desk",
            "workers": [{"name": "w", "description": "", "tokens": 1, "keywords": ["x"]}],
            "teams": [{"name": "desk", "description": "", "members": ["w"], "keywords": []}],
        }),
        encoding="utf-8",
    )
    assert load_topology(hand).teams[0].router is INHERIT, "a team without a router key inherits"

    v2 = dataclasses.replace(V1, teams=V1.teams[:2] + (dataclasses.replace(V1.teams[2], router="router-large"),))
    moves: list[tuple[str, str]] = []

    def broken_move(src, dst) -> None:
        moves.append((os.fspath(src), os.fspath(dst)))
        raise OSError("disk full")

    with monkeypatch.context() as m:
        m.setattr(os, "replace", broken_move)
        m.setattr(os, "rename", broken_move)
        with pytest.raises(OSError):
            save_topology(path, v2)
    assert moves and Path(moves[0][0]).parent == path.parent, "the temp file sits next to the snapshot"
    assert load_topology(path) == V1, "an interrupted save keeps the previous snapshot"
    assert sorted(os.listdir(tmp_path)) == ["hand.json", "topology.json"], "a failed save leaves no temp file behind"

    save_topology(path, v2)
    assert load_topology(path) == v2, "a topology must round-trip exactly"
    for broken in (
        dataclasses.replace(V1, teams=(dataclasses.replace(V1.teams[0], members=("refund", "billing")),) + V1.teams[1:]),
        dataclasses.replace(V1, workers=V1.workers + (WorkerSpec("ops", "", 1),)),
        dataclasses.replace(V1, root="refund"),
    ):
        with pytest.raises(ValueError):
            save_topology(path, broken)
    assert load_topology(path) == v2, "an invalid topology is rejected before anything is written"
    assert sorted(os.listdir(tmp_path)) == ["hand.json", "topology.json"], (
        "an invalid topology is rejected before anything is written"
    )


WORKERS = [
    WorkerSpec("a", "", 30, ("refund", "invoice")),
    WorkerSpec("b", "", 50, ("invoice", "chargeback")),
    WorkerSpec("c", "", 20, ("dispute",)),
    WorkerSpec("d", "", 40, ("crash",)),
    WorkerSpec("e", "", 60, ("error", "crash")),
    WorkerSpec("f", "", 10, ("login",)),
    WorkerSpec("g", "", 70, ("password",)),
    WorkerSpec("h", "", 25, ("quote",)),
    WorkerSpec("i", "", 25, ("pricing",)),
    WorkerSpec("j", "", 80, ("legal",)),
]


def prompt_cost(topology: Topology, team: TeamSpec, overhead: int, team_tokens: int) -> int:
    members = [topology.find(name) for name in team.members]
    return overhead + sum(m.tokens if isinstance(m, WorkerSpec) else team_tokens for m in members)


@pytest.mark.skip("Part 3")
def test_budgeted_hierarchy() -> None:
    """Nest supervisors only where the context budget forces it, and never build fake layers."""
    topology = plan_hierarchy(WORKERS, budget=120, overhead=20, team_tokens=15)
    assert [(t.name, t.members) for t in topology.teams] == [
        ("L1-0", ("a", "b", "c")),
        ("L1-1", ("d", "e")),
        ("L1-2", ("f", "g")),
        ("L1-3", ("h", "i")),
        ("L2-0", ("L1-0", "L1-1", "L1-2", "L1-3")),
        ("root", ("L2-0", "j")),
    ], "greedy groups, in order, each as long as the budget allows; a group of one is carried up"
    assert topology.root == "root" and topology.workers == tuple(WORKERS), (
        "the root supervisor is named root, and the workers stay as given"
    )
    assert all(prompt_cost(topology, t, 20, 15) <= 120 for t in topology.teams), "every prompt fits the budget"
    assert topology.find("L1-0").keywords == ("refund", "invoice", "chargeback", "dispute"), (
        "a supervisor's keywords are its members', in order, without repeats"
    )
    assert topology.find("L1-1") == TeamSpec("L1-1", "Supervises d, e", ("d", "e"), ("crash", "error"), INHERIT), (
        "a made supervisor names its members, takes their keywords and inherits its router"
    )

    small = plan_hierarchy(WORKERS[:3], budget=120, overhead=20, team_tokens=15)
    assert [(t.name, t.members) for t in small.teams] == [("root", ("a", "b", "c"))], (
        "workers that fit under one supervisor get no extra layer"
    )
    mixed = plan_hierarchy([WORKERS[4], WORKERS[1], WORKERS[5]], budget=120, overhead=20, team_tokens=15)
    assert [(t.name, t.members) for t in mixed.teams] == [("L1-0", ("b", "f")), ("root", ("e", "L1-0"))], (
        "the root's prompt pays the overhead too; carried items keep their place; supervisors are numbered as made"
    )
    with pytest.raises(ValueError) as caught:
        plan_hierarchy([WORKERS[0], WorkerSpec("huge", "", 101)], budget=120, overhead=20, team_tokens=15)
    assert "huge" in str(caught.value), "the error names the worker that cannot fit in any prompt"

    outcome: dict[str, Exception] = {}

    def attempt() -> None:
        try:
            plan_hierarchy([WorkerSpec(f"p{n}", "", 60) for n in range(4)], budget=120, overhead=20, team_tokens=15)
        except ValueError as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(2.0)
    assert "error" in outcome, "a level that cannot be cut into fewer items raises ValueError instead of looping"


CASE = {
    "customer": "Ada Lovelace",
    "email": "ada@example.com",
    "invoice": "4711",
    "card": "4242 4242 4242 4242",
}
VIEWS = {
    "refund": ("invoice", "customer", "card"),
    "sales": ("customer", "seats"),
    "audit": ("invoice",),
    "legal": ("customer",),
}
CALLS = [
    ToolCall("refund", "refund the invoice"),
    ToolCall("sales", "quote 20 seats"),
    ToolCall("audit", "record the refund"),
    ToolCall("legal", "check the contract"),
]


class SpecialistPool:
    """Stands in for the specialists at the far end of the channel.

    Replies follow the script, a list of ("reply", id) and ("progress", id) steps, so they come
    back out of order. Unknown methods get JSON-RPC's "Method not found" error, and a handler
    that raises becomes a server error.
    """

    def __init__(self, script: list[tuple[str, int]]) -> None:
        self.script = list(script)
        self.sent: list[dict] = []
        self.receives = 0
        self.handlers = {
            "refund": lambda p: f"refunded invoice {p['context']['invoice']}",
            "sales": lambda p: f"quote for {p['context']['customer']}",
            "audit": self.read_only,
        }

    @staticmethod
    def read_only(params: dict) -> str:
        raise RuntimeError("audit log is read-only")

    async def send(self, frame: str) -> None:
        await asyncio.sleep(0)
        self.sent.append(json.loads(frame))

    async def receive(self) -> str:
        await asyncio.sleep(0)
        self.receives += 1
        assert self.script, "every call already has its reply; stop reading"
        kind, call_id = self.script.pop(0)
        requests = {r["id"]: r for r in self.sent}
        assert call_id in requests, "send every tool call before waiting for a reply"
        if kind == "progress":
            return json.dumps({"jsonrpc": "2.0", "method": "progress", "params": {"id": call_id, "note": "working"}})
        request = requests[call_id]
        handler = self.handlers.get(request["method"])
        if handler is None:
            error = {"code": -32601, "message": "Method not found"}
            return json.dumps({"jsonrpc": "2.0", "id": call_id, "error": error})
        try:
            return json.dumps({"jsonrpc": "2.0", "id": call_id, "result": handler(request["params"])})
        except Exception as exc:
            return json.dumps({"jsonrpc": "2.0", "id": call_id, "error": {"code": -32000, "message": str(exc)}})


SCRIPT = [("progress", 2), ("reply", 3), ("reply", 1), ("progress", 1), ("reply", 4), ("reply", 2)]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


@pytest.mark.skip("Part 4")
def test_tool_call_supervision() -> None:
    """The supervisor calls specialists as tools over JSON-RPC and passes results on as they arrive."""
    pool = SpecialistPool(SCRIPT)
    results = collect(supervise(CASE, CALLS, VIEWS, pool))
    assert pool.sent == [
        {"jsonrpc": "2.0", "id": 1, "method": "refund", "params": {
            "instruction": "refund the invoice",
            "context": {"invoice": "4711", "customer": "Ada Lovelace", "card": "4242 4242 4242 4242"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "sales", "params": {
            "instruction": "quote 20 seats", "context": {"customer": "Ada Lovelace"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "audit", "params": {
            "instruction": "record the refund", "context": {"invoice": "4711"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "legal", "params": {
            "instruction": "check the contract", "context": {"customer": "Ada Lovelace"}}},
    ], "each request is a JSON-RPC 2.0 call carrying exactly the fields its specialist may see"
    assert results == [
        ToolResult(3, "audit", False, "audit log is read-only"),
        ToolResult(1, "refund", True, "refunded invoice 4711"),
        ToolResult(4, "legal", False, "Method not found"),
        ToolResult(2, "sales", True, "quote for Ada Lovelace"),
    ], "results come out in the order their replies arrive, matched to calls by id"

    probe = SpecialistPool(SCRIPT)

    async def first_result() -> ToolResult:
        agen = supervise(CASE, CALLS, VIEWS, probe)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert asyncio.run(first_result()).call_id == 3, "the first result is the first reply to arrive"
    assert probe.receives == 2, (
        "pass each result on as soon as its reply arrives, and read nothing the caller has not asked for"
    )

    quiet = SpecialistPool([])
    with pytest.raises(ValueError):
        collect(supervise(CASE, CALLS + [ToolCall("billing", "charge the card")], VIEWS, quiet))
    assert quiet.sent == [], "a call with no view is refused before anything is sent"


DESK = Topology(
    root="desk",
    workers=(
        WorkerSpec("refunds", "Refunds", 5, ("refund",)),
        WorkerSpec("disputes", "Disputes", 5, ("chargeback", "dispute")),
        WorkerSpec("crashes", "Crash triage", 5, ("crash", "error")),
        WorkerSpec("password_reset", "Password resets", 5, ("password",)),
        WorkerSpec("quotes", "Quotes", 5, ("quote", "pricing", "invoice")),
    ),
    teams=(
        TeamSpec("billing", "Billing", ("refunds", "disputes"), ("invoice", "refund", "chargeback")),
        TeamSpec("accounts", "Accounts", ("password_reset",), ("login", "password", "invoice")),
        TeamSpec("support", "Support", ("crashes", "accounts"), ("crash", "error", "bug", "invoice")),
        TeamSpec("commercial", "Commercial", ("accounts", "quotes"), ("pricing", "quote", "invoice")),
        TeamSpec("desk", "Front desk", ("billing", "support", "commercial"), ()),
    ),
)

INVOICE_TRACE = (
    "desk -> billing",
    "  billing -> none",
    "desk -> support, back from billing",
    "  support -> accounts",
    "    accounts -> none",
    "  support -> none, back from accounts",
    "desk -> commercial, back from support",
    "  commercial -> quotes",
)


@pytest.mark.skip("Part 5")
def test_hierarchical_routing() -> None:
    """Route down the nested teams by keyword, backing out of dead ends, and count and trace every pick."""
    refund = route(DESK, "REFUND for invoice 4711")
    assert refund == Route("refunds", ("desk", "billing", "refunds"), 3, 0), (
        "each team offers its first matching member; one op per pick, plus one for the worker"
    )
    assert refund.trace == ("desk -> billing", "  billing -> refunds"), (
        "one trace line per pick: two spaces for every team above it on the path, then team -> member"
    )

    found = route(DESK, "a question about invoice 4711")
    assert (found.worker, found.path, found.backtracks) == ("quotes", ("desk", "commercial", "quotes"), 3), (
        "back out of a dead end to the next matching member; a team that came up empty is not entered again"
    )
    assert found.ops == 9, "every pick costs an op, the empty ones too, plus one for the worker"
    assert len(found.trace) == found.ops - 1, "one trace line per pick, the empty ones too, and nothing else"
    assert found.trace == INVOICE_TRACE, (
        "after a backtrack, the team above writes its next pick at its own depth and names the team it came back from"
    )
    capped = route(DESK, "a question about invoice 4711", max_backtracks=2)
    assert capped == Route(None, (), 6, 2), (
        "needing more backtracks than allowed leaves the task unresolved"
    )
    assert capped.trace == INVOICE_TRACE[:6], "an unresolved task keeps the trace of every pick it made"
    assert route(DESK, "Quote, please: the debugger add-on") == Route(
        "quotes", ("desk", "commercial", "quotes"), 3, 0
    ), "keywords match whole words"
    parcel = route(DESK, "my parcel never arrived")
    assert parcel == Route(None, (), 1, 0), (
        "a dead end at the root leaves the task unresolved"
    )
    assert parcel.trace == ("desk -> none",), "an unresolved task keeps the trace of every pick it made"

    loop = Topology(
        root="a",
        workers=(WorkerSpec("w", "", 1, ("x",)),),
        teams=(TeamSpec("a", "", ("b",), ("loop",)), TeamSpec("b", "", ("a", "w"), ("loop",))),
    )
    with pytest.raises(ValueError):
        route(loop, "loop x")
