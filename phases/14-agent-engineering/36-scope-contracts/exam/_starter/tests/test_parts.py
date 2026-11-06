import asyncio
import dataclasses
import json
import os
import time
from urllib.parse import unquote

import pytest
from taskscope.archive import ClosedTask, ReportArchive
from taskscope.check import Finding, ScopeReport, scope_check
from taskscope.contract import RunSummary, ScopeContract, merge_contracts
from taskscope.diffscan import scan_diff
from taskscope.globs import compile_glob, normalize_path
from taskscope.layers import Explanation, resolve_chain


def contract(task_id: str, allowed, forbidden=(), **fields) -> ScopeContract:
    """A contract with the boilerplate fields filled in."""
    fields.setdefault("goal", f"work on {task_id}")
    fields.setdefault("acceptance_criteria", [])
    fields.setdefault("rollback_plan", "git revert the merge commit")
    return ScopeContract(task_id=task_id, allowed_files=list(allowed), forbidden_files=list(forbidden), **fields)


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(data: bytes, size: int):
    for start in range(0, len(data), size):
        yield data[start : start + size]


def raises(error: type[BaseException], call, *args) -> bool:
    """True when call(*args) raises error. Any other exception goes through."""
    try:
        call(*args)
    except error:
        return True
    return False


def results_of(lines: list[str]) -> list[dict]:
    return [json.loads(line) for line in "".join(lines).splitlines()]


def uri_of(result: dict) -> str:
    return result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]


def summary(results: list[dict]) -> list[tuple[str, str, str]]:
    return [(r["ruleId"], r["level"], unquote(uri_of(r))) for r in results]


