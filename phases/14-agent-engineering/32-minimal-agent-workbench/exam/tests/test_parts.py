import copy
import difflib
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from workbench.context import load_context
from workbench.epics import roll_up
from workbench.files import AgentState, Task, check_board, load_board, load_state, save_board, write_initial
from workbench.lines import BoardLines
from workbench.patches import diff, turn_patches
from workbench.picker import Decision, next_task
from workbench.turn import take_turn


def task(task_id: str, status: str = "todo", owner: str = "builder", **extra) -> Task:
    return Task(task_id, f"goal of {task_id}", owner, ["make test"], status, extra=extra)


def read_files(root) -> dict:
    return {
        name: json.loads((root / name).read_text(encoding="utf-8"))
        for name in ("agent_state.json", "task_board.json")
    }


def apply_patch(doc, patch: list) -> object:
    """The watcher's side: a strict RFC 6902 applier for add, replace and remove."""
    doc = copy.deepcopy(doc)
    for op in patch:
        assert op.get("op") in ("add", "replace", "remove") and set(op) <= {"op", "path", "value"}, (
            f"unexpected operation {op}"
        )
        if op["path"] == "":
            doc = op["value"]
            continue
        assert op["path"].startswith("/"), f"not a JSON Pointer: {op['path']!r}"
        *parents, last = [t.replace("~1", "/").replace("~0", "~") for t in op["path"][1:].split("/")]
        target = doc
        for token in parents:
            target = target[int(token)] if isinstance(target, list) else target[token]
        if isinstance(target, list):
            index = int(last)
            top = len(target) if op["op"] == "add" else len(target) - 1
            assert 0 <= index <= top, f"{op['op']} {op['path']}: no such position"
            if op["op"] == "add":
                target.insert(index, op["value"])
            elif op["op"] == "replace":
                target[index] = op["value"]
            else:
                del target[index]
        else:
            assert op["op"] == "add" or last in target, f"{op['op']} {op['path']}: no such key"
            if op["op"] == "remove":
                del target[last]
            else:
                target[last] = op["value"]
    return doc


