import asyncio
import copy
import csv
import hashlib
import io
import json
import time

import pytest
from webgym.app import ShoppingApp
from webgym.harness import Action, Result, Task, run_suite
from webgym.parallel import run_parallel
from webgym.predicates import Verdict, evaluate
from webgym.snapshots import SnapshotError, SnapshotStore
from webgym.trajectory import align, efficiency

A = Action

SNAPSHOT = {
    "catalog": [
        {"sku": "sku-001", "name": "headphones", "price": 199},
        {"sku": "sku-002", "name": "keyboard", "price": 129},
        {"sku": "sku-003", "name": "mouse", "price": 59},
    ],
    "cart": {},
    "orders": [{"oid": "ord-001", "items": {"sku-002": 1}, "total": 129}],
}


def scripted(*plan):
    """A scripted agent: ("note", text) entries are notes, anything else is (action, args)."""

    def agent(env) -> None:
        for name, arg in plan:
            if name == "note":
                env.note(arg)
            else:
                env.act(name, **arg)

    return agent


@pytest.mark.skip("Part 1")
def test_suite_judging() -> None:
    """Episodes are judged on their final state, counted in actions, and isolated by reset."""
    snapshot = copy.deepcopy(SNAPSHOT)
    buy = [A("list_items"), A("add_to_cart", {"sku": "sku-001"}), A("checkout")]
    swap = buy[:2] + [A("add_to_cart", {"sku": "sku-003"}), A("checkout")]
    other_paths = [
        Task("headphones_detour", {"sku-001": 1}, buy, scripted(
            ("list_items", {}), ("add_to_cart", {"sku": "sku-003"}), ("remove_from_cart", {"sku": "sku-003"}),
            ("add_to_cart", {"sku": "sku-001"}), ("checkout", {}))),
        Task("headphones_direct", {"sku-001": 1}, buy, scripted(
            ("add_to_cart", {"sku": "sku-001"}), ("checkout", {}))),
        Task("bundle_other_order", {"sku-001": 1, "sku-003": 1}, swap, scripted(
            ("list_items", {}), ("add_to_cart", {"sku": "sku-003"}), ("add_to_cart", {"sku": "sku-001"}),
            ("checkout", {}))),
    ]
    assert [r.success for r in run_suite(snapshot, other_paths)] == [True, True, True], (
        "an episode that ends in the wanted state succeeds, whatever path it took"
    )

    tasks = [
        Task("headphones", {"sku-001": 1}, buy, scripted(
            ("list_items", {}), ("add_to_cart", {"sku": "sku-001"}), ("checkout", {}))),
        Task("keyboard_again", {"sku-002": 1}, buy, scripted(("list_items", {}))),
        Task("mouse", {"sku-003": 1}, buy, scripted(
            ("add_to_cart", {"sku": "sku-002"}), ("checkout", {}),
            ("note", "wrong item, buy the mouse instead"),
            ("add_to_cart", {"sku": "sku-003"}), ("checkout", {}))),
        Task("headphones_only", {"sku-001": 1}, buy, scripted(
            ("add_to_cart", {"sku": "sku-0O1"}), ("add_to_cart", {"sku": "sku-001"}),
            ("add_to_cart", {"sku": "sku-003"}), ("checkout", {}))),
        Task("swap", {"sku-001": 1, "sku-003": 1}, swap, scripted(
            ("list_items", {}), ("add_to_cart", {"sku": "sku-001"}), ("add_to_cart", {"sku": "sku-002"}),
            ("note", "revised choice: drop the keyboard"), ("remove_from_cart", {"sku": "sku-002"}),
            ("add_to_cart", {"sku": "sku-003"}), ("checkout", {}))),
    ]
    results = run_suite(snapshot, tasks)
    assert [r.success for r in results] == [True, False, False, False, True], (
        "success is judged on the final state: exactly one new order, holding exactly the wanted items"
    )
    replay = Task("replay", {"sku-001": 1}, buy, scripted(*[(a.name, a.args) for a in buy]))
    (replayed,) = run_suite({**snapshot, "cart": {"sku-002": 1}}, [replay])
    assert not replayed.success, "the final state decides, even when the agent replays gold step for step"
    assert [r.steps for r in results] == [3, 1, 4, 4, 6], (
        "every action is a step, an action that returned an error too; notes are not steps"
    )
    assert [r.gold_steps for r in results] == [3, 3, 3, 3, 4]
    assert results[4].orders == [
        {"oid": "ord-002", "items": {"sku-001": 1, "sku-003": 1}, "total": 258}
    ], "an episode reports the orders it placed"

    app = ShoppingApp(snapshot)
    rows = app.list_items()
    rows[0]["price"] = 1
    assert app.list_items()[0]["price"] == 199, "list_items hands out copies of the catalog rows"
    for bad in (0, -1, 1.5):
        assert app.add_to_cart("sku-001", bad).startswith("error"), "quantities must be positive integers"
    assert app.cart == {}, "a rejected add leaves the cart alone"

    pinned = copy.deepcopy(snapshot)
    markdown = Task("markdown", {"sku-003": 1}, [A("set_price"), A("add_to_cart"), A("checkout")], scripted(
        ("set_price", {"sku": "sku-003", "price": 49}), ("add_to_cart", {"sku": "sku-003"}), ("checkout", {})))
    mouse = Task("mouse", {"sku-003": 1}, buy, scripted(
        ("add_to_cart", {"sku": "sku-003"}), ("checkout", {})))
    first, second = run_suite(snapshot, [markdown, mouse])
    assert first.orders[0]["total"] == 49, "state carries over between the actions of one episode"
    assert second.orders[0]["total"] == 59, "every episode starts from the pinned snapshot"
    assert snapshot == pinned, "running episodes never changes the pinned snapshot"
    app = ShoppingApp(snapshot)
    app.set_price("sku-003", 49)
    app.reset()
    assert app.state() == pinned, "reset puts the app back to exactly the pinned state"

    big = {
        "catalog": [{"sku": f"sku-{i:05d}", "name": f"item {i}", "price": 100 + i % 7} for i in range(5000)],
        "cart": {},
        "orders": [],
    }
    skus = [f"sku-{i:05d}" for i in range(0, 5000, 2)]
    bulk = Task("bulk", {sku: 1 for sku in skus}, [], scripted(
        *[("add_to_cart", {"sku": sku}) for sku in skus], ("checkout", {})))
    start = time.perf_counter()
    (result,) = run_suite(big, [bulk])
    elapsed = time.perf_counter() - start
    assert result.success
    assert elapsed < 0.08, "adding to the cart should stay fast on a large catalog"