@pytest.mark.skip("Part 1")
def test_scope_check() -> None:
    """Contracts merge by least privilege, and the checker counts and compares as its docstring says."""
    project = contract(
        "knowledge-base", ["app.py", "tests/test_*.py", "lib/**/*.py"], ["scripts/release.sh", "config/prod.yaml"],
        altitude="project", approvals_required=["any new runtime dependency"], time_budget_minutes=60,
        network_egress=["api.anthropic.com", "pypi.org", "files.pythonhosted.org"], violation_budget=2,
    )
    task = contract(
        "T-001", ["app.py", "lib/upload/*.py", "tests/test_upload*.py", "tools/*.py"], ["migrations/**"],
        goal="validate PDF uploads", acceptance_criteria=["pytest -x tests/test_upload.py"],
        time_budget_minutes=30, network_egress=["api.anthropic.com", "pypi.org"], violation_budget=3,
        parent="import-pdf",
    )
    effective = merge_contracts(project, task)
    accepted = ["pytest -x tests/test_upload.py"]
    report = scope_check(effective, RunSummary(
        touched_files=[
            "app.py", "lib/upload/pdf.py", "tests/test_upload_pdf.py", "lib/search/index.py", "tools/bump.py",
            "migrations/0002_add_size.sql", "scripts/release.sh", "docs/upload.md", "README.md", "lib/upload/pdf.py",
        ],
        commands_run=accepted,
        elapsed_minutes=30.0,
    ))
    assert report.off_scope_writes == ["lib/search/index.py", "tools/bump.py"], (
        "a path is in scope only when both contracts allow it"
    )
    assert report.in_scope_writes == ["app.py", "lib/upload/pdf.py", "tests/test_upload_pdf.py"], (
        "a path both contracts allow is in scope, once"
    )
    assert report.forbidden_writes == ["migrations/0002_add_size.sql", "scripts/release.sh"], "either contract can forbid"
    assert report.soft_off_scope_writes == ["docs/upload.md", "README.md"], "docs paths outside the contract are soft"
    assert [(f.code, f.severity) for f in report.findings] == [
        ("scope.forbidden", "block"), ("scope.off_scope", "warn"), ("scope.soft_off_scope", "info"),
    ], "one finding per kind; 30 minutes fits a 30-minute budget"
    read_only = merge_contracts(project, contract("T-002", [], goal="investigate the upload bug"))
    assert scope_check(read_only, RunSummary(["app.py"], [], 1.0)).off_scope_writes == ["app.py"], (
        "an empty allowed_files allows nothing"
    )
    nested = merge_contracts(contract("org", ["**"], altitude="project"), effective)
    assert scope_check(nested, RunSummary(["tools/bump.py"], accepted, 1.0)).off_scope_writes == ["tools/bump.py"], (
        "a merged contract keeps every allow-list when it is merged again"
    )

    def checked(touched: list[str]) -> ScopeReport:
        return scope_check(effective, RunSummary(touched, accepted, 5.0))

    within = checked(["lib/search/a.py", "docs/a.md", "tools/b.py", "README.md", "lib/search/a.py"])
    assert not within.over_budget and within.passed(), (
        "soft files and repeated touches do not count against the budget"
    )
    assert not checked(["lib/search/a.py", "tools/b.py", "scripts/release.sh"]).over_budget, (
        "forbidden files block on their own; the budget counts off-scope files"
    )
    over = checked(["lib/search/a.py", "tools/b.py", "lib/search/c.py"])
    assert over.over_budget and not over.passed(), "the violation budget counts off-scope files"

    def refused(scope: ScopeContract, hosts: list[str]) -> list[str]:
        found = scope_check(scope, RunSummary([], accepted, 1.0, hosts)).findings
        return [f.detail for f in found if f.code == "network.unallowed_host"]

    assert refused(effective, ["API.Anthropic.com:443", "pypi.org", "PYPI.ORG:443"]) == [], (
        "hosts compare case-insensitively and without a port"
    )
    assert refused(effective, ["files.pythonhosted.org", "api.anthropic.com"]) != [], "both contracts must allow a host"
    local = dataclasses.replace(effective, network_egress=["[2001:db8::7]", "LocalHost"])
    assert refused(local, ["[2001:db8::7]:8443", "[2001:DB8::7]"]) == [], "an IPv6 address keeps its brackets"
    assert refused(local, ["localhost:5432", "LOCALHOST"]) == [], "allowlist entries compare case-insensitively too"
    assert refused(local, ["[2001:db8::8]:443"]) != [], "another IPv6 address is still refused"
    assert refused(dataclasses.replace(effective, network_egress=[]), ["localhost"]) != [], (
        "an empty network_egress allows no host"
    )
    assert refused(dataclasses.replace(effective, network_egress=None), ["anything.example:8080"]) == [], (
        "network_egress None means no enforcement"
    )

    services = [f"services/svc-{i:04d}/**" for i in range(2500)]
    protected = [f"services/svc-{i:04d}/deploy/prod.yaml" for i in range(2000, 2500)]
    platform = contract(
        "monorepo", services + ["tools/*.py", "*.toml"], protected + ["**/secrets/**", "*.lock"],
        altitude="project", violation_budget=5,
    )
    codemod = contract(
        "T-900", ["services/**", "pyproject.toml"], ["services/*/migrations/**"], violation_budget=5, parent="logging-v2",
    )
    touched = [f"services/svc-{2480 + i % 20:04d}/src/handler_{i}.py" for i in range(1700)]
    touched += [
        "services/svc-2484/README.md", "pyproject.toml", "services/svc-2481/secrets/api.key", "poetry.lock",
        "services/svc-2482/deploy/prod.yaml", "services/svc-2483/migrations/0007_index.sql",
    ]
    start = time.perf_counter()
    big = scope_check(merge_contracts(platform, codemod), RunSummary(touched, [], 3.0))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, "scope_check should be fast on large contracts and large diffs"
    assert big.forbidden_writes == touched[-4:], "every forbidden glob still applies, with or without a literal directory"
    assert big.in_scope_writes[-2:] == ["services/svc-2484/README.md", "pyproject.toml"], (
        "a docs path the contract allows is in scope"
    )
    assert len(big.in_scope_writes) == 1702