@pytest.mark.skip("Part 1")
def test_turn_cycle(tmp_path) -> None:
    """Turns pick up where a dead session stopped, and a task is done only when its acceptance passes."""
    root = tmp_path / "repo"
    write_initial(root)
    state_file = root / "agent_state.json"
    # A newer workbench wrote last_run and a lease, and the last session died after it saved the board.
    newer = json.loads(state_file.read_text(encoding="utf-8"))
    newer["last_run"] = "2026-11-02T18:40:00+00:00"
    newer["lease"] = "s-41"
    state_file.write_text(json.dumps(newer), encoding="utf-8")
    save_board(
        root / "task_board.json",
        [
            Task("T-007", "hotfix the /signup 500", "builder", ["pytest -q tests/test_signup.py"]),
            Task("R-003", "review T-005", "reviewer", ["gh pr checks 41"], "in_progress"),
            Task("T-006", "rate-limit /login", "builder",
                 ["pytest -q tests/test_login.py", "ruff check app"], "in_progress"),
            Task("T-008", "write the /login runbook", "builder", []),
            Task("H-002", "rotate the staging key", "human", ["vault status"]),
        ],
    )
    exits = {"pytest -q tests/test_login.py": -9, "ruff check app": 0, "pytest -q tests/test_signup.py": 0}

    def turns(n: int) -> tuple[AgentState, dict[str, Task]]:
        for _ in range(n):
            state, board = take_turn(root, exits.__getitem__)
        return state, {t.id: t for t in board}

    state, board = turns(1)
    on_disk = json.loads(state_file.read_text(encoding="utf-8"))
    assert (on_disk.get("last_run"), on_disk.get("lease")) == ("2026-11-02T18:40:00+00:00", "s-41"), (
        "keys this version does not know survive a turn"
    )
    assert state.active_task_id == "T-006", "the builder first takes back its own task left in progress"

    state, board = turns(3)
    assert board["T-006"].status == "blocked", "a failing acceptance command blocks the task"
    assert board["T-006"].checks == {"pytest -q tests/test_login.py": -9, "ruff check app": 0}, (
        "every acceptance command runs and its exit code is recorded"
    )
    assert (state.active_task_id, state.touched_files, state.blockers) == (
        None,
        [],
        ["pytest -q tests/test_login.py exited -9"],
    ), "a blocked task leaves the builder, and its failures become the blockers"

    state, board = turns(1)
    assert (state.active_task_id, state.blockers) == ("T-007", []), "a new task starts with no blockers"
    state, board = turns(3)
    assert board["T-007"].status == "done", "a task is done when every acceptance command exits 0"

    state, board = turns(4)
    assert board["T-008"].status == "blocked" and state.blockers == ["T-008 has no acceptance command"], (
        "a task without acceptance commands is never done"
    )
    state, board = turns(1)
    assert state.next_action == "no work on the board, idle", "reviewer and human tasks are not the builder's"
    assert load_state(state_file) == state, "the state file holds what the turn returned"

    # Two branches each added T-014, and the merge kept both.
    merged = [Task("T-013", "a", "builder", ["make a"]), Task("T-014", "b", "builder", ["make b"])]
    merged.append(Task("T-014", "c", "builder", ["make c"]))
    with pytest.raises(ValueError) as err:
        check_board(merged)
    assert "T-014" in str(err.value), "name the repeated id"

    # A board that has kept every finished task since the repo started.
    history = [Task(f"T-{n:05d}", f"task {n}", "builder", ["make test"], "done") for n in range(8000)]
    start = time.perf_counter()
    check_board(history)
    assert time.perf_counter() - start < 0.06, "checking a long board should be fast"

    context_root=tmp_path/'context-repo';context_root.mkdir()
    (context_root/'AGENTS.md').write_text('Read state and board; load deeper rules only when needed.\n',encoding='utf-8')
    (context_root/'docs').mkdir()
    rule='Scope commands first; style last.\n原样给当前回合。\n'
    verify='Run python -m pytest before declaring done.\n'
    (context_root/'docs/rules.md').write_text(rule,encoding='utf-8')
    (context_root/'docs/verify.md').write_text(verify,encoding='utf-8')
    requested=['docs/verify.md','./docs/rules.md','docs/verify.md','AGENTS.md']
    expected=[('AGENTS.md',(context_root/'AGENTS.md').read_text()),('docs/verify.md',verify),('docs/rules.md',rule)]
    assert load_context(context_root,requested)==expected, 'a tiny router loads root and explicitly requested documents once in request order'
    updated=rule+'The current acceptance command changed.\n'
    (context_root/'docs/rules.md').write_text(updated,encoding='utf-8');expected[-1]=('docs/rules.md',updated)
    assert load_context(context_root,requested)==expected, 'each turn sees fresh selected documentation rather than a cached catalog'
    unrelated=context_root/'docs/archive';unrelated.mkdir()
    for n in range(600):
        (unrelated/f'note-{n:04d}.md').write_text(f'# Resolved note {n}\n'+('Historical observation; no current request needs this note.\n'*8),encoding='utf-8')
    start=time.perf_counter()
    contexts=[load_context(context_root,requested) for _ in range(20)]
    elapsed=time.perf_counter()-start
    assert contexts==[expected]*20, 'context loading preserves selected documents across ordinary turn requests'
    assert elapsed<0.03, 'load requested context without reading every unrelated workspace document'
    (unrelated/'binary-export.md').write_bytes(b'not UTF-8: \xff\xfe')
    assert load_context(context_root,requested)==expected, 'unrequested documents are never read even when they are not valid UTF-8'


