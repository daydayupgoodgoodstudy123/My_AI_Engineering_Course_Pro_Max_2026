import asyncio
import copy
import json
import os
import re
import stat
import time
from pathlib import Path

import pytest
from statefile.graph import MigrationGraph
from statefile.manager import StateManager
from statefile.migrate import migrate, upgrade_file, v1_to_v2, v2_to_v3
from statefile.schema import BOARD_SCHEMA, STATE_SCHEMA, SchemaError, VersionError, validate, with_tracked_files
from statefile.sessions import Conflict, RevisionFile, run_sessions
from statefile.snapshot import CorruptSnapshot, Snapshot


def raises(error: type[BaseException], call, *args, **kwargs) -> bool:
    """True when the call raises error. Any other exception propagates."""
    try:
        call(*args, **kwargs)
    except error:
        return True
    return False


def refused(call, *args, **kwargs) -> bool:
    return raises(SchemaError, call, *args, **kwargs)


HAND_EDITED = {
    "schema_version": 3,
    "active_task_id": None,
    "touched_files": [],
    "risks": ["staging db is shared"],
    "next_action": "pick the next task",
    "last_human_touch": 1761998400.25,
}


@pytest.mark.skip("Part 1")
def test_state_manager(tmp_path, monkeypatch) -> None:
    """A bad write is a refused write, a good one round-trips, and validation stays fast on a big repo."""
    path = tmp_path / "agent_state.json"
    path.write_text(json.dumps(HAND_EDITED, indent=2) + "\n", encoding="utf-8")  # a human stamped the edit
    mgr = StateManager(path, STATE_SCHEMA)
    state = mgr.update(active_task_id="T-001", next_action="read the /signup handler")
    assert state == {**HAND_EDITED, "active_task_id": "T-001", "next_action": "read the /signup handler"}, (
        "update merges the changes into the state on disk"
    )
    assert mgr.load() == state, "update writes the state it returns"
    assert mgr.update(last_human_touch=1762002000)["last_human_touch"] == 1762002000, "a whole number is a JSON number"

    before = path.read_bytes()
    for bad in (
        {"active_task_id": "T-001\n"},
        {"active_task_id": "T-01"},
        {"active_task_id": ""},
        {"touched_files": None},
        {"risks": ["db down", 7]},
        {"last_human_touch": True},
        {"last_human_touch": float("nan")},
        {"last_human_touch": float("inf")},
        {"last_human_touch": "2026-11-01T12:00:00Z"},
        {"schema_version": 3.0},
        {"last_run": "2026-11-01"},
    ):
        assert refused(mgr.update, **bad), f"a bad write is refused: {bad}"
        assert path.read_bytes() == before, "a refused write leaves the file as it was"

    task_id = {"type": "string", "pattern": r"T-\d{3,}|EPIC-\d{2,}"}
    validate("EPIC-07", task_id)
    for bad in ("T-001-old", "xT-001", "EPIC-07\n"):
        assert refused(validate, bad, task_id), f"a pattern must match the whole string: {bad!r}"

    board = [
        {"id": "T-001", "goal": "validate /signup payloads", "owner": "builder",
         "acceptance": ["pytest -x tests/test_signup.py"], "status": "in_progress",
         "priority": 1, "needs_review": True, "estimate_h": 3},
        {"id": "T-002", "goal": "rate-limit /login", "owner": "human", "acceptance": [],
         "status": "todo", "priority": "someday", "labels": ["security"]},
    ]
    boards = StateManager(tmp_path / "task_board.json", BOARD_SCHEMA)
    boards.commit(board)
    assert boards.load() == board, "tasks may carry fields of the team's own"
    ref = {"type": "object", "properties": {"id": {"type": "string"}}}
    assert not refused(validate, {"id": "T-003", "sprint": 12}, ref), (
        "without additionalProperties: false, other keys are allowed"
    )
    for bad in ({"priority": True}, {"priority": 4}, {"needs_review": 1}, {"owner": "Human"}, {"status": None}):
        assert refused(boards.commit, [board[0], {**board[1], **bad}]), f"a bad task is refused: {bad}"
    boards.commit([board[0], {**board[1], "priority": 2.0}])
    assert boards.load()[1]["priority"] == 2.0, "2.0 is the number 2"

    nested = {"enum": ["x", [1.0, {"a": [True], "b": 2}]]}
    validate([1, {"b": 2.0, "a": [True]}], nested)
    for bad in ([1, {"a": [1], "b": 2}], [True, {"a": [True], "b": 2}], "y"):
        assert refused(validate, bad, nested), f"enum compares JSON values: {bad!r}"
    assert refused(validate, 0, {"enum": [False, "0", None]}) and refused(validate, False, {"enum": [0, ""]}), (
        "a boolean is never a number"
    )

    tracked = [f"pkg{i // 100:02d}/module_{i:05d}.py" for i in range(6000)]
    repo = with_tracked_files(STATE_SCHEMA, tracked)
    codemod = {**state, "touched_files": tracked[-2000:]}
    start = time.perf_counter()
    validate(codemod, repo)
    elapsed = time.perf_counter() - start
    assert refused(validate, {**state, "touched_files": [tracked[0], "src/sigup.py"]}, repo), (
        "touched files must be files the repo tracks"
    )
    assert elapsed < 0.15, "validation stays fast on a big repo"
    repo["properties"]["touched_files"]["items"]["enum"][0] = "docs/new.md"  # the repo renamed a file
    assert not refused(validate, {**state, "touched_files": ["docs/new.md"]}, repo), (
        "validate reads the schema as it is at the time of the call"
    )


    preserved = path.read_bytes()
    assert refused(mgr.update, next_action="do not persist this prefix", last_human_touch="invalid timestamp"), (
        "the whole changes request is refused when a later field is invalid"
    )
    assert path.read_bytes() == preserved, "a refused multi-field update persists no prefix"

    replaced: list[tuple[Path, Path]] = []
    real_replace = os.replace
    def recording_replace(src, dst):
        replaced.append((Path(src), Path(dst)))
        return real_replace(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", recording_replace)
        complete = mgr.update(next_action="review the complete checkpoint", risks=["review pending"])
        assert complete["next_action"] == "review the complete checkpoint" and complete["risks"] == ["review pending"], (
            "every field belongs to the same completed update"
        )
        assert len(replaced) == 1 and replaced[0][1] == path, "one nonempty update replaces the state once"
        replaced.clear()
        assert mgr.update() == complete and replaced == [], "an empty update validates and returns without replacing"

    # A repo-wide review records one finite status/proof pair for each component.
    # The source's touched-file list stays ordinary state, not generated artifact contents.
    checkpoints = {f"component_{i:03d}": {"status": "reviewed", "proof": f"check component {i}"} for i in range(256)}
    checkpoint_schema = copy.deepcopy(STATE_SCHEMA)
    checkpoint_schema["properties"].update({key: {
        "type": "object", "required": ["status", "proof"], "additionalProperties": False,
        "properties": {"status": {"type": "string"}, "proof": {"type": "string"}},
    } for key in checkpoints})
    checkpoint_manager = StateManager(tmp_path / "review_state.json", checkpoint_schema)
    checkpoint_manager.commit(codemod)
    start = time.perf_counter()
    batched = checkpoint_manager.update(**checkpoints)
    batch_elapsed = time.perf_counter() - start
    assert all(batched[key] == value for key, value in checkpoints.items()) and checkpoint_manager.load() == batched, (
        "a multi-component checkpoint keeps every result and existing state"
    )
    assert batch_elapsed < 0.03, "a checkpoint request is encoded and persisted as one state transition"


class Crash(BaseException):
    """Stands in for the process dying on the spot (kill -9, a power cut)."""


def exact(a, b) -> bool:
    """The same JSON value with the same Python types and key order; -0.0 is not 0.0."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return repr(a) == repr(b)
    return a == b


DOC = {
    "schema_version": 3,
    "next_action": "réviser /signup, puis 下一步 🧠",
    "touched_files": ["src/app.py", "docs/naïve.md"],
    "notes": "LS inside, a tab\there, a quote \" and a backslash \\",
    "counters": {"tool_calls": 2**63 + 1, "offset": -0.0, "ratio": 0.1 + 0.2, "tiny": 5e-324},
    "zeta": {"b": 2, "a": 1},
    "flags": [True, 1, 1.0, 0, False, None],
    "empty": {"list": [], "object": {}},
}


@pytest.mark.skip("Part 2")
def test_snapshot_durability(tmp_path, monkeypatch) -> None:
    """A snapshot is replaced whole or not at all, survives a crash anywhere, and reads back exactly."""
    path = tmp_path / "agent_state.json"
    calls: list[tuple] = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            calls.append(("dir", info.st_ino))
        else:
            calls.append(("file", info.st_ino, info.st_size))  # what the file holds when it is fsynced
        real_fsync(fd)

    def replace(src, dst):
        calls.append(("replace", Path(src), Path(dst), stat.S_IMODE(os.stat(src).st_mode)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)

    assert Snapshot(path).save(DOC) is True, "the first save writes"
    assert path.read_bytes() == (json.dumps(DOC, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), (
        "the file is UTF-8 JSON indented by 2, keys in order, non-ASCII as is, one newline at the end"
    )
    assert exact(Snapshot(path).load(), DOC), "a snapshot reads back exactly"
    renames = [call for call in calls if call[0] == "replace"]
    assert len(renames) == 1 and renames[0][2] == path, "save renames one temporary file over the target"
    temp = renames[0][1]
    assert temp.parent == tmp_path and re.fullmatch(r"agent_state\.json\..+\.tmp", temp.name), (
        "the temporary file sits next to the target, named <file name>.<random>.tmp"
    )
    at = calls.index(renames[0])
    new = os.stat(path)
    assert ("file", new.st_ino, new.st_size) in calls[:at], "the new file is flushed and fsynced before the rename"
    assert ("dir", os.stat(tmp_path).st_ino) in calls[at + 1 :], "the directory is fsynced after the rename"
    assert renames[0][3] == stat.S_IMODE(new.st_mode) == 0o644, (
        "a new snapshot is readable by the team (0o644) from the moment it is renamed into place"
    )

    calls.clear()
    inode = os.stat(path).st_ino
    assert Snapshot(path).save(copy.deepcopy(DOC)) is False, "saving the same document again writes nothing"
    assert calls == [] and os.stat(path).st_ino == inode, "saving the same document again writes nothing"
    snap = Snapshot(path)
    for what, doc in (
        ("1 became true", {**DOC, "flags": [True, True, 1.0, 0, False, None]}),
        ("-0.0 became 0.0", {**DOC, "counters": {**DOC["counters"], "offset": 0.0}}),
        ("the keys changed order", dict(reversed(DOC.items()))),
    ):
        assert snap.save(doc) is True, f"a change that == cannot see is still a change: {what}"
        assert exact(snap.load(), doc), "a snapshot reads back exactly"
    assert snap.save(DOC) is True
    path.write_text('{"schema_version": 3}\n', encoding="utf-8")  # a human rewrites the file
    assert snap.save(DOC) is True and exact(snap.load(), DOC), (
        "save compares with the file on disk, not with what it saved last"
    )

    os.chmod(path, 0o640)
    last = {**DOC, "next_action": "ship it"}
    assert snap.save(last) is True
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640, "a save keeps the permission bits of the file it replaces"

    before = path.read_bytes()
    with pytest.raises(TypeError):
        snap.save({**DOC, "touched_files": {"src/app.py"}})
    with pytest.raises(ValueError):
        snap.save({**DOC, "last_human_touch": float("nan")})
    assert path.read_bytes() == before and os.listdir(tmp_path) == ["agent_state.json"], (
        "a save that fails leaves the old file and no temporary file"
    )

    def crash(*args):
        raise Crash

    def crash_on_dir(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise Crash
        fsync(fd)

    for name, fake, real in (("fsync", crash, fsync), ("replace", crash, replace)):
        monkeypatch.setattr(os, name, fake)
        with pytest.raises(Crash):
            Snapshot(path).save({**DOC, "next_action": "half done"})
        monkeypatch.setattr(os, name, real)
        assert exact(Snapshot(path).load(), last), f"a crash before the rename keeps the old snapshot (os.{name})"
        assert os.listdir(tmp_path) == ["agent_state.json"], "opening clears what a crashed save left behind"
    monkeypatch.setattr(os, "fsync", crash_on_dir)
    with pytest.raises(Crash):
        Snapshot(path).save(DOC)
    monkeypatch.setattr(os, "fsync", fsync)
    assert exact(Snapshot(path).load(), DOC), "once renamed, the new snapshot is the one on disk"

    for name, text in (
        ("agent_state.json.k2j3h4ab.tmp", '{"half": '),
        ("agent_state.json.orig", "a human's backup"),
        ("task_board.json.x9y8z7wq.tmp", "["),
        ("old.agent_state.json.ab12cd34.tmp", "{"),
    ):
        (tmp_path / name).write_text(text, encoding="utf-8")
    Snapshot(path)
    assert sorted(os.listdir(tmp_path)) == [
        "agent_state.json",
        "agent_state.json.orig",
        "old.agent_state.json.ab12cd34.tmp",
        "task_board.json.x9y8z7wq.tmp",
    ], "opening removes this file's leftover temporary files, and nothing else"

    for raw in (
        b'{"schema_version": 3, "next_',
        b"",
        b'{"next_action": "caf\xe9"}\n',
        b'{"last_human_touch": NaN}\n',
        b'{"last_human_touch": -Infinity}\n',
    ):
        path.write_bytes(raw)
        with pytest.raises(CorruptSnapshot):
            Snapshot(path).load()
        assert path.read_bytes() == raw, "a corrupt snapshot is left for a human to look at"
    with pytest.raises(FileNotFoundError):
        Snapshot(tmp_path / "never_saved.json").load()


V1 = {
    "schema_version": 1,
    "active_task_id": "",
    "touched_files": ["src/app.py"],
    "assumptions": ["python 3.12"],
    "blockers": ["db down", "auth flaky"],
    "next_action": "fix /signup",
}
V3 = {
    "schema_version": 3,
    "active_task_id": None,
    "touched_files": ["src/app.py"],
    "assumptions": ["python 3.12"],
    "next_action": "fix /signup",
    "risks": ["db down", "auth flaky"],
    "last_human_touch": None,
}


@pytest.mark.skip("Part 3")
def test_migration_chain(tmp_path, monkeypatch) -> None:
    """Old state files reach the current version one checked step at a time, or not at all."""
    doc = copy.deepcopy(V1)
    assert migrate(doc) == V3, "a v1 file becomes v3"
    assert doc == V1, "migrate never changes the caller's document"
    v2 = {key: value for key, value in V1.items() if key != "blockers"}
    assert migrate(V1, target=2) == {**v2, "schema_version": 2, "risks": ["db down", "auth flaky"]}, (
        "migrate stops at the target"
    )

    seen: list[tuple[int, int]] = []

    def spy(step, fn):
        def run(d):
            seen.append((step, d["schema_version"]))
            return fn(d)

        return run

    def annotate(d):  # a step that also notes how the file got here
        d["assumptions"].append("migrated from v1")
        return v1_to_v2(d)

    chain = {1: spy(1, annotate), 2: spy(2, v2_to_v3)}
    doc = copy.deepcopy(V1)
    out = migrate(doc, migrations=chain)
    assert seen == [(1, 1), (2, 2)], "every step runs, in order, on the version it migrates from"
    assert out["assumptions"] == ["python 3.12", "migrated from v1"] and doc == V1, (
        "migrate never changes the caller's document"
    )
    current = migrate(out)
    assert current == out and current is not out and current["assumptions"] is not out["assumptions"], (
        "a document already at the target comes back as a copy"
    )

    no_version = {key: value for key, value in V1.items() if key != "schema_version"}
    for bad in (no_version, {**V1, "schema_version": "1"}, {**V1, "schema_version": 0}, {**V3, "schema_version": 4}):
        assert raises(VersionError, migrate, bad), (
            f"a version it cannot migrate is refused: {bad.get('schema_version')!r}"
        )
    assert raises(VersionError, migrate, V3, target=2), "there are no downgrades"
    assert raises(VersionError, migrate, V1, migrations={1: v1_to_v2}), "a missing step is refused"

    seen.clear()
    assert refused(migrate, {**V1, "touched_files": None}, migrations=chain), (
        "the input is validated against its own version"
    )
    assert seen == [], "an invalid document is refused before any step runs"
    assert refused(migrate, {**V3, "risks": None}), "a document already at the target is validated too"

    def lossy(d):  # drops next_action; the next step happens to put one back
        d = v1_to_v2(d)
        del d["next_action"]
        return d

    def refill(d):
        d.setdefault("next_action", "pick the next task")
        return v2_to_v3(d)

    assert refused(migrate, V1, migrations={1: lossy, 2: refill}), (
        "every step's result is checked against its own version's schema"
    )

    def jumps(d):  # claims to have produced v3
        d = v1_to_v2(d)
        d["schema_version"] = 3
        return d

    def leaps(d):  # does both bumps in one step
        return v2_to_v3(v1_to_v2(d))

    for step in (jumps, leaps):
        assert refused(migrate, V1, migrations={1: step, 2: v2_to_v3}), (
            f"a step must produce the next version: {step.__name__}"
        )

    path = tmp_path / "agent_state.json"
    path.write_text(json.dumps(V1, indent=2) + "\n", encoding="utf-8")
    renamed: list[Path] = []
    real_replace = os.replace

    def replace(src, dst):
        renamed.append(Path(dst))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)

    def broken(d):
        raise RuntimeError("bug in the v2 -> v3 script")

    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        upgrade_file(path, migrations={1: v1_to_v2, 2: broken})
    assert path.read_bytes() == before and renamed == [], "a failed upgrade leaves the file exactly as it was"
    assert upgrade_file(path) == (1, 3), "upgrade_file reports the version found and the version reached"
    assert json.loads(path.read_text(encoding="utf-8")) == V3 and renamed == [path], (
        "the upgraded file is written once, atomically"
    )
    assert upgrade_file(path) == (3, 3) and renamed == [path], "a file already at the current version is not rewritten"
    path.write_text(json.dumps({**V3, "schema_version": 4}) + "\n", encoding="utf-8")
    before = path.read_bytes()
    assert raises(VersionError, upgrade_file, path) and path.read_bytes() == before, (
        "a file from a newer version is refused and left alone"
    )
    assert os.listdir(tmp_path) == ["agent_state.json"], "no temporary file is left behind"


START = {"touched_files": [], "risks": [], "next_action": "pick the next task"}


def events(lines: list[str]) -> list[dict]:
    assert all(isinstance(line, str) and line.endswith("\n") and line.count("\n") == 1 for line in lines), (
        "one line of JSON per attempt"
    )
    return [json.loads(line) for line in "".join(lines).splitlines()]


@pytest.mark.skip("Part 4")
def test_concurrent_sessions(tmp_path, monkeypatch) -> None:
    """Sessions sharing a state file never lose each other's writes, and every attempt is reported as it happens."""
    path = tmp_path / "agent_state.json"
    renamed: list[Path] = []
    real_replace = os.replace

    def replace(src, dst):
        renamed.append(Path(dst))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    a, b = RevisionFile(path), RevisionFile(path)
    assert a.read() == (0, None), "a missing file is revision 0"
    assert a.commit(0, START) == 1, "each commit adds 1 to the revision"
    assert renamed == [path], "a commit replaces the file atomically"
    rev_a, state_a = a.read()
    rev_b, state_b = b.read()
    state_b["risks"].append("db down")
    assert b.commit(rev_b, state_b) == 2, "each commit adds 1 to the revision"
    state_a["touched_files"].append("src/app.py")
    before = path.read_bytes()
    with pytest.raises(Conflict):
        a.commit(rev_a, state_a)
    assert path.read_bytes() == before, "a commit from a stale read writes nothing"
    assert RevisionFile(path).read() == (2, {**START, "risks": ["db down"]})

    calls: list[tuple[str, list[str]]] = []

    async def race() -> list[str]:
        release, retry = asyncio.Event(), asyncio.Event()  # each builder turn waits until the line before it is out

        async def builder(state):
            again = any(who == "builder" for who, _ in calls)
            calls.append(("builder", list(state["touched_files"])))
            await (retry if again else release).wait()
            state["touched_files"].append("src/app.py")
            return state

        async def reviewer(state):
            calls.append(("reviewer", list(state["touched_files"])))
            await asyncio.sleep(0)
            state["touched_files"].append("tests/test_app.py")
            return state

        stream = run_sessions(path, {"builder": builder, "reviewer": reviewer})
        lines = []
        for gate in (release, retry):
            try:
                lines.append(await asyncio.wait_for(stream.__anext__(), 1.0))
            except asyncio.TimeoutError:
                pytest.fail("each attempt is reported as soon as it is decided")
            except StopAsyncIteration:
                break
            gate.set()
        return lines + [line async for line in stream]

    assert events(asyncio.run(race())) == [
        {"session": "reviewer", "attempt": 1, "base": 2, "revision": 3, "result": "committed"},
        {"session": "builder", "attempt": 1, "base": 2, "revision": 3, "result": "conflict"},
        {"session": "builder", "attempt": 2, "base": 3, "revision": 4, "result": "committed"},
    ], "the session that lost the race reads again and commits on top"
    assert calls == [("builder", []), ("reviewer", []), ("builder", ["tests/test_app.py"])], (
        "a conflict reruns the turn on the fresh state"
    )
    both = {**START, "risks": ["db down"], "touched_files": ["tests/test_app.py", "src/app.py"]}
    assert RevisionFile(path).read() == (4, both), "no session's write is lost"

    async def contended() -> tuple[list[str], list[str]]:
        human = RevisionFile(path)
        seen: list[str] = []

        async def planner(state):
            seen.append(state["next_action"])
            assert len(seen) <= 2, "a session gives up after max_attempts attempts"
            for _ in range(2):  # a human saves the file twice while the planner thinks
                revision, other = human.read()
                other["next_action"] = f"human edit {len(seen)}"
                human.commit(revision, other)
            await asyncio.sleep(0)
            state["touched_files"].append("plan.md")
            return state

        lines = [line async for line in run_sessions(path, {"planner": planner}, max_attempts=2)]
        return lines, seen

    lines, seen = asyncio.run(contended())
    assert events(lines) == [
        {"session": "planner", "attempt": 1, "base": 4, "revision": 6, "result": "conflict"},
        {"session": "planner", "attempt": 2, "base": 6, "revision": 8, "result": "gave_up"},
    ], "a session gives up after max_attempts attempts; a conflict reports the revision it found on disk"
    assert seen == ["pick the next task", "human edit 1"], "every attempt starts from a fresh read"
    assert RevisionFile(path).read() == (8, {**both, "next_action": "human edit 2"}), (
        "a session that gives up writes nothing"
    )


FIELDS = {
    "active_task_id": {"type": ["string", "null"], "pattern": r"^(T-\d{3,}|)$"},
    "task": {"type": ["string", "null"], "pattern": r"^T-\d{3,}$"},
    "touched_files": {"type": "array", "items": {"type": "string"}},
    "blockers": {"type": "array", "items": {"type": "string"}},
    "risks": {"type": "array", "items": {"type": "string"}},
    "next_action": {"type": "string"},
    "last_human_touch": {"type": ["number", "null"]},
}


def schema(version: int, *names: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", *names],
        "properties": {"schema_version": {"type": "integer", "enum": [version]}, **{n: FIELDS[n] for n in names}},
    }


HISTORY = {
    1: schema(1, "active_task_id", "touched_files", "blockers", "next_action"),
    2: schema(2, "active_task_id", "touched_files", "risks", "next_action"),  # team A: blockers -> risks
    3: schema(3, "active_task_id", "touched_files", "blockers", "next_action", "last_human_touch"),  # team B
    4: schema(4, "active_task_id", "touched_files", "risks", "next_action", "last_human_touch"),  # the merge
    5: schema(5, "task", "touched_files", "risks", "next_action", "last_human_touch"),
}


def rename(old: str, new: str, version: int):
    def step(d):
        d[new] = d.pop(old)
        d["schema_version"] = version
        return d

    return step


def stamp(version: int):
    def step(d):
        d["last_human_touch"] = None
        d["schema_version"] = version
        return d

    return step


def shortcut(d):
    d = rename("blockers", "risks", 4)(d)
    d["last_human_touch"] = None
    return d


def to_v5(d):
    d["task"] = d.pop("active_task_id") or None
    d["schema_version"] = 5
    return d


OLD = {
    "schema_version": 1,
    "active_task_id": "",
    "touched_files": ["src/app.py"],
    "blockers": ["db down", "auth flaky"],
    "next_action": "fix /signup",
}
NEW = {
    "schema_version": 5,
    "task": None,
    "touched_files": ["src/app.py"],
    "risks": ["db down", "auth flaky"],
    "next_action": "fix /signup",
    "last_human_touch": None,
}


@pytest.mark.skip("Part 5")
def test_migration_graph() -> None:
    """Versions branch, merge and get shortcuts: take the shortest way up, and prove every way agrees."""
    ran: list[tuple[int, int]] = []

    def build(steps: dict) -> MigrationGraph:
        graph = MigrationGraph(HISTORY)
        for (src, dst), fn in steps.items():

            def logged(d, src=src, dst=dst, fn=fn):
                ran.append((src, dst))
                return fn(d)

            graph.add(src, dst, logged)
        return graph

    steps = {  # registered in this order on purpose
        (1, 3): stamp(3),
        (3, 4): rename("blockers", "risks", 4),
        (1, 2): rename("blockers", "risks", 2),
        (2, 4): stamp(4),
        (4, 5): to_v5,
    }
    chains = build(steps)
    assert chains.path(1, 4) == [(1, 2), (2, 4)], "among equally short paths, the smaller versions come first"
    assert chains.path(1, 3) == [(1, 3)] and chains.path(3, 5) == [(3, 4), (4, 5)]
    assert chains.path(5, 5) == [], "a document already at the target needs no steps"
    for start, target in ((2, 3), (4, 1), (1, 6), (0, 5)):
        assert raises(VersionError, chains.path, start, target), f"no way from {start} to {target}"

    graph = build({**steps, (1, 4): shortcut})
    assert graph.path(1, 4) == [(1, 4)] and graph.path(1, 5) == [(1, 4), (4, 5)], (
        "the fewest migrations win, shortcuts included"
    )
    doc = copy.deepcopy(OLD)
    ran.clear()
    assert graph.upgrade(doc, 5) == NEW and ran == [(1, 4), (4, 5)], "upgrade follows the shortest path"
    assert doc == OLD, "upgrade never changes the caller's document"
    ran.clear()
    assert refused(graph.upgrade, {**OLD, "touched_files": None}, 5) and ran == [], (
        "a document that breaks its own version's schema is refused before any step runs"
    )
    v2 ={**rename("blockers", "risks", 2)(copy.deepcopy(OLD))}
    assert raises(VersionError, graph.upgrade, v2, 3), "a version on another branch cannot be reached"

    assert graph.disagreements(OLD, 5) == [], "the shortcut and both chains give the same document"
    assert graph.disagreements(NEW, 5) == []

    def tidy_shortcut(d):  # someone sorted the risks in the shortcut only
        d = shortcut(d)
        d["risks"].sort()
        return d

    tidy = build({**steps, (1, 4): tidy_shortcut})
    assert tidy.disagreements(OLD, 5) == [
        [(1, 2), (2, 4), (4, 5)],
        [(1, 3), (3, 4), (4, 5)],
    ], "every path that disagrees with the planned one, in order"

    def lossy_merge(d):  # team B's merge step drops the touched files
        d = rename("blockers", "risks", 4)(d)
        d["touched_files"] = []
        return d

    broken = build({**steps, (1, 4): shortcut, (3, 4): lossy_merge})
    assert broken.disagreements(OLD, 5) == [[(1, 3), (3, 4), (4, 5)]], (
        "each path is judged by its own steps, not by a result cached per version"
    )
    assert raises(VersionError, broken.disagreements, v2, 3), "a target that cannot be reached is an error, not []"