@pytest.mark.skip("Part 2")
def test_archive_roundtrip(tmp_path) -> None:
    """A closed task comes back exactly as it was closed, and its evidence can never be rewritten."""
    effective = contract(
        "T-001", ["lib/upload/*.py", "app.py"], ["migrations/**", "scripts/release.sh"],
        goal="validate PDF uploads", acceptance_criteria=["pytest -x tests/test_upload.py"],
        rollback_plan='git revert 4f2c1e9, then redeploy tag "v1.4.2"', approvals_required=["any new runtime dependency"],
        network_egress=[], allowed_within=[["app.py", "lib/**/*.py"], ["lib/**", "app.py"]], parent="import-pdf",
    )
    run = RunSummary(
        touched_files=["lib/upload/pdf.py", "docs/café notes.md", "lib/upload/pdf.py", 'docs/"draft".md', "app.py"],
        commands_run=["pytest -x tests/test_upload.py", "ruff check ."],
        elapsed_minutes=0.1 + 0.2,
        network_hosts=["api.anthropic.com:443"],
    )
    report = ScopeReport(
        task_id="T-001",
        in_scope_writes=["lib/upload/pdf.py", "app.py"],
        off_scope_writes=[],
        forbidden_writes=[],
        soft_off_scope_writes=["docs/café notes.md", 'docs/"draft".md'],
        missing_acceptance=[],
        findings=[
            Finding("scope.soft_off_scope", "info", "docs/markdown off-scope: ['docs/café notes.md', 'docs/\"draft\".md']"),
            Finding("network.unallowed_host", "block", "egress to non-allowlisted hosts: ['api.anthropic.com:443']"),
        ],
        over_budget=False,
    )
    closed = ClosedTask(effective, run, report, closed_at=1767225600.1234567)
    archive = ReportArchive(tmp_path)
    path = archive.close(closed)
    assert path == tmp_path / "closed" / "T-001.json", "closed/<task_id>.json under the archive root"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["task_id"] == "T-001" and raw["passed"] is False and raw["closed_at"] == 1767225600.1234567, (
        "auditors read task_id, passed (a JSON boolean) and closed_at at the top level"
    )

    back = ReportArchive(tmp_path).load("T-001")
    assert back.contract.network_egress == [] and back.contract.allowed_within == effective.allowed_within, (
        "the contract comes back as it was: [] is deny-all, and allowed_within keeps every list"
    )
    assert back.run.touched_files == run.touched_files, "the run is evidence: touches stay in order, repeats included"
    assert back.run.elapsed_minutes == 0.1 + 0.2 and back.closed_at == 1767225600.1234567, (
        "numbers come back exactly"
    )
    assert back.report.findings == report.findings, "findings come back as Findings, severity and detail intact"
    assert back == closed, "a closed task round-trips exactly, after a reopen"

    clean = ClosedTask(
        dataclasses.replace(effective, task_id="T-010", network_egress=None, time_budget_minutes=45),
        RunSummary(["app.py", "docs/upload.md"], ["pytest -x tests/test_upload.py"], 12.0),
        ScopeReport("T-010", ["app.py"], [], [], ["docs/upload.md"], [], [
            Finding("scope.soft_off_scope", "info", "docs/markdown off-scope: ['docs/upload.md']"),
        ], False),
        closed_at=1767312000.0,
    )
    archive.close(clean)
    assert json.loads((tmp_path / "closed" / "T-010.json").read_text(encoding="utf-8"))["passed"] is True, (
        "passed is report.passed(): an info finding still passes"
    )
    assert archive.load("T-010") == clean, "network_egress None (no enforcement) stays None"

    before = path.read_bytes()
    assert raises(FileExistsError, archive.close, dataclasses.replace(closed, closed_at=1767229200.0)), (
        "a task is closed once: closing it again raises FileExistsError"
    )
    assert path.read_bytes() == before, "a closed report is never rewritten"

    (tmp_path / "elsewhere" / "closed").mkdir(parents=True)
    planted = tmp_path / "elsewhere" / "closed" / "T-001.json"
    os.symlink(tmp_path / "outside.json", planted)
    assert raises(FileExistsError, ReportArchive(tmp_path / "elsewhere").close, closed), (
        "an existing entry of any kind blocks the close"
    )
    assert not (tmp_path / "outside.json").exists() and planted.is_symlink(), (
        "an existing entry is never followed or replaced"
    )

    broken = ClosedTask(
        effective, dataclasses.replace(run, elapsed_minutes=float("nan")),
        dataclasses.replace(report, task_id="T-003"), closed_at=1767226000.0,
    )
    assert raises(ValueError, archive.close, broken), "the archive holds strict JSON: NaN raises ValueError"
    assert not (tmp_path / "closed" / "T-003.json").exists(), "a failed close leaves nothing behind"
    archive.close(dataclasses.replace(broken, run=run))

    escape = dataclasses.replace(clean, report=dataclasses.replace(clean.report, task_id="../T-004"))
    assert raises(ValueError, archive.close, escape), "'../T-004' is not a plain task id"
    assert not (tmp_path / "T-004.json").exists(), "a bad task id writes nothing"
    for bad in ("T-004/x", "", ".hidden", "T 004"):
        task = dataclasses.replace(clean, report=dataclasses.replace(clean.report, task_id=bad))
        assert raises(ValueError, archive.close, task), f"{bad!r} is not a plain task id"
    assert raises(ValueError, archive.load, "../closed/T-001"), "load takes plain task ids only"
    assert raises(KeyError, archive.load, "T-404"), "an unknown task_id raises KeyError"
    (tmp_path / "closed" / ".T-005.json.tmp").write_text("{}", encoding="utf-8")
    (tmp_path / "closed" / "._T-001.json").write_bytes(b"\x00\x05\x16\x07")
    (tmp_path / "closed" / "notes.txt").write_text("not a report", encoding="utf-8")
    assert ReportArchive(tmp_path).task_ids() == ["T-001", "T-003", "T-010"], "task_ids lists closed tasks only, sorted"