@pytest.mark.skip("Part 2")
def test_board_lines(tmp_path) -> None:
    """The board as JSON Lines round-trips exactly, and changing one task changes one line."""
    path = tmp_path / "task_board.jsonl"
    board = [
        Task("T-001", 'validate /signup ("strict" mode) \\ 注册校验 ✓', "builder",
             ["pytest -q tests/test_signup.py", "ruff check app"], "done",
             checks={"ruff check app": 0, "pytest -q tests/test_signup.py": 0}),
        Task("R-001", "review T-002 before the release", "reviewer", ["gh pr checks 41"], "in_progress",
             extra={"depends_on": ["T-002"], "priority": 3, "notes": None}),
        Task("T-002", "", "builder", [], "blocked", checks={"pytest -q tests/test_login.py": -9}),
    ]
    store = BoardLines(path)
    store.save(board)
    text = path.read_text(encoding="utf-8")
    assert text.split("\n")[1] == (
        '{"id": "R-001", "goal": "review T-002 before the release", "owner": "reviewer", '
        '"acceptance": ["gh pr checks 41"], "status": "in_progress", "checks": {}, '
        '"depends_on": ["T-002"], "priority": 3, "notes": null}'
    ), "one task per line: the lesson's keys in order, then the task's other keys"
    assert text.endswith("}\n") and text.count("\n") == 3, "every line ends with a newline"
    assert store.load() == board, "a board round-trips exactly"
    assert BoardLines(path).load() == board, "a board round-trips exactly"

    # Someone adds a task by hand, in their own style, after a blank line.
    with path.open("a", encoding="utf-8") as f:
        f.write('\n{"status":"todo","id":"T-003","owner":"builder",'
                '"goal":"bump ruff","acceptance":["ruff --version"]}\n')
    assert [t.id for t in store.load()] == ["T-001", "R-001", "T-002", "T-003"], "the file is read every time"

    before = path.read_text(encoding="utf-8").split("\n")
    store.update(Task("T-002", "", "builder", [], "todo", checks={"pytest -q tests/test_login.py": -9}))
    after = path.read_text(encoding="utf-8").split("\n")
    changed = list(difflib.unified_diff(before, after, lineterm="", n=0))[2:]
    assert changed == ["@@ -3 +3 @@", "-" + before[2], "+" + before[2].replace('"blocked"', '"todo"')], (
        "changing one task rewrites that task's line and no other"
    )
    store.update(Task("T-003", "bump ruff", "builder", ["ruff --version"], "in_progress"))
    assert path.read_text(encoding="utf-8").split("\n")[4] == (
        '{"id": "T-003", "goal": "bump ruff", "owner": "builder", "acceptance": ["ruff --version"], '
        '"status": "in_progress", "checks": {}}'
    ), "a hand-written line becomes a normal line once its task changes"
    assert [t.status for t in BoardLines(path).load()] == ["done", "in_progress", "todo", "in_progress"], (
        "the file reads back after both changes"
    )

    with pytest.raises(KeyError):
        store.update(Task("T-404", "not on the board", "builder", ["make test"]))
    unchanged = path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        store.update(Task("T-001", "x", "builder", ["make test"], "doing"))
    with pytest.raises(ValueError):
        store.update(Task("T-002", "", "builder", [], "in_progress"))  # the builder is already on T-003
    assert path.read_text(encoding="utf-8") == unchanged, "a change that breaks the board writes nothing"

    # Two branches each added T-004, and git kept both lines.
    with path.open("a", encoding="utf-8") as f:
        for goal in ("a", "b"):
            line = {"id": "T-004", "goal": goal, "owner": "builder", "acceptance": ["make"]}
            f.write(json.dumps(line) + "\n")
    with pytest.raises(ValueError):
        store.load()


