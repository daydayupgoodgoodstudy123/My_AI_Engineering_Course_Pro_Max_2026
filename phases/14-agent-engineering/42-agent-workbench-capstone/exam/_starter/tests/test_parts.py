import hashlib
import time
from pathlib import Path

import pytest
from wbpack.install import install, preview_paths
from wbpack.manifest import FileEntry, Manifest, load_manifest, save_manifest, verify_manifest
from wbpack.upgrade import release_allowed, required_bump, upgrade_plan
from wbpack.stream import Operation, stream_install
from wbpack.components import Component, resolve_components


def put(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def entry(path, body=b"x", mode=0o644, component="docs"):
    return FileEntry(path, hashlib.sha256(body).hexdigest(), mode, component)


@pytest.mark.skip("Part 1")
def test_install_contract(tmp_path) -> None:
    """Install only pack-owned paths, refuse overwrite and publish a truthful version."""
    pack = {"docs/guide.md": b"guide", "scripts/check.py": b"check"}
    first = tmp_path / "first"
    (first / ".github").mkdir(parents=True)
    receipt = install(first, pack, "1.0.0")
    assert not receipt.ci_wired, "CI requires an existing workflows directory"
    assert (first / "docs/guide.md").read_bytes() == b"guide", "copy every selected file"

    occupied = tmp_path / "occupied"
    put(occupied, "docs/guide.md", b"team rules")
    try:
        install(occupied, pack, "1.0.0")
    except FileExistsError:
        pass
    else:
        assert False, "refuse to replace any managed file without force"
    assert (occupied / "docs/guide.md").read_bytes() == b"team rules", "refusal is read-only"
    put(occupied, "docs/local/guide.md", b"team notes")
    put(occupied, "scripts/user.py", b"user code")
    receipt = install(occupied, pack, "1.0.0", force=True)
    assert receipt.unmanaged == ("docs/local/guide.md", "scripts/user.py"), (
        "report every unmanaged relative path, including matching basenames"
    )
    assert (occupied / "docs/local/guide.md").is_file() and (occupied / "docs/local/guide.md").read_bytes() == b"team notes", "force retains user files"
    assert (occupied / "scripts/user.py").is_file() and (occupied / "scripts/user.py").read_bytes() == b"user code", "force retains user files"

    broken = tmp_path / "broken"
    put(broken, ".workbench-version", b"1.0.0\n")
    copied = []
    def fail_second(path, body):
        if copied:
            raise OSError("disk full")
        put(broken, path.relative_to(broken).as_posix(), body)
        copied.append(path)
    with pytest.raises(OSError, match="disk full"):
        install(broken, pack, "2.0.0", force=True, writer=fail_second)
    assert (broken / ".workbench-version").read_text() == "1.0.0\n", (
        "a failed copy must not publish the new version"
    )
    ready = tmp_path / "ready"
    (ready / ".github/workflows").mkdir(parents=True)
    good = install(ready, pack, "1.1.0")
    assert good.ci_wired and (ready / ".github/workflows/workbench.yml").exists(), (
        "wire CI when workflows already exists"
    )
    assert (ready / ".workbench-version").read_text() == "1.1.0\n", "publish a successful version"

    inventory = [f"docs/local/{i}.md" for i in range(24000)]
    managed = [f"schemas/schema-{i}.json" for i in range(2200)]
    start = time.perf_counter()
    preview = preview_paths(managed, inventory)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.08, "preview must scale with the inventory plus the pack"
    assert preview == dict.fromkeys(managed, False), "preview reflects actual path presence"
    assert preview_paths(["docs/a.md", "scripts/a.md", "z"], ["scripts/a.md", "z"]) == {
        "docs/a.md": False, "scripts/a.md": True, "z": True
    }, "a basename match is not a managed-path match"


@pytest.mark.skip("Part 2")
def test_manifest_roundtrip(tmp_path) -> None:
    """A quoted TSV manifest preserves file identity and reports all damaged files."""
    rows = (
        entry("docs/团队 rules.md", b"rules", 0o640, "docs"),
        entry("scripts/init agent.py", b"init", 0o755, "scripts"),
        entry("schemas/state.json", b"{}", 0o600, "schemas"),
    )
    original = Manifest("1.10.3", rows)
    store = tmp_path / "metadata"
    save_manifest(store, original)
    assert load_manifest(store) == original, "manifest fields must round-trip exactly"
    text = (store / "MANIFEST.tsv").read_text(encoding="utf-8")
    assert "\t0755\t" in text, "permission bits are written in octal"
    for row, body in zip(rows, (b"rules", b"init", b"{}")):
        put(tmp_path / "repo", row.path, body)
    assert verify_manifest(tmp_path / "repo", original) == [], "verify the complete original pack"
    put(tmp_path / "repo", rows[0].path, b"edited")
    (tmp_path / "repo" / rows[2].path).unlink()
    assert verify_manifest(tmp_path / "repo", original) == [rows[0].path, rows[2].path], (
        "report every digest mismatch or missing path in manifest order"
    )
    replacement = Manifest("2.0.0", (rows[1],))
    save_manifest(store, replacement)
    assert load_manifest(store) == replacement, "saving replaces the manifest rather than appending"
    empty = Manifest("2.0.1", ())
    save_manifest(store, empty)
    assert load_manifest(store) == empty, "an empty manifest still pins its version"


@pytest.mark.skip("Part 3")
def test_release_and_three_way_upgrade() -> None:
    """Classify a release and preserve local edits during a three-way upgrade."""
    docs = entry("docs/rules.md", b"old")
    newdocs = entry("docs/rules.md", b"new")
    script = entry("scripts/init.py", b"old", 0o755, "scripts")
    newscript = entry("scripts/init.py", b"new", 0o755, "scripts")
    schema = entry("schemas/state.json", b"{}", component="schemas")
    base = Manifest("1.9.3", (docs, script, schema))
    assert required_bump(base, base, set()) == "none", "no file change needs no release bump"
    assert required_bump(base, Manifest("", (newdocs, script, schema)), set()) == "patch", (
        "doc-only changes require a patch"
    )
    assert required_bump(base, Manifest("", (newdocs, newscript, schema)), set()) == "minor", (
        "non-migrating runtime changes require a minor"
    )
    assert required_bump(base, Manifest("", (docs, newscript, schema)), {script.path}) == "major", (
        "migration-requiring script changes require a major"
    )
    assert required_bump(base, Manifest("", (docs, script)), set()) == "major", (
        "schema removal is still a schema change"
    )
    mode_changed = FileEntry(script.path, script.sha256, 0o644, script.component)
    assert required_bump(base, Manifest("", (docs, mode_changed, schema)), set()) == "minor", (
        "permission-only runtime changes still need a release"
    )
    assert release_allowed("1.9.3", "1.10.0", "minor"), "version fields are numeric"
    assert release_allowed("1.9.3", "2.0.0", "major"), "a major resets lower version fields"
    assert release_allowed("1.9.3", "1.9.4", "patch"), "patch increments only patch"
    assert not release_allowed("1.9.3", "1.10.0", "patch"), "doc-only changes use the patch increment"
    assert not release_allowed("1.9.3", "2.9.3", "major"), "release increments must reset lower fields"
    assert release_allowed("1.9.3", "1.9.3", "none"), "unchanged packs keep the version"

    old = dict.fromkeys(("clean", "update", "local", "conflict", "remove", "keep", "gone", "same", "local-delete"), "old")
    local = {**old, "local": "ours", "conflict": "ours", "keep": "ours", "same": "new", "new-clash": "ours", "user": "private"}
    del local["gone"]
    del local["local-delete"]
    incoming = {**old, "update": "new", "conflict": "new", "same": "new", "added": "new", "new-clash": "new"}
    for path in ("remove", "keep", "gone"):
        del incoming[path]
    assert upgrade_plan(old, local, incoming) == sorted({
        "clean": "unchanged", "update": "update", "local": "locally-modified",
        "conflict": "conflict", "remove": "removed", "keep": "locally-modified",
        "gone": "unchanged", "same": "unchanged", "local-delete": "locally-modified",
        "added": "added", "new-clash": "conflict"
    }.items()), "three-way statuses must distinguish upstream changes from local changes"
    assert upgrade_plan({"a": "old"}, {}, {"a": "new"}) == [("a", "conflict")], (
        "a local deletion conflicts with an upstream content change"
    )
    assert upgrade_plan({}, {"new": "x", "private": "y"}, {"new": "x"}) == [("new", "unchanged")], (
        "an incoming file already present is unchanged; user-only files stay outside the plan"
    )


@pytest.mark.skip("Part 4")
def test_incremental_install_log(tmp_path) -> None:
    """Log each completed operation immediately and undo completed writes in reverse."""
    ops = [Operation("add", "docs/new guide.md", b"new"),
           Operation("update", "scripts/init agent.py", b"new init"),
           Operation("remove", "schemas/old state.json"),
           Operation("skip", "docs/local notes.md")]
    expected = [">f+++++++++ docs/new guide.md\n", ">f.st...... scripts/init agent.py\n",
                "*deleting schemas/old state.json\n", "skip docs/local notes.md (locally modified)\n"]
    def seed(root):
        put(root, "scripts/init agent.py", b"old init").chmod(0o751)
        put(root, "schemas/old state.json", b"old schema").chmod(0o640)
        put(root, "docs/local notes.md", b"mine")
    real = tmp_path / "real"
    seed(real)
    pulled = []
    def source():
        for op in ops:
            pulled.append(op.path)
            yield op
    lines = stream_install(real, source())
    assert next(lines) == expected[0] and len(pulled) == 1, "emit after each operation without prefetching"
    assert (real / ops[0].path).read_bytes() == b"new", "the emitted operation has already reached disk"
    assert [expected[0], *lines] == expected, "preserve full paths in itemize lines"
    assert (real / ops[1].path).read_bytes() == b"new init", "update applies new bytes"
    assert not (real / ops[2].path).exists(), "remove applies before its log line"
    assert (real / ops[3].path).read_bytes() == b"mine", "skip is read-only"
    dry = tmp_path / "dry"
    seed(dry)
    assert list(stream_install(dry, ops, dry_run=True, before_write=lambda op: pytest.fail("dry-run called hook"))) == expected, (
        "dry-run uses the same forward lines"
    )
    assert not (dry / ops[0].path).exists() and (dry / ops[1].path).read_bytes() == b"old init", "dry-run makes no writes"
    assert (dry / ops[2].path).read_bytes() == b"old schema", "dry-run preserves removals"
    rollback = tmp_path / "rollback"
    seed(rollback)
    def fail_at_end(op):
        if op.path == "scripts/failing.py":
            raise OSError("disk full")
    failed = stream_install(rollback, [*ops, Operation("add", "scripts/failing.py")], before_write=fail_at_end)
    seen = []
    with pytest.raises(OSError, match="disk full"):
        for line in failed:
            seen.append(line)
            if line.startswith("rollback "):
                rel = line[len("rollback "):-1]
                path = rollback / rel
                expected_before = {
                    "schemas/old state.json": (b"old schema", 0o640),
                    "scripts/init agent.py": (b"old init", 0o751),
                }
                if rel in expected_before:
                    body, mode = expected_before[rel]
                    assert path.is_file() and path.read_bytes() == body and path.stat().st_mode & 0o777 == mode, (
                        "a rollback line follows the completed restoration"
                    )
                else:
                    assert not path.exists(), "a rollback line follows the completed restoration"
    assert seen == [*expected, "rollback schemas/old state.json\n", "rollback scripts/init agent.py\n", "rollback docs/new guide.md\n"], (
        "rollback reverses completed non-skip operations"
    )
    assert not (rollback / ops[0].path).exists(), "rollback removes newly added files"
    assert (rollback / ops[1].path).read_bytes() == b"old init" and (rollback / ops[1].path).stat().st_mode & 0o777 == 0o751, (
        "rollback restores original bytes and permission bits"
    )
    assert (rollback / ops[2].path).read_bytes() == b"old schema" and (rollback / ops[2].path).stat().st_mode & 0o777 == 0o640, (
        "rollback restores a removed file with its mode"
    )
    assert (rollback / ops[3].path).read_bytes() == b"mine" and not (rollback / "scripts/failing.py").exists(), "neither skips nor failed operations enter the undo log"


@pytest.mark.skip("Part 5")
def test_component_reference_closure() -> None:
    """A partial pack includes referenced components and explains excluded dependencies."""
    graph = {
        "router": Component(("AGENTS.md",), ("docs", "runtime")),
        "docs": Component(("docs/rules.md",), ("schemas",)),
        "runtime": Component(("scripts/init.py",), ("schemas",)),
        "schemas": Component(("schemas/state.json",)),
        "project": Component(("task_board.json",)),
        "broken": Component(("docs/unreachable.md",), ("missing",)),
    }
    excluded = {"task_board.json", "scripts/vendor_sdk.py", "docs/onboarding.md"}
    assert resolve_components(graph, ["router", "runtime", "router"], excluded) == ["schemas", "docs", "runtime", "router"], (
        "include every dependency once, before its dependant, preserving reference order"
    )
    assert resolve_components(graph, [], excluded) == [], "unrequested components do not enter a partial pack"
    bad = {**graph, "schemas": Component(("scripts/vendor_sdk.py",))}
    with pytest.raises(ValueError) as caught:
        resolve_components(bad, ["router"], excluded)
    assert "router -> docs -> schemas: scripts/vendor_sdk.py" in str(caught.value), "excluded files need the full reference path"
    later_excluded = {**graph, "schemas": Component(("schemas/state.json", "scripts/vendor_sdk.py"))}
    with pytest.raises(ValueError) as caught:
        resolve_components(later_excluded, ["router"], excluded)
    assert "router -> docs -> schemas: scripts/vendor_sdk.py" in str(caught.value), "every selected file is checked for exclusion"
    with pytest.raises(ValueError) as caught:
        resolve_components(graph, ["project"], excluded)
    assert "project: task_board.json" in str(caught.value), "a directly requested excluded file is still rejected"
    with pytest.raises(ValueError) as caught:
        resolve_components(graph, ["broken"], excluded)
    assert "broken -> missing" in str(caught.value), "missing components need the reference path"
    cycle = {"a": Component((), ("b",)), "b": Component((), ("a",))}
    with pytest.raises(ValueError) as caught:
        resolve_components(cycle, ["a"], set())
    assert "a -> b -> a" in str(caught.value), "cycles need the complete reference path"
    assert resolve_components(graph, ["runtime", "docs"], excluded) == ["schemas", "runtime", "docs"], "request order breaks independent ties"