GLOB_CASES = [
    ("lib/**/*.py", "lib/pdf.py", True, "**/ matches zero directories"),
    ("lib/**/*.py", "lib/upload/v2/pdf.py", True, "**/ matches several directories"),
    ("**/*.md", "README.md", True, "a leading **/ matches zero directories"),
    ("**/.env", "deploy/prod.env", False, "a leading **/ matches whole directories only"),
    ("a/**/b.txt", "a/x/y/b.txt", True, "**/ in the middle matches several directories"),
    ("a/**/b.txt", "a/xb.txt", False, "**/ matches whole directories only"),
    ("*.md", "docs/guide.md", False, "* stays inside one segment"),
    ("app/*.py", "app/api/routes.py", False, "* stays inside one segment"),
    ("a?c.py", "a/c.py", False, "? never matches /"),
    ("lib/**.py", "lib/upload/pdf.py", False, "** inside a segment is *"),
    ("docs/**", "docs/guide/install.md", True, "dir/** matches every file below dir"),
    ("docs/**", "docs", False, "dir/** matches below dir, not dir itself"),
    ("docs/**", "docsite/index.md", False, "dir/** stops at the directory name"),
    ("docs/", "docs/guide/install.md", True, "a trailing / names a directory"),
    ("**", "any/path/at/all.txt", True, "** alone matches every path"),
    ("docs/v1.2/*.md", "docs/v1x2/notes.md", False, "characters other than * ? [ and \\ are literal"),
    ("lib/c++/*.h", "lib/c++/vector.h", True, "characters other than * ? [ and \\ are literal"),
    ("README.md", "readme.md", False, "matching is case-sensitive"),
    ("*.PY", "app.py", False, "matching is case-sensitive"),
    ("lib/[ab]*.py", "lib/beta.py", True, "a class matches one of its members"),
    ("lib/[ab]*.py", "lib/gamma.py", False, "a class matches only its members"),
    ("lib/v[1-3].py", "lib/v2.py", True, "a class can hold a range"),
    ("lib/[!a]*.py", "lib/beta.py", True, "[!...] matches what is not in the class"),
    ("lib/[!a]*.py", "lib/alpha.py", False, "[!...] matches what is not in the class"),
    ("lib[!x]x.py", "lib/x.py", False, "a class never matches /"),
    ("web/app/\\[slug\\]/page.tsx", "web/app/[slug]/page.tsx", True, "a backslash makes the next character literal"),
    ("web/app/\\[slug\\]/page.tsx", "web/app/s/page.tsx", False, "an escaped [ does not open a class"),
]