@pytest.mark.skip("Part 3")
def test_pick_next() -> None:
    """The builder starts its most important ready task, and a stale state needs an operator."""
    now = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
    board = [
        task("T-001", "done"),
        task("H-001", owner="human", priority=9),
        task("T-002", "blocked", priority=7),
        task("T-003", priority=5, depends_on=["T-001", "T-004"]),
        task("T-004", "in_progress", owner="reviewer"),
        task("T-010", priority=2, depends_on=["T-001"]),
        task("T-006", priority=2),
        task("T-007"),
    ]
    assert next_task(board, now) == Decision("start", "T-010"), (
        "the builder's highest-priority todo whose dependencies are done, board order on ties"
    )

    waiting = [
        task("T-020", depends_on=["T-021", "T-022"]),
        task("T-021", "blocked"),
        task("T-022", "done"),
        task("H-020", owner="human", depends_on=["T-021"]),
        task("T-023", depends_on=["T-021"]),
    ]
    assert next_task(waiting, now) == Decision("idle", waiting={"T-020": ["T-021"], "T-023": ["T-021"]}), (
        "idle says what each builder todo is still waiting for"
    )
    assert next_task([task("T-030", "done")], now) == Decision("idle"), "an empty queue is idle"
    with pytest.raises(ValueError) as err:
        next_task([task("T-031"), task("T-032", depends_on=["T-099"])], now)
    assert "T-099" in str(err.value), "a dependency that is not on the board is an error"

    last_run = "2026-11-02T09:00:00+00:00"
    assert next_task(board, now, last_run=last_run).action == "start", "exactly 24 hours old is not stale yet"
    later = now + timedelta(seconds=1)
    assert next_task(board, later, last_run=last_run) == Decision("refuse"), (
        "a state more than 24 hours old needs an operator"
    )
    assert next_task(waiting, later, last_run=last_run) == Decision("refuse"), (
        "a stale state is refused even when there is nothing to start"
    )
    assert next_task(board, later, last_run=last_run, confirm=last_run).action == "start", (
        "the operator confirmed this state"
    )
    assert next_task(
        board, later + timedelta(days=2), last_run="2026-11-04T09:00:00+00:00", confirm=last_run
    ) == Decision("refuse"), "a confirmation covers the state it named, not the next one"
    assert next_task(board, now, last_run="2026-11-02T10:30:00+02:00") == Decision("refuse"), (
        "10:30 at UTC+2 is 24.5 hours before now"
    )
    with pytest.raises(ValueError):
        next_task(board, now, last_run="2026-11-02T09:00:00")


@pytest.mark.skip("Part 4")
def test_turn_patches(tmp_path) -> None:
    """Every turn reaches the watcher as one JSON Patch line, as soon as the turn ends."""
    login = ["pytest -q tests/test_login.py", "git diff --quiet HEAD~1 -- migrations/"]
    before = {
        "agent_state.json": {"active_task_id": "T-006", "touched_files": ["app.py", "test_app.py"],
                             "assumptions": ["staging only"], "blockers": [],
                             "next_action": "run verification command for T-006", "lease": "s-41"},
        "task_board.json": [{"id": "T-006", "goal": "rate-limit /login", "owner": "builder",
                             "acceptance": login, "status": "in_progress", "checks": {}}],
    }
    after = copy.deepcopy(before)
    after["agent_state.json"].update(
        active_task_id=None,
        touched_files=[],
        blockers=["pytest -q tests/test_login.py exited 1"],
        next_action="T-006 is blocked",
    )
    del after["agent_state.json"]["lease"]
    after["task_board.json"][0].update(status="blocked", checks={login[0]: 1, login[1]: 0})
    after["task_board.json"].append({"id": "H-003", "goal": "look at the login limits", "owner": "human",
                                     "acceptance": [], "status": "todo", "checks": {}})
    assert diff(before, after) == [
        {"op": "replace", "path": "/agent_state.json/active_task_id", "value": None},
        {"op": "remove", "path": "/agent_state.json/touched_files/1"},
        {"op": "remove", "path": "/agent_state.json/touched_files/0"},
        {"op": "add", "path": "/agent_state.json/blockers/0", "value": after["agent_state.json"]["blockers"][0]},
        {"op": "replace", "path": "/agent_state.json/next_action", "value": "T-006 is blocked"},
        {"op": "remove", "path": "/agent_state.json/lease"},
        {"op": "replace", "path": "/task_board.json/0/status", "value": "blocked"},
        {"op": "add", "path": "/task_board.json/0/checks/pytest -q tests~1test_login.py", "value": 1},
        {"op": "add", "path": "/task_board.json/0/checks/git diff --quiet HEAD~01 -- migrations~1", "value": 0},
        {"op": "add", "path": "/task_board.json/1", "value": after["task_board.json"][1]},
    ], "one operation per changed value, in document order, on escaped JSON Pointers"
    assert diff(after, copy.deepcopy(after)) == [], "equal documents need no operations"

    root = tmp_path / "repo"
    write_initial(root)
    save_board(root / "task_board.json", [
        Task("T-006", "rate-limit /login", "builder", login),
        Task("T-007", "hotfix the /signup 500", "builder", ["pytest -q tests/test_signup.py"]),
    ])
    exits = {login[0]: 1, login[1]: 0, "pytest -q tests/test_signup.py": 0}
    mirror = read_files(root)
    lines = []
    for line in turn_patches(root, exits.__getitem__, turns=15):
        lines.append(line)
        if len(lines) == 1:
            state = read_files(root)["agent_state.json"]
            assert (state["active_task_id"], state["touched_files"]) == ("T-006", []), (
                "yield each patch as soon as its turn ends"
            )
        assert line.endswith("\n") and line.count("\n") == 1, "one patch per line"
        mirror = apply_patch(mirror, json.loads(line))
        assert mirror == read_files(root), f"patch {len(lines)} brings the watcher up to date"
        if len(lines) == 4:
            # Between turns a person unblocks T-006, fixes its test and files a task of their own.
            tasks = load_board(root / "task_board.json")
            tasks[0].status = "todo"
            tasks.append(Task("H-003", "look at the login limits", "human", []))
            save_board(root / "task_board.json", tasks)
            exits[login[0]] = 0
    assert [t["status"] for t in mirror["task_board.json"]] == ["done", "done", "todo"], (
        "T-006 passes once its test is fixed"
    )
    assert len(lines) == 15 and lines[-2:] == ["[]\n", "[]\n"] and lines[-3] != "[]\n", (
        "a turn that changes nothing still sends []"
    )