# The digest of STORED under the canonical form described in SnapshotStore.
STORED_DIGEST = "f0801a60fadacc15664c9195cd472250ac41140004db876136672caa664d0efe"

STORED = {
    "catalog": [
        {"sku": "sku-010", "name": "Kopfhörer", "price": 19900},
        {"sku": "sku-002", "name": "keyboard, mechanical", "price": 12900},
        {"sku": "sku-003", "name": 'mouse "pro"', "price": 5900},
    ],
    "cart": {"sku-003": 2},
    "orders": [{"oid": "ord-001", "items": {"sku-010": 1, "sku-002": 1}, "total": 32800}],
}


@pytest.mark.skip("Part 2")
def test_snapshot_store(tmp_path) -> None:
    """Pinned snapshots are stored by content and come back exactly, or not at all."""
    root = tmp_path / "snapshots"
    store = SnapshotStore(root)
    digest = store.put(copy.deepcopy(STORED))
    assert digest == STORED_DIGEST, "the digest is the SHA-256 of the canonical JSON"

    shuffled = {
        "orders": [{"total": 32800, "items": {"sku-002": 1, "sku-010": 1}, "oid": "ord-001"}],
        "cart": {"sku-003": 2},
        "catalog": [{"price": r["price"], "name": r["name"], "sku": r["sku"]} for r in STORED["catalog"]],
    }
    assert store.put(shuffled) == digest, "key order does not change the digest"
    reordered = copy.deepcopy(STORED)
    reordered["catalog"].reverse()
    other = store.put(reordered)
    assert other != digest, "the catalog order is part of the state"
    assert sorted(p.name for p in root.iterdir()) == sorted([f"{digest}.json", f"{other}.json"]), (
        "one file per distinct snapshot, named by its digest"
    )

    back = SnapshotStore(root).get(digest)
    assert back == STORED, "a snapshot round-trips exactly"
    assert [r["sku"] for r in back["catalog"]] == ["sku-010", "sku-002", "sku-003"], (
        "a snapshot round-trips exactly"
    )
    assert all(type(r["price"]) is int for r in back["catalog"]), "prices come back as integer cents"
    assert ShoppingApp(back).state() == STORED
    with pytest.raises(KeyError):
        store.get(hashlib.sha256(b"never stored").hexdigest())

    for field, bad in (("price", 5900.0), ("price", True), ("price", -1)):
        broken = copy.deepcopy(STORED)
        broken["catalog"][2][field] = bad
        with pytest.raises(ValueError):
            store.put(broken)
    broken = copy.deepcopy(STORED)
    broken["cart"]["sku-003"] = 0
    with pytest.raises(ValueError):
        store.put(broken)
    broken = copy.deepcopy(STORED)
    broken["orders"][0]["total"] = 32800.0
    with pytest.raises(ValueError):
        store.put(broken)
    broken = copy.deepcopy(STORED)
    broken["orders"][0]["items"]["sku-010"] = 0
    with pytest.raises(ValueError):
        store.put(broken)
    assert sorted(p.name for p in root.iterdir()) == sorted([f"{digest}.json", f"{other}.json"]), (
        "a rejected snapshot is not stored"
    )

    path = root / f"{digest}.json"
    original = path.read_bytes()
    edits = [
        original.replace(b":5900,", b":4900,"),
        original.replace(b":5900,", b":5900.0,"),
        json.dumps(json.loads(original), sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8"),
    ]
    for edited in edits:
        assert edited != original
        path.write_bytes(edited)
        with pytest.raises(SnapshotError, match=digest):
            store.get(digest)
    path.write_bytes(original)
    assert store.get(digest) == STORED


@pytest.mark.skip("Part 3")
def test_trajectory_efficiency() -> None:
    """Align agent actions with gold, and report steps over gold for successful tasks."""
    gold = [A("list_items"), A("add_to_cart", {"sku": "sku-001"}), A("add_to_cart", {"sku": "sku-003", "qty": 2}),
            A("checkout")]
    agent = [A("list_items"), A("add_to_cart", {"sku": "SKU-001", "qty": 1}), A("add_to_cart", {"sku": "sku-001"}),
             A("add_to_cart", {"qty": 2, "sku": "sku-003"}), A("checkout")]
    assert align(agent, gold).ops == [
        ("match", 0, 0), ("match", 1, 1), ("extra", 2, None), ("match", 3, 2), ("match", 4, 3)
    ], "compare normalized actions; of two identical adds, the repeat is the extra one"

    short = [A("list_items"), A("add_to_cart", {"sku": "sku-003"}), A("checkout")]
    wrong_target = align([A("list_items"), A("add_to_cart", {"sku": "sku-002"}), A("checkout")], short)
    assert wrong_target.ops == [("match", 0, 0), ("substitute", 1, 1), ("match", 2, 2)], (
        "the right action on the wrong item is one substitution"
    )
    assert wrong_target.count("substitute") == 1
    wrong_action = align([A("list_items"), A("remove_from_cart", {"sku": "sku-003"}), A("checkout")], short)
    assert wrong_action.ops == [("match", 0, 0), ("extra", 1, None), ("missing", None, 1), ("match", 2, 2)], (
        "different actions are never paired; on a tie, skip the agent's action first"
    )
    assert align([], short[:2]).ops == [("missing", None, 0), ("missing", None, 1)]
    assert align(short[:1], []).ops == [("extra", 0, None)]

    results = [
        Result("a", True, 6, 4),
        Result("b", True, 3, 3),
        Result("c", False, 10, 3),
        Result("d", True, 9, 3),
    ]
    report = efficiency(results)
    assert report["success_rate"] == pytest.approx(0.75)
    assert report["micro"] == pytest.approx(18 / 10), "micro: total steps over total gold, successful tasks only"
    assert report["macro"] == pytest.approx((1.5 + 1.0 + 3.0) / 3), "macro: mean of per-task ratios"
    assert efficiency([Result("c", False, 10, 3)]) == {"success_rate": 0.0, "micro": None, "macro": None}, (
        "no successful task, no efficiency"
    )


@pytest.mark.skip("Part 4")
def test_parallel_episodes(tmp_path) -> None:
    """Concurrent episodes stay isolated, and each reports one CSV record as it finishes."""
    store = SnapshotStore(tmp_path)
    digest = store.put({**copy.deepcopy(SNAPSHOT), "orders": []})
    gate = asyncio.Event()
    active, peak = [0], [0]

    def tracked(body):
        async def agent(env) -> None:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            try:
                await body(env)
            finally:
                active[0] -= 1

        return agent

    async def hold(env) -> None:
        env.act("add_to_cart", sku="sku-001")
        await gate.wait()
        env.act("checkout")

    async def mouse(env) -> None:
        env.act("add_to_cart", sku="sku-003")
        await asyncio.sleep(0)
        env.act("checkout")

    async def crash(env) -> None:
        env.act("add_to_cart", sku="sku-002")
        env.act("checkout")
        await asyncio.sleep(0)
        raise RuntimeError("agent crashed")

    two = [A("add_to_cart"), A("checkout")]
    tasks = [
        Task('hold, "headphones"', {"sku-001": 1}, two, tracked(hold)),
        Task("mouse", {"sku-003": 1}, two, tracked(mouse)),
        Task("crash", {"sku-002": 1}, two, tracked(crash)),
    ]

    async def consume() -> list[str]:
        lines = []
        async for line in run_parallel(store, digest, tasks, limit=2):
            lines.append(line)
            if next(csv.reader(io.StringIO(line)), [])[:1] == ["crash"]:
                gate.set()
        return lines

    try:
        lines = asyncio.run(asyncio.wait_for(consume(), 1.0))
    except asyncio.TimeoutError:
        pytest.fail(
            "the stream stalled: every episode, a crashed one too, reports its record as soon as it "
            "finishes, and a freed slot starts the next episode right away"
        )
    assert all(len(list(csv.reader(io.StringIO(line)))) == 1 and line.endswith("\n") for line in lines), (
        "every yielded string is one CSV record with its line ending"
    )
    assert list(csv.reader(io.StringIO("".join(lines)))) == [
        ["task_id", "success", "steps", "gold_steps"],
        ["mouse", "1", "2", "2"],
        ["crash", "0", "2", "2"],
        ['hold, "headphones"', "1", "2", "2"],
    ], "records in finish order; every episode has its own app; an agent that raises fails its own episode only"
    assert peak[0] == 2, "at most limit episodes run at once"
    assert store.get(digest) == {**SNAPSHOT, "orders": []}

    cancelled = []

    async def stuck(env) -> None:
        env.act("add_to_cart", sku="sku-001")
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(env.trace[-1].action.name)

    async def quick(env) -> None:
        env.act("add_to_cart", sku="sku-003")
        env.act("checkout")

    async def close_early() -> tuple[str, list[str]]:
        episodes = [Task("stuck", {"sku-001": 1}, two, stuck), Task("quick", {"sku-003": 1}, two, quick)]
        stream = run_parallel(store, digest, episodes, 2)
        await stream.__anext__()
        first = await stream.__anext__()
        await stream.aclose()
        await asyncio.sleep(0)
        return first, list(cancelled)

    first, seen = asyncio.run(asyncio.wait_for(close_early(), 1.0))
    assert list(csv.reader(io.StringIO(first))) == [["quick", "1", "2", "2"]]
    assert seen == ["add_to_cart"], "closing the stream cancels the episodes still running"


STATE = {
    "catalog": [
        {"sku": "sku-001", "name": "headphones", "price": 199},
        {"sku": "sku-002", "name": "keyboard", "price": 129},
        {"sku": "sku-003", "name": "mouse", "price": 49},
    ],
    "cart": {},
    "orders": [{"oid": "ord-001", "items": {"sku-001": 1, "sku-002": 2}, "total": 457}],
}


@pytest.mark.skip("Part 5")
def test_goal_predicates() -> None:
    """Nested success conditions, and the innermost predicate that explains a failure."""
    goal = {"all": [
        {"ordered": {"sku": "sku-001", "qty": 1}},
        {"not": {"ordered": {"sku": "sku-002"}}},
        {"price": {"sku": "sku-003", "eq": 49}},
    ]}
    assert evaluate(goal, STATE) == Verdict(False, ("all", 1, "not")), (
        "a failed not is explained by what it forbids; ordered without qty means any quantity"
    )
    assert evaluate(goal["all"][0], STATE) == Verdict(True, None)
    assert evaluate({"all": [goal["all"][0], goal["all"][2], {"cart_empty": {}}]}, STATE) == Verdict(True, None)

    assert evaluate({"all": []}, STATE) == Verdict(True, None), "an empty all holds"
    assert evaluate({"any": []}, STATE) == Verdict(False, ()), "an empty any does not"
    assert evaluate({"not": {"not": {"ordered": {"sku": "sku-003"}}}}, STATE) == Verdict(False, ("not", "not")), (
        "two negations cancel: blame the predicate that failed"
    )
    forbidden = {"not": {"any": [
        {"orders": {"count": 2}},
        {"ordered": {"sku": "sku-002", "qty": 2}},
        {"price": {"sku": "sku-003", "eq": 49}},
    ]}}
    assert evaluate(forbidden, STATE) == Verdict(False, ("not", "any", 1)), (
        "a forbidden any is explained by its first alternative that held"
    )
    nested = {"all": [
        {"price": {"sku": "sku-003", "eq": 49}},
        {"any": [{"orders": {"count": 2}}, {"ordered": {"sku": "sku-003"}}]},
        {"orders": {"count": 3}},
    ]}
    assert evaluate(nested, STATE) == Verdict(False, ("all", 1)), (
        "an any with no alternative holding is explained by itself; an all by its first failing child"
    )
    assert evaluate({"not": {"all": [{"cart_empty": {}}]}}, STATE) == Verdict(False, ("not",)), (
        "an all that held when it should not have is explained by itself"
    )
    exact = {"any": [{"orders": {"count": 0}}, {"ordered": {"sku": "sku-002", "qty": 1}}]}
    assert evaluate(exact, STATE) == Verdict(False, ()), "a count and a qty are matched exactly"

    with pytest.raises(ValueError, match="refunded"):
        evaluate({"any": [{"orders": {"count": 1}}, {"refunded": {"oid": "ord-001"}}]}, STATE)
    for malformed in (
        {"all": [{"cart_empty": {}}], "any": []},
        {"all": {"cart_empty": {}}},
        {"not": [{"cart_empty": {}}]},
        {"ordered": {"qty": 1}},
        {"ordered": {"sku": "sku-001", "quantity": 1}},
    ):
        with pytest.raises(ValueError):
            evaluate({"any": [{"cart_empty": {}}, malformed]}, STATE)