@pytest.mark.skip("Part 3")
def test_glob_dialect() -> None:
    """Contract globs mean what their authors meant, on normalized repository paths."""
    assert normalize_path("./lib//upload/./pdf.py") == "lib/upload/pdf.py", "./ and repeated slashes are dropped"
    assert normalize_path("lib/search/../upload/pdf.py") == "lib/upload/pdf.py", "a/../b is b"
    assert normalize_path("docs/guide/") == "docs/guide", "a trailing slash goes away"
    assert normalize_path("..notes/todo.md") == "..notes/todo.md", "'..notes' is a name, not a parent"
    assert normalize_path("Lib/PDF.py") == "Lib/PDF.py", "case is kept"
    for bad in ("", ".", "/etc/passwd", "../secrets.env", "lib/../../secrets.env", "lib/.."):
        assert raises(ValueError, normalize_path, bad), f"{bad!r} is not a file inside the repository"

    for pattern, path, expected, rule in GLOB_CASES:
        assert compile_glob(pattern).match(path) is expected, f"{rule}: {pattern!r} against {path!r}"
    for bad in ("", "/app.py", "lib/[ab.py", "lib/x\\"):
        assert raises(ValueError, compile_glob, bad), f"{bad!r} is not a valid glob"

    gate = contract(
        "T-003", ["lib/**/*.py", "app/*.py"], ["web/app/\\[slug\\]/**", "**/.env"], docs_paths_soft=["docs/"],
    )
    report = scope_check(gate, RunSummary(
        ["./lib/pdf.py", "lib/pdf.py", "app//api/routes.py", "lib/../app/main.py", "web/app/[slug]/page.tsx",
         ".env", "../secrets.env", "docs/guide/install.md", "web/app/s/page.tsx"],
        [], 1.0,
    ))
    assert report.in_scope_writes == ["lib/pdf.py", "app/main.py"], (
        "the checker matches contract globs in this dialect, on normalized paths"
    )
    assert report.soft_off_scope_writes == ["docs/guide/install.md"], "a trailing / names a directory in the checker too"
    assert report.forbidden_writes[:2] == ["web/app/[slug]/page.tsx", ".env"], "forbidden globs use the dialect too"
    assert report.forbidden_writes == ["web/app/[slug]/page.tsx", ".env", "../secrets.env"], (
        "a path outside the repository is forbidden"
    )
    assert report.off_scope_writes == ["app/api/routes.py", "web/app/s/page.tsx"], (
        "the checker matches contract globs in this dialect, on normalized paths"
    )


DIFF = b"".join(line + b"\n" for line in [
    b"diff --git a/app.py b/app.py",
    b"index 3b18e51..a5c1966 100644",
    b"--- a/app.py",
    b"+++ b/app.py",
    b"@@ -1,2 +1,3 @@",
    b" import upload",
    b"+import pdf",
    b" app = upload.App()",
    b"diff --git a/migrations/0001_init.sql b/migrations/0001_init.sql",
    b"index 5f332ff..7fad796 100644",
    b"--- a/migrations/0001_init.sql",
    b"+++ b/migrations/0001_init.sql",
    b"@@ -1,3 +1,2 @@",
    b" CREATE TABLE docs (id int);",
    b"--- a/b test cohort",
    b" CREATE INDEX docs_id ON docs (id);",
    b"diff --git a/docs/release notes.md b/docs/release notes.md",
    b"index 422c2b7..de98044 100644",
    b"--- a/docs/release notes.md\t",
    b"+++ b/docs/release notes.md\t",
    b"@@ -1,2 +1,3 @@",
    b" ## 1.4",
    b" - faster uploads",
    b"+- PDF size limit",
    b"diff --git a/lib/search/rank.py b/lib/upload/rank.py",
    b"similarity index 92%",
    b"rename from lib/search/rank.py",
    b"rename to lib/upload/rank.py",
    b"index 1a2b3c4..5d6e7f8 100644",
    b"--- a/lib/search/rank.py",
    b"+++ b/lib/upload/rank.py",
    b"@@ -10,2 +10,2 @@ def rank(hits):",
    b"-    return sorted(hits)",
    b"+    return sorted(hits, key=score)",
    b"diff --git a/scripts/deploy.sh b/lib/upload/deploy_notes.py",
    b"similarity index 100%",
    b"copy from scripts/deploy.sh",
    b"copy to lib/upload/deploy_notes.py",
    b"diff --git a/assets/logo.png b/assets/logo.png",
    b"index 12c8a8b..861dfeb 100644",
    b"Binary files a/assets/logo.png and b/assets/logo.png differ",
    b'diff --git "a/docs/caf\\303\\251.md" "b/docs/caf\\303\\251.md"',
    b"index 587be6b..d735d34 100644",
    b'--- "a/docs/caf\\303\\251.md"',
    b'+++ "b/docs/caf\\303\\251.md"',
    b"@@ -1 +1 @@",
    b"-caf\xe9 au lait",
    b"+caf\xc3\xa9 au lait",
    b"diff --git a/lib/search/old_index.py b/lib/search/old_index.py",
    b"deleted file mode 100644",
    b"index 286c5f5..0000000",
    b"--- a/lib/search/old_index.py",
    b"+++ /dev/null",
    b"@@ -1 +0,0 @@",
    b"-INDEX = {}",
    b"diff --git a/scripts/release.sh b/scripts/release.sh",
    b"old mode 100644",
    b"new mode 100755",
    b'diff --git "a/docs/odd\\"name.md" "b/docs/odd\\"name.md"',
    b"index bca70f3..d169a2f 100644",
    b'--- "a/docs/odd\\"name.md"',
    b'+++ "b/docs/odd\\"name.md"',
    b"@@ -1 +1 @@",
    b"-q",
    b"+q2",
    b"diff --git a/notes/plan b/todo.md b/notes/plan b/todo.md",
    b"index 258cd57..e933320 100644",
    b"--- a/notes/plan b/todo.md\t",
    b"+++ b/notes/plan b/todo.md\t",
    b"@@ -1 +1 @@",
    b"-todo",
    b"+todo: size limit",
    b'diff --git "a/docs/r\\303\\251sum\\303\\251.md" b/docs/resume.md',
    b"similarity index 100%",
    b'rename from "docs/r\\303\\251sum\\303\\251.md"',
    b"rename to docs/resume.md",
    b"diff --git a/tools/empty.txt b/tools/empty.txt",
    b"new file mode 100644",
    b"index 0000000..e69de29",
    b"diff --git a/migrations/0001_init.sql b/migrations/0001_init.sql",
    b"index 7fad796..9c0d2e1 100644",
    b"--- a/migrations/0001_init.sql",
    b"+++ b/migrations/0001_init.sql",
    b"@@ -1,2 +1,2 @@",
    b"-CREATE INDEX docs_id ON docs (id);",
    b"+CREATE INDEX docs_id ON docs (id, size);",
])