@pytest.mark.skip("Part 5")
def test_epic_rollup() -> None:
    """An epic's status comes from the tasks under it, and the next leaf is found depth first."""
    board = [
        task("T-9", priority=4),
        task("E-1", "done", priority=6),
        task("S-11", parent="E-1"),
        task("T-111", "done", parent="S-11"),
        task("T-112", "blocked", parent="S-11"),
        task("T-113", parent="S-11"),
        task("T-110", parent="S-11"),
        task("E-2", priority=5),
        task("T-21", parent="E-2"),
        task("T-22", owner="human", parent="E-2", priority=9),
        task("T-23", parent="E-2", priority=3),
        task("E-3", "in_progress"),
        task("T-31", "done", parent="E-3"),
        task("T-32", "done", parent="E-3"),
        task("E-4"),
        task("T-41", "done", parent="E-4"),
        task("T-42", parent="E-4"),
    ]
    report = roll_up(board)
    assert report.status == {
        "T-9": "todo", "E-1": "blocked", "S-11": "blocked", "T-111": "done", "T-112": "blocked",
        "T-113": "todo", "T-110": "todo", "E-2": "todo", "T-21": "todo", "T-22": "todo", "T-23": "todo",
        "E-3": "done", "T-31": "done", "T-32": "done", "E-4": "in_progress", "T-41": "done", "T-42": "todo",
    }, "an epic is done when everything under it is, blocked when anything is, in progress once work started"
    assert report.conflicts == [
        ("E-1", "done", "blocked"),
        ("S-11", "todo", "blocked"),
        ("E-3", "in_progress", "done"),
        ("E-4", "todo", "in_progress"),
    ], "every epic whose own status disagrees, in board order"
    assert report.next_leaf == "T-113", (
        "depth first, the most important branch first, even when it is blocked; board order on ties"
    )
    assert roll_up([task("E-5"), task("T-51", owner="human", parent="E-5")]).next_leaf is None, (
        "only the builder's leaves are next"
    )

    with pytest.raises(ValueError) as err:
        roll_up([task("E-6"), task("T-61", parent="E-9")])
    assert "T-61" in str(err.value), "name the task whose parent is missing"
    with pytest.raises(ValueError) as err:
        roll_up([task("E-7"), task("T-71", parent="T-72"), task("T-72", parent="T-71")])
    assert "T-71" in str(err.value) or "T-72" in str(err.value), "name a task on the loop of parents"