EXPECTED = [
    ("scope/forbidden", "error", "migrations/0001_init.sql"),
    ("scope/soft-off-scope", "note", "docs/release notes.md"),
    ("scope/off-scope", "warning", "lib/search/rank.py"),
    ("scope/off-scope", "warning", "assets/logo.png"),
    ("scope/over-budget", "error", "assets/logo.png"),
    ("scope/soft-off-scope", "note", "docs/café.md"),
    ("scope/off-scope", "warning", "lib/search/old_index.py"),
    ("scope/forbidden", "error", "scripts/release.sh"),
    ("scope/soft-off-scope", "note", 'docs/odd"name.md'),
    ("scope/soft-off-scope", "note", "notes/plan b/todo.md"),
    ("scope/soft-off-scope", "note", "docs/résumé.md"),
    ("scope/soft-off-scope", "note", "docs/resume.md"),
    ("scope/off-scope", "warning", "tools/empty.txt"),
]


@pytest.mark.skip("Part 4")
def test_diff_scan() -> None:
    """A git diff is checked file by file while it streams, as SARIF results, one per line."""
    gate = contract(
        "T-001", ["app.py", "lib/upload/*.py", "tests/test_upload*.py"], ["migrations/**", "scripts/**"],
        violation_budget=1,
    )
    lines = collect(scan_diff(chunked(DIFF, 4096), gate))
    results = results_of(lines)
    seen = summary(results)
    paths = [path for _, _, path in seen]
    assert "lib/search/rank.py" in paths, "both sides of a rename are checked"
    assert "scripts/deploy.sh" not in paths, "a copy writes only its destination"
    assert {"assets/logo.png", "lib/search/old_index.py", "scripts/release.sh", "tools/empty.txt"} <= set(paths), (
        "binary files, deletions, mode changes and new empty files are writes too"
    )
    assert {"docs/café.md", 'docs/odd"name.md', "docs/résumé.md"} <= set(paths), (
        "a quoted path is C-unescaped, and its bytes are UTF-8"
    )
    assert "notes/plan b/todo.md" in paths, "a path may contain spaces, even ' b/'"
    assert "b test cohort" not in paths, "a removed SQL comment is not a file header"
    reported = [path for rule, _, path in seen if rule != "scope/over-budget"]
    assert len(reported) == len(set(reported)), "each path is reported once"
    assert [path for rule, _, path in seen if rule == "scope/over-budget"] == ["assets/logo.png"], (
        "one over-budget result, for the file that tips the budget"
    )
    assert seen == EXPECTED, "one result per violating path, in diff order"
    assert uri_of(results[1]) == "docs/release%20notes.md" and uri_of(results[5]) == "docs/caf%C3%A9.md", (
        "uri is the path as a percent-encoded URI reference"
    )
    assert all(path in r["message"]["text"] for r, (rule, _, path) in zip(results, seen) if rule != "scope/over-budget"), (
        "message.text names the path"
    )
    for size in (1, 7, 100):
        assert collect(scan_diff(chunked(DIFF, size), gate)) == lines, (
            f"the same results whatever the chunk size ({size} bytes)"
        )
    tail = collect(scan_diff(chunked(b"diff --git a/scripts/run.sh b/scripts/run.sh", 5), gate))
    assert summary(results_of(tail)) == [("scope/forbidden", "error", "scripts/run.sh")], (
        "the last line counts even without a newline"
    )
    modes = b"diff --git a/scripts/run.sh b/scripts/run.sh\nold mode 100644\nnew mode 100755\n"
    assert summary(results_of(collect(scan_diff(chunked(modes, 5), gate)))) == [
        ("scope/forbidden", "error", "scripts/run.sh"),
    ], "a file whose header ends the stream is checked too"
    again = b"".join(b"diff --git a/%s b/%s\nold mode 100644\nnew mode 100755\n" % (p, p)
                     for p in (b"tools/a.sh", b"tools/a.sh", b"tools/b.sh"))
    assert summary(results_of(collect(scan_diff(chunked(again, 64), gate)))) == [
        ("scope/off-scope", "warning", "tools/a.sh"), ("scope/off-scope", "warning", "tools/b.sh"),
        ("scope/over-budget", "error", "tools/b.sh"),
    ], "the budget counts distinct off-scope files"

    pulled: list[int] = []
    head = (
        b"diff --git a/migrations/0002_size.sql b/migrations/0002_size.sql\n"
        b"index 1111111..2222222 100644\n"
        b"--- a/migrations/0002_size.sql\n"
        b"+++ b/migrations/0002_size.sql\n"
        b"@@ -1 +1,400 @@\n"
    )

    async def probe():
        for i, chunk in enumerate([head] + [b"+ALTER TABLE docs ADD COLUMN c%d int;\n" % n for n in range(400)]):
            pulled.append(i)
            yield chunk

    async def first() -> str:
        agen = scan_diff(probe(), gate)
        line = await agen.__anext__()
        await agen.aclose()
        return line

    assert summary(results_of([asyncio.run(first())])) == [("scope/forbidden", "error", "migrations/0002_size.sql")]
    assert len(pulled) <= 2, "report a file as soon as its header is complete"


@pytest.mark.skip("Part 5")
def test_contract_chain() -> None:
    """Contracts nest from the project down to a subtask, and no layer can widen the layers above it."""
    project = contract(
        "knowledge-base", ["app.py", "lib/**", "tests/**", "docs/**"], ["scripts/**", "scripts/release.sh", "config/prod/**"],
        altitude="project", approvals_required=["any new runtime dependency"], violation_budget=3,
    )
    feature = contract(
        "import-pdf", ["app.py", "lib/upload/**", "lib/pdf/**", "tests/**"], ["lib/pdf/vendor/**"],
        altitude="feature", parent="knowledge-base", acceptance_criteria=["pytest tests/test_import.py"],
        time_budget_minutes=120, network_egress=[], violation_budget=2,
    )
    task = contract(
        "T-001", ["lib/upload/**", "lib/pdf/parse.py", "tests/test_upload*.py", "tools/upload_cli.py"],
        ["lib/upload/legacy/**", "secrets/**", "**/release.sh"],
        parent="import-pdf", acceptance_criteria=["pytest -x tests/test_upload.py"], approvals_required=["schema changes"],
        time_budget_minutes=45, network_egress=["api.anthropic.com"], violation_budget=5,
    )
    subtask = contract(
        "T-001.1", ["lib/upload/limits.py", "lib/**", "tests/test_upload_limits.py", "tools/**"], ["scripts/release.sh"],
        altitude="subtask", parent="T-001", network_egress=["api.anthropic.com", "pypi.org"], violation_budget=9,
    )
    search = contract("full-text-search", ["lib/search/**", "tests/**"], altitude="feature", parent="knowledge-base")
    ranking = contract("T-002", ["lib/search/**"], parent="full-text-search", network_egress=["api.anthropic.com"])
    contracts = [subtask, ranking, project, task, search, feature]

    chain = resolve_chain(contracts, "T-001.1")
    assert [layer.task_id for layer in chain.layers] == ["knowledge-base", "import-pdf", "T-001", "T-001.1"], (
        "the layers run from the project down"
    )
    assert chain.explain("lib/upload/limits.py") == Explanation("allowed", None, None), "every layer allows it"
    assert chain.explain("lib/search/index.py") == Explanation("not_allowed", "import-pdf", None), (
        "the layer nearest the project explains"
    )
    assert chain.explain("lib/pdf/render.py") == Explanation("not_allowed", "T-001", None), (
        "a subtask cannot widen its task"
    )
    assert chain.explain("tools/upload_cli.py") == Explanation("not_allowed", "knowledge-base", None), (
        "the project's allow-list still holds three layers down"
    )
    assert chain.explain("lib/upload/legacy/v1.py") == Explanation("forbidden", "T-001", "lib/upload/legacy/**"), (
        "a task's forbidden glob binds its subtasks"
    )
    assert chain.explain("scripts/release.sh") == Explanation("forbidden", "knowledge-base", "scripts/**"), (
        "the first matching glob of the layer nearest the project"
    )
    assert chain.explain("secrets/prod.env") == Explanation("forbidden", "T-001", "secrets/**"), (
        "forbidden wins over not allowed, whichever layer says it"
    )
    assert chain.explain_host("api.anthropic.com") == Explanation("not_allowed", "import-pdf", None), (
        "an empty network_egress allows no host"
    )
    assert chain.explain_host("pypi.org") == Explanation("not_allowed", "import-pdf", None), (
        "a subtask cannot widen network_egress either"
    )
    other = resolve_chain(contracts, "T-002")
    assert other.explain_host("API.Anthropic.com:443") == Explanation("allowed", None, None), (
        "network_egress None does not restrict, and hosts compare as in scope_check"
    )
    assert other.explain_host("pypi.org") == Explanation("not_allowed", "T-002", None)

    effective = chain.effective()
    assert effective.network_egress == [], "deny-all stays deny-all down the chain"
    assert other.effective().network_egress == ["api.anthropic.com"], "None defers to the layers that restrict"
    assert (effective.time_budget_minutes, effective.violation_budget) == (45, 2), "budgets take the tightest layer"
    assert effective.approvals_required == ["any new runtime dependency", "schema changes"], (
        "approvals accumulate from the project down"
    )
    assert effective.forbidden_files == sorted([
        "scripts/**", "scripts/release.sh", "config/prod/**", "lib/pdf/vendor/**", "lib/upload/legacy/**", "secrets/**",
        "**/release.sh",
    ]), "forbidden globs accumulate"
    report = scope_check(effective, RunSummary(
        ["lib/upload/limits.py", "lib/pdf/render.py", "tools/upload_cli.py", "lib/upload/legacy/v1.py"],
        ["pytest tests/test_import.py", "pytest -x tests/test_upload.py"], 10.0,
    ))
    assert (report.in_scope_writes, report.off_scope_writes, report.forbidden_writes) == (
        ["lib/upload/limits.py"], ["lib/pdf/render.py", "tools/upload_cli.py"], ["lib/upload/legacy/v1.py"],
    ), "the merged contract checks a run the way the chain explains it"

    assert raises(KeyError, resolve_chain, contracts, "T-404"), "an unknown task_id raises KeyError"
    for stray, rule in (
        (contract("T-003", ["lib/**"], parent="ocr"), "a missing layer raises ValueError"),
        (contract("T-004", ["lib/**"], parent="knowledge-base"), "a task sits under a feature"),
        (contract("T-005.1", ["lib/**"], altitude="subtask", parent="import-pdf"), "a subtask sits under a task"),
        (contract("T-006", ["lib/**"]), "only the project contract has no parent"),
        (contract("search-service", ["lib/search/**"], altitude="project", parent="knowledge-base"),
         "a project contract has no parent"),
    ):
        assert raises(ValueError, resolve_chain, contracts + [stray], stray.task_id), rule
    twin = contract("T-001", ["lib/search/**"], parent="full-text-search")
    assert raises(ValueError, resolve_chain, contracts + [twin], "T-001.1"), "two contracts with one task_id raise ValueError"
