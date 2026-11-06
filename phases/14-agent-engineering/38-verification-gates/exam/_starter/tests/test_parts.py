import asyncio
import hashlib
import hmac
import itertools
import json
import shlex
import time
from dataclasses import replace

import pytest
from verifygate.checks import acceptance_findings
from verifygate.gate import apply_overrides, verify
from verifygate.model import Artifacts, Finding, Verdict
from verifygate.overridelog import LogTampered, OverrideLog
from verifygate.report import write_report
from verifygate.signing import canonical, make_override
from verifygate.stack import StackCommit, verify_stack
from verifygate.summary import render_summary, stream_summaries

SECRET = b"override-secret-held-by-the-release-captains"
HEAD = "4be7a1c"

# Acceptance commands as a human typed them into the scope contract.
SIGNUP = "pytest -x tests/test_signup.py::test_rejects_short_password"
LINT = "ruff check  app 'tests/test_signup.py'"
PAY = 'pytest -k "card and not slow" tests/test_pay.py'
# The argv lists the lesson 37 runner records for them.
SIGNUP_ARGV = ["pytest", "-x", "tests/test_signup.py::test_rejects_short_password"]
LINT_ARGV = ["ruff", "check", "app", "tests/test_signup.py"]
PAY_ARGV = ["pytest", "-k", "card and not slow", "tests/test_pay.py"]
CLOCK = itertools.count(1767225600)


def run(argv, exit_code, command_id, parent=None, error=None) -> dict:
    """A feedback record as the lesson 37 runner writes it; records made later started later."""
    return {
        "command_id": command_id,
        "parent_command_id": parent,
        "command": argv,
        "stdout_tail": "",
        "stderr_tail": error or "",
        "exit_code": exit_code,
        "duration_ms": 840,
        "started_at": float(next(CLOCK)),
        "agent_note": "",
        "error": error,
    }


def sign_fields(fields: dict, secret: bytes = SECRET) -> dict:
    """fields plus the signature the override CLI computes: HMAC-SHA256 of the canonical JSON, 32 hex digits."""
    body = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    return {**fields, "signature": hmac.new(secret, body, hashlib.sha256).hexdigest()[:32]}


def signed(task_id, finding_code, reason, user_id, head_commit, ts, secret: bytes = SECRET) -> dict:
    """An override entry as the override CLI writes it."""
    fields = {
        "task_id": task_id,
        "finding_code": finding_code,
        "reason": reason,
        "user_id": user_id,
        "head_commit": head_commit,
        "ts": ts,
    }
    return sign_fields(fields, secret)


CLEAN_SCOPE = {"forbidden_writes": [], "off_scope_writes": [], "soft_off_scope_writes": [], "over_budget": False}


def task(acceptance, feedback, **changes) -> Artifacts:
    """Task T-42 at HEAD with clean scope, green rules and coverage up a point; changes replace fields."""
    art = Artifacts(
        task_id="T-42",
        head_commit=HEAD,
        acceptance_commands=acceptance,
        feedback=feedback,
        scope_report=CLEAN_SCOPE,
        rule_report=[{"slug": "done/tests-pass", "passed": True, "severity": "block"}],
        coverage_report={"current": 0.86, "previous": 0.85},
    )
    return replace(art, **changes)


def codes(findings) -> list[tuple[str, str]]:
    return [(f.code, f.severity) for f in findings]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


@pytest.mark.skip("Part 1")
def test_acceptance_and_overrides() -> None:
    """Acceptance is read off lesson 37's records, latest run first; only signed, current overrides count."""
    accept = [SIGNUP, LINT, PAY]
    clean = [run(SIGNUP_ARGV, 0, "c1"), run(LINT_ARGV, 0, "c2"), run(PAY_ARGV, 0, "c3")]
    assert acceptance_findings(task(accept, clean)) == [], "an argv record is a run of the acceptance command"

    retried = [run(SIGNUP_ARGV, 1, "c1"), run(LINT_ARGV, 0, "c2"), run(SIGNUP_ARGV, 0, "c3", "c1"), run(PAY_ARGV, 0, "c4")]
    assert acceptance_findings(task(accept, retried)) == [], "the latest run of an acceptance command decides"
    broken = clean + [run(SIGNUP_ARGV, 2, "c4", "c1")]
    assert acceptance_findings(task(accept, broken)) == [Finding("acceptance.failed", "block", f"exit 2: {SIGNUP}")], (
        "a pass that a later run broke is no longer a pass"
    )
    crashed = clean + [run(LINT_ARGV, None, "c4", "c2", error="TimeoutExpired after 600 s")]
    assert acceptance_findings(task(accept, crashed)) == [Finding("feedback.null_exit", "block", f"no exit code: {LINT}")], (
        "a latest run without an exit code blocks"
    )
    lookalike = clean[:2] + [run(["pytest", "-k", "card", "and", "not", "slow", "tests/test_pay.py"], 0, "c3")]
    assert acceptance_findings(task(accept, lookalike)) == [Finding("acceptance.missing", "block", f"never ran: {PAY}")], (
        "a different argv is a different command, even if it reads the same with spaces"
    )

    gated = [
        Finding("scope.forbidden", "block", "forbidden writes: scripts/release.sh"),
        Finding("scope.off_scope", "warn", "off-scope writes: README.md"),
        Finding("rule.failed", "block", "rule failed: forbidden/no-release-script-edits"),
        Finding("feedback.null_exit", "block", f"no exit code: {LINT}"),
    ]
    reason = "Release script bump approved in INC-2231"
    approval = make_override("T-42", "scope.forbidden", reason, "maria", HEAD, secret=SECRET, ts=1767225600.25)

    def overridden(entries, task_id="T-42", head_commit=HEAD):
        return apply_overrides(gated, entries, task_id=task_id, head_commit=head_commit, secret=SECRET)

    assert overridden([approval]) == [
        Finding("scope.forbidden", "overridden", "forbidden writes: scripts/release.sh", "maria", reason),
        *gated[1:],
    ], "a signed override clears its own block finding, and no other"
    assert gated[0].severity == "block", "apply_overrides leaves the findings it was given alone"
    assert overridden([approval], head_commit="9f00d2e") == gated, "an override recorded at an older HEAD is stale"
    assert overridden([approval], task_id="T-43") == gated, "an override belongs to its own task"
    assert overridden([{**approval, "reason": "Approved by everyone"}]) == gated, "an entry changed after signing is refused"
    assert overridden([{**approval, "ts": 1767225601.25}]) == gated, "the timestamp is signed too"
    forged = make_override("T-42", "scope.forbidden", reason, "maria", HEAD, secret=b"guessed-by-the-agent", ts=1767225600.25)
    assert overridden([forged]) == gated, "an override signed with another secret is forged"
    assert overridden([{k: v for k, v in approval.items() if k != "signature"}]) == gated, (
        "an entry without a signature is not an override"
    )
    flaky = make_override("T-42", "feedback.null_exit", "Runner is flaky, lint passed locally", "maria", HEAD, secret=SECRET)
    assert overridden([flaky]) == gated, "a null exit cannot be overridden: there is no result to sign off on"
    readme = make_override("T-42", "scope.off_scope", "README edit is fine", "maria", HEAD, secret=SECRET)
    assert overridden([readme]) == gated, "only block findings are overridden"
    second_look = make_override("T-42", "scope.forbidden", "Re-approved after review", "dev-lead", HEAD, secret=SECRET)
    assert overridden([approval, second_look])[0].overridden_by == "dev-lead", "the last signed override of a finding counts"
    elsewhere = make_override("T-43", "scope.forbidden", "Release bump for T-43", "dev-lead", "9f00d2e", secret=SECRET)
    assert overridden([approval, elsewhere])[0].overridden_by == "maria", (
        "an entry that does not count for this task leaves the one that does"
    )
    fields = {"task_id": "T-42", "finding_code": "scope.forbidden", "reason": reason, "user_id": "maria", "head_commit": HEAD}
    for blank in ({"reason": "   "}, {"user_id": ""}):
        with pytest.raises(ValueError):
            make_override(**{**fields, **blank}, secret=SECRET)
    with pytest.raises(ValueError):
        make_override("T-42", "scope.forbidden", reason, "maria", HEAD, secret=b"")

    many = [f"pytest -x tests/test_api.py::test_case_{i:03d}" for i in range(400)]
    log = [run(shlex.split(cmd), 0, f"a{i}") for i, cmd in enumerate(many)]
    log += [run(["python", "-c", f"print({i})"], 0, f"p{i}") for i in range(8000)]
    start = time.perf_counter()
    found = acceptance_findings(task(many, log))
    elapsed = time.perf_counter() - start
    assert found == []
    assert elapsed < 0.1, "acceptance_findings reads the feedback log once"


@pytest.mark.skip("Part 2")
def test_override_log(tmp_path) -> None:
    """Overrides live in an append-only, signed JSON-lines file: they read back exactly, and a bad line is named."""
    path = tmp_path / "outputs" / "verification" / "overrides.jsonl"
    with pytest.raises(ValueError):
        OverrideLog(path, b"")
    log = OverrideLog(path, SECRET)
    assert log.entries() == [], "a log that does not exist yet has no entries"

    first = signed(
        "T-42", "scope.forbidden", "Release script bump approved in INC-2231 by María, release captain ✅", "maria", HEAD,
        1767225600.4815162,
    )
    second = signed(
        "T-42", "rule.failed", 'Waived: "done/tests-pass" flaked twice on C:\\ci\\win-runner\tsee #8812', "dev-lead", HEAD,
        1767225660,
    )
    third = signed("T-43", "coverage.regression", "Deleted the legacy importer and its tests", "maria", "9f00d2e", 1767229200.1)
    assert [log.append(entry) for entry in (first, second, third)] == [1, 2, 3], "append returns the new entry's line number"

    entries = OverrideLog(path, SECRET).entries()
    assert entries == [first, second, third], "entries read back as they were appended"
    assert [canonical(e) for e in entries] == [canonical(e) for e in (first, second, third)], (
        "the signed bytes survive the round trip, number types included"
    )
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n") and [json.loads(line) for line in text.split("\n")[:-1]] == [first, second, third], (
        "one JSON entry per line, each ending with a newline"
    )

    foreign = signed("T-46", "rule.failed", "Überprüft und freigegeben", "jonas", "5d1e2f3", 1767240000.0)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(reversed(list(foreign.items()))), ensure_ascii=False, separators=(", ", " : ")) + "\n")
    assert OverrideLog(path, SECRET).entries()[-1] == foreign, (
        "a line another tool wrote, with other spacing, key order and raw UTF-8, still verifies"
    )

    before = path.read_bytes()
    one, two = OverrideLog(path, SECRET), OverrideLog(path, SECRET)
    docs_move = signed("T-44", "scope.off_scope", "Docs move agreed with the docs team", "kenji", "77aa01b", 1767232800.0)
    changelog = signed("T-44", "rule.failed", "Changelog entry lands with the release PR", "kenji", "77aa01b", 1767232801.5)
    outage = signed("T-45", "acceptance.failed", "Upstream outage, rerun scheduled", "maria", "0c0ffee", 1767236400.75)
    assert (one.append(docs_move), two.append(changelog), one.append(outage)) == (5, 6, 7), (
        "line numbers count what is in the file, whoever wrote it"
    )
    assert path.read_bytes().startswith(before), "earlier lines are never rewritten, whoever wrote them"
    assert OverrideLog(path, SECRET).entries() == [first, second, third, foreign, docs_move, changelog, outage], (
        "two writers share one log"
    )

    kept = path.read_bytes()
    fields = {k: v for k, v in first.items() if k != "signature"}
    refused = {
        "unsigned": fields,
        "changed after signing": {**first, "reason": "Approved"},
        "signed with another secret": signed("T-42", "scope.forbidden", "ok", "maria", HEAD, 1767225600.0, secret=b"guessed"),
        "carrying an extra field": sign_fields({**fields, "approved": True}),
        "missing a field": sign_fields({k: v for k, v in fields.items() if k != "head_commit"}),
    }
    for name, bad in refused.items():
        try:
            log.append(bad)
        except ValueError:
            continue
        pytest.fail(f"append must refuse an entry {name}")
    assert path.read_bytes() == kept, "a refused entry writes nothing"

    good = path.read_text(encoding="utf-8").split("\n")

    def first_bad_line(number: int, line: str, also: dict | None = None) -> int:
        lines = list(good)
        lines[number - 1] = line
        for other, replacement in (also or {}).items():
            lines[other - 1] = replacement
        path.write_text("\n".join(lines), encoding="utf-8")
        with pytest.raises(LogTampered) as caught:
            OverrideLog(path, SECRET).entries()
        return caught.value.line

    parsed = [json.loads(line) for line in good[:-1]]
    assert first_bad_line(2, json.dumps({**parsed[1], "reason": "Waived"})) == 2, "a changed field is caught on its own line"
    assert first_bad_line(3, json.dumps({**parsed[2], "ts": 1767229200.2})) == 3, "the timestamp is signed too"
    assert first_bad_line(4, good[3][:-1] + ', "approved": true}') == 4, "an added field is caught"
    renamed = {k: v for k, v in parsed[3].items() if k not in ("signature", "ts")}
    assert first_bad_line(4, json.dumps(sign_fields({**renamed, "timestamp": parsed[3]["ts"]}))) == 4, (
        "a renamed field is caught, even when the line is signed"
    )
    assert first_bad_line(5, good[4][:60]) == 5, "a cut-off line is caught"
    assert first_bad_line(6, "") == 6, "a blank line is not an entry"
    assert first_bad_line(7, "null") == 7, "a line that is not a JSON object is caught"
    assert first_bad_line(2, '{"finding_code": "coverage.missing", ' + good[1][1:]) == 2, (
        "a field given twice is caught: two JSON readers could disagree on its value"
    )
    assert first_bad_line(3, json.dumps({**parsed[2], "signature": "é" * 32})) == 3, (
        "a mangled signature is caught, not crashed on"
    )
    assert first_bad_line(5, "{}", also={2: json.dumps({**parsed[1], "user_id": "agent"})}) == 2, (
        "the first bad line is the one reported"
    )


@pytest.mark.skip("Part 3")
def test_verdict_and_report(tmp_path) -> None:
    """verify() merges the four sources into one verdict, the same every time; write_report() puts it at the one path."""
    ok = [{"command": SIGNUP, "exit_code": 0}]
    clean = task([SIGNUP], ok)
    assert verify(clean, secret=SECRET) == Verdict("T-42", HEAD, True, False, [], {"current": 0.86, "previous": 0.85}), (
        "a clean task passes with no findings"
    )

    messy = task(
        [SIGNUP],
        [{"command": SIGNUP, "exit_code": 1}],
        scope_report={
            "forbidden_writes": ["scripts/release.sh"],
            "off_scope_writes": ["docs/api.md"],
            "soft_off_scope_writes": ["CHANGELOG.md"],
            "over_budget": False,
        },
        rule_report=[
            {"slug": "done/tests-pass", "passed": False, "severity": "block"},
            {"slug": "uncertainty/open-question-note", "passed": False, "severity": "warn"},
            {"slug": "style/docstring-first-line", "passed": False, "severity": "info"},
            {"slug": "approval/new-dependency", "passed": True, "severity": "block"},
        ],
        coverage_report={"current": 0.845, "previous": 0.85},
    )
    verdict = verify(messy, secret=SECRET)
    assert codes(verdict.findings) == [
        ("acceptance.failed", "block"),
        ("scope.forbidden", "block"),
        ("scope.off_scope", "warn"),
        ("scope.soft_off_scope", "info"),
        ("rule.failed", "block"),
        ("rule.failed", "warn"),
        ("rule.failed", "info"),
        ("coverage.minor_regression", "warn"),
    ], "findings come source by source, each rule with the severity it was written with"
    assert not verdict.passed, "a block fails the task"
    strict = verify(messy, secret=SECRET, strict=True)
    assert codes(strict.findings) == [
        ("acceptance.failed", "block"),
        ("scope.forbidden", "block"),
        ("scope.off_scope", "block"),
        ("scope.soft_off_scope", "info"),
        ("rule.failed", "block"),
        ("rule.failed", "block"),
        ("rule.failed", "info"),
        ("coverage.minor_regression", "block"),
    ], "--strict turns every warn into a block and leaves info alone"
    assert strict.strict and not verdict.strict, "the verdict records whether the gate ran strict"

    readme = task([SIGNUP], ok, scope_report={**CLEAN_SCOPE, "off_scope_writes": ["README.md"]})
    approved = signed("T-42", "scope.off_scope", "README documents the new signup contract", "maria", HEAD, 1767225600.0)
    assert codes(verify(readme, [approved], secret=SECRET).findings) == [("scope.off_scope", "warn")], (
        "a warn needs no override"
    )
    lenient = verify(readme, [approved], secret=SECRET, strict=True)
    assert lenient.passed and codes(lenient.findings) == [("scope.off_scope", "overridden")], (
        "under --strict a signed override clears the block strict made"
    )
    assert not verify(readme, secret=SECRET, strict=True).passed, "without the override the block strict made stands"

    for row in (
        {"slug": "forbidden/no-release-script-edits", "passed": False},
        {"slug": "forbidden/no-release-script-edits", "passed": False, "severity": "Warn"},
        {"slug": "forbidden/no-release-script-edits", "passed": False, "severity": "critical"},
    ):
        tagged = verify(task([SIGNUP], ok, rule_report=[row]), secret=SECRET)
        assert codes(tagged.findings) == [("rule.failed", "block")] and not tagged.passed, (
            f"a failed rule tagged {row.get('severity')!r} blocks: the gate fails closed"
        )

    missing = {"feedback": "feedback_record.jsonl", "scope_report": "scope_report.json", "rule_report": "rule_report.json"}
    for field, name in missing.items():
        lost = verify(replace(clean, **{field: None}), secret=SECRET)
        assert lost.findings == [Finding("gate.missing_artifact", "block", f"missing artifact: {name}")] and not lost.passed, (
            f"a missing {name} blocks instead of counting as clean"
        )
    assert codes(verify(replace(messy, scope_report=None), secret=SECRET).findings) == [
        ("acceptance.failed", "block"),
        ("gate.missing_artifact", "block"),
        ("rule.failed", "block"),
        ("rule.failed", "warn"),
        ("rule.failed", "info"),
        ("coverage.minor_regression", "warn"),
    ], "a missing artifact's finding takes its source's place"
    empty = verify(task([SIGNUP], ok, scope_report={}, rule_report=[]), secret=SECRET)
    assert empty.passed and empty.findings == [], "an empty artifact exists and has nothing in it"
    never_ran = [Finding("acceptance.missing", "block", f"never ran: {SIGNUP}")]
    assert verify(task([SIGNUP], []), secret=SECRET).findings == never_ran, "an empty feedback log is not a missing one"
    nothing = verify(task([], ok), secret=SECRET)
    assert codes(nothing.findings) == [("gate.no_acceptance", "block")] and not nothing.passed, (
        "a task without an acceptance command proves nothing"
    )

    for previous, current, expected in (
        (0.85, 0.84, [("coverage.minor_regression", "warn")]),
        (0.81, 0.80, [("coverage.minor_regression", "warn")]),
        (0.85, 0.839, [("coverage.regression", "block")]),
        (0.8599, 0.849, [("coverage.regression", "block")]),
        (0.9, 0.6 + 0.3, []),
        (0.80, 0.79, [("coverage.below_floor", "block"), ("coverage.minor_regression", "warn")]),
    ):
        measured = task([SIGNUP], ok, coverage_report={"current": current, "previous": previous})
        assert codes(verify(measured, secret=SECRET).findings) == expected, (
            f"coverage {previous} -> {current}: more than one point down blocks, less warns, float noise is no drop"
        )
    assert codes(verify(task([SIGNUP], ok, coverage_report=None), secret=SECRET).findings) == [("coverage.missing", "warn")], (
        "no coverage report is a warn"
    )
    for floor in (0.9, 1.0):
        assert codes(verify(clean, secret=SECRET, coverage_floor=floor).findings) == [("coverage.below_floor", "block")], (
            f"the floor is the one given, here {floor}"
        )
    for floor in (80, 0):
        try:
            verify(clean, secret=SECRET, coverage_floor=floor)
        except ValueError:
            continue
        pytest.fail(f"verify must refuse coverage_floor={floor}: a floor is a fraction in (0, 1]")

    path = write_report(tmp_path, verdict)
    assert path == tmp_path / "outputs" / "verification" / "T-42.json", "one task, one path"
    expected_text = json.dumps(verdict.to_dict(), indent=2, sort_keys=True) + "\n"
    assert path.read_text(encoding="utf-8") == expected_text, "the report is the verdict's JSON, keys sorted, two-space indent"
    assert write_report(tmp_path, verify(messy, secret=SECRET)) == path and path.read_text(encoding="utf-8") == expected_text, (
        "the same artifacts give the same bytes"
    )
    write_report(tmp_path, verify(clean, secret=SECRET))
    assert json.loads(path.read_text(encoding="utf-8")) == verify(clean, secret=SECRET).to_dict(), (
        "a new verdict replaces the report"
    )
    for bad in ("../T-42", "T-42/../../escape", "..", ".T-42", "", "T 42"):
        try:
            write_report(tmp_path, replace(verdict, task_id=bad))
        except ValueError:
            continue
        pytest.fail(f"write_report must refuse the task id {bad!r}")
    written = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()]
    assert written == ["outputs/verification/T-42.json"], "nothing but the one report is written"


def report(findings, passed=False, strict=False) -> dict:
    return {"task_id": "T-42", "head_commit": HEAD, "passed": passed, "strict": strict, "coverage": None, "findings": findings}


def row(code, severity, detail, by=None, why=None) -> dict:
    return {"code": code, "severity": severity, "detail": detail, "overridden_by": by, "override_reason": why}


MIXED = report(
    [
        row("acceptance.failed", "block", "exit 2: pytest -x tests/test_signup.py '|' tee log.txt"),
        row("coverage.minor_regression", "warn", "coverage dropped 0.50%"),
        row("scope.forbidden", "overridden", "forbidden writes: deploy\\prod.ps1", "maria", "approved in `#release`, INC-2231"),
        row("acceptance.failed", "block", "exit 1: ruff check 'app/**/*.py'"),
        row("rule.failed", "info", "rule failed: style/docstring-first-line"),
    ]
)
MIXED_MD = (
    "# T-42: FAILED\n"
    "head 4be7a1c\n"
    "\n"
    "## block (2)\n"
    "\n"
    "| code | detail |\n"
    "| --- | --- |\n"
    "| acceptance.failed | exit 2: pytest -x tests/test\\_signup.py '\\|' tee log.txt |\n"
    "| acceptance.failed | exit 1: ruff check 'app/\\*\\*/\\*.py' |\n"
    "\n"
    "## warn (1)\n"
    "\n"
    "| code | detail |\n"
    "| --- | --- |\n"
    "| coverage.minor\\_regression | coverage dropped 0.50% |\n"
    "\n"
    "## info (1)\n"
    "\n"
    "| code | detail |\n"
    "| --- | --- |\n"
    "| rule.failed | rule failed: style/docstring-first-line |\n"
    "\n"
    "## overridden (1)\n"
    "\n"
    "| code | detail | by | reason |\n"
    "| --- | --- | --- | --- |\n"
    "| scope.forbidden | forbidden writes: deploy\\\\prod.ps1 | maria | approved in \\`#release\\`, INC-2231 |\n"
)
ANNOTATED = report(
    [
        row("rule.failed", "info", "rule failed: style/docstring-first-line"),
        row("rule.failed", "warn", "rule failed: uncertainty/open-question-note"),
    ],
    passed=True,
)
ANNOTATED_MD = (
    "# T-42: PASSED\n"
    "head 4be7a1c\n"
    "\n"
    "## warn (1)\n"
    "\n"
    "| code | detail |\n"
    "| --- | --- |\n"
    "| rule.failed | rule failed: uncertainty/open-question-note |\n"
    "\n"
    "## info (1)\n"
    "\n"
    "| code | detail |\n"
    "| --- | --- |\n"
    "| rule.failed | rule failed: style/docstring-first-line |\n"
)

LINT_S = "ruff check app"
SIGNUP_S = "pytest -x tests/test_signup.py"
ARRIVALS = [
    {"command_id": "c1", "command": LINT_S, "exit_code": 0},
    {"command_id": "c2", "command": SIGNUP_S, "exit_code": 1},
    {"command_id": "c3", "command": "git status", "exit_code": 0},
    {"command_id": "c4", "command": SIGNUP_S, "exit_code": 1},
    {"command_id": "c5", "command": SIGNUP_S, "exit_code": 0},
    {"command_id": "c6", "command": "git diff --stat", "exit_code": 0},
    {"command_id": "c7", "command": LINT_S, "exit_code": None},
    {"command_id": "c8", "command": LINT_S, "exit_code": 0},
]


def scripted_gate() -> tuple:
    """A stand-in for verify(...).to_dict(): T-42's two acceptance commands, the latest run of each decides."""
    seen: list[list[str]] = []

    def gate(feedback: list[dict]) -> dict:
        seen.append([record["command_id"] for record in feedback])
        latest = {record["command"]: record for record in feedback}
        findings = []
        for cmd in (LINT_S, SIGNUP_S):
            last = latest.get(cmd)
            if last is None:
                findings.append(row("acceptance.missing", "block", f"never ran: {cmd}"))
            elif last["exit_code"] is None:
                findings.append(row("feedback.null_exit", "block", f"no exit code: {cmd}"))
            elif last["exit_code"] != 0:
                findings.append(row("acceptance.failed", "block", f"exit {last['exit_code']}: {cmd}"))
        return report(findings, passed=not findings)

    return gate, seen


async def arrive(records, pulled=None):
    for record in records:
        if pulled is not None:
            pulled.append(record["command_id"])
        yield record


@pytest.mark.skip("Part 4")
def test_summary_stream() -> None:
    """A Markdown summary follows the gate as feedback arrives: one per change, as soon as it happens."""
    assert render_summary(MIXED) == MIXED_MD, "one table per severity, in a fixed order, with special characters escaped"
    assert render_summary(ANNOTATED) == ANNOTATED_MD, (
        "warn and info annotate a passing verdict, and a severity without findings gets no section"
    )
    assert render_summary(report([], passed=True, strict=True)) == "# T-42: PASSED\nhead 4be7a1c, strict\n", (
        "the head line says when the gate ran strict"
    )

    gate, seen = scripted_gate()
    chunks = collect(stream_summaries(arrive(ARRIVALS), gate))
    reference, _ = scripted_gate()
    expected = [render_summary(reference(ARRIVALS[:n])) for n in (0, 1, 2, 5, 7, 8)]
    assert chunks[:1] == expected[:1], "the first summary is the verdict before any record arrives"
    assert len(chunks) == len(expected), "a summary goes out when a record changes it, and only then"
    assert chunks[1:] == ["\n---\n\n" + text for text in expected[1:]], (
        "summaries are separated by a blank line, ---, and a blank line"
    )
    assert seen == [[r["command_id"] for r in ARRIVALS[:n]] for n in range(len(ARRIVALS) + 1)], (
        "the gate runs before the first record and after each one, on every record so far"
    )
    assert collect(stream_summaries(arrive([]), scripted_gate()[0])) == expected[:1], (
        "a stream without records still gets the first summary"
    )

    pulled: list[str] = []

    async def first_three() -> list[int]:
        agen = stream_summaries(arrive(ARRIVALS, pulled), scripted_gate()[0])
        counts = []
        for _ in range(3):
            await agen.__anext__()
            counts.append(len(pulled))
        await agen.aclose()
        return counts

    pulled_at = asyncio.run(first_three())
    assert pulled_at[0] == 0, "the first summary goes out before the first record is read"
    assert pulled_at == [0, 1, 2], "each summary goes out as soon as the record that changed it arrives"


def stack_artifacts(sha: str, coverage: float | None, made_at: str | None = None) -> Artifacts:
    """CI's artifacts for one commit of the T-60 stack. CI compared coverage with main as it was when the job ran."""
    return Artifacts(
        task_id="T-60",
        head_commit=made_at or sha,
        acceptance_commands=["pytest -x tests"],
        feedback=[{"command": "pytest -x tests", "exit_code": 0}],
        scope_report=CLEAN_SCOPE,
        rule_report=[{"slug": "done/tests-pass", "passed": True, "severity": "block"}],
        coverage_report=None if coverage is None else {"current": coverage, "previous": 0.86},
    )


@pytest.mark.skip("Part 5")
def test_pr_stack() -> None:
    """Each commit of a stack is gated against the commit it sits on, and blocked by the first failure below it."""
    given = [
        StackCommit("e1", "d1", stack_artifacts("e1", 0.80)),
        StackCommit("c1", "b1", stack_artifacts("c1", None)),
        StackCommit("g1", "f1", stack_artifacts("g1", 0.83)),
        StackCommit("a1", "m0", stack_artifacts("a1", 0.83)),
        StackCommit("h1", "b1", stack_artifacts("h1", 0.83, made_at="h0")),
        StackCommit("d1", "c1", stack_artifacts("d1", 0.80)),
        StackCommit("b1", "a1", stack_artifacts("b1", 0.825)),
        StackCommit("f1", "b1", None),
    ]
    waiver = signed("T-60", "coverage.regression", "Deleted the legacy importer and its tests", "maria", "a1", 1767240000.0)
    statuses = verify_stack("m0", 0.85, given, [waiver], secret=SECRET)

    assert [s.sha for s in statuses] == ["a1", "b1", "c1", "d1", "e1", "h1", "f1", "g1"], (
        "parents before children, depth first, children in the order given"
    )
    by_sha = {s.sha: s for s in statuses}
    assert {sha: by_sha[sha].verdict.coverage for sha in ("a1", "b1", "c1", "d1", "e1")} == {
        "a1": {"current": 0.83, "previous": 0.85},
        "b1": {"current": 0.825, "previous": 0.83},
        "c1": None,
        "d1": {"current": 0.80, "previous": 0.825},
        "e1": {"current": 0.80, "previous": 0.80},
    }, "each commit is compared with the coverage it is stacked on, not with main"
    assert {sha: codes(by_sha[sha].verdict.findings) for sha in ("a1", "b1", "c1", "d1", "e1")} == {
        "a1": [("coverage.regression", "overridden")],
        "b1": [("coverage.minor_regression", "warn")],
        "c1": [("coverage.missing", "warn")],
        "d1": [("coverage.regression", "block")],
        "e1": [],
    }, "an override signed at a1 stays on a1"
    assert [(s.sha, s.status, s.blocked_by) for s in statuses] == [
        ("a1", "passed", None),
        ("b1", "passed", None),
        ("c1", "passed", None),
        ("d1", "failed", "d1"),
        ("e1", "passed", "d1"),
        ("h1", "waiting", "h1"),
        ("f1", "waiting", "f1"),
        ("g1", "waiting", "f1"),
    ], "a commit waits for its parent's report and is blocked by the first commit below it that has not passed"
    assert all(by_sha[sha].verdict is None for sha in ("f1", "g1", "h1")), "a waiting commit has no verdict"
    assert given[5].artifacts.coverage_report == {"current": 0.80, "previous": 0.86}, "the artifacts passed in are not changed"

    strict = verify_stack("m0", 0.85, given, [waiver], secret=SECRET, strict=True)
    assert [(s.sha, s.status, s.blocked_by) for s in strict][:5] == [
        ("a1", "passed", None),
        ("b1", "failed", "b1"),
        ("c1", "failed", "b1"),
        ("d1", "failed", "b1"),
        ("e1", "passed", "b1"),
    ], "--strict reaches every commit of the stack"
    floored = verify_stack("m0", 0.85, given, [waiver], secret=SECRET, coverage_floor=0.81)
    assert [(s.sha, s.status) for s in floored][:5] == [
        ("a1", "passed"),
        ("b1", "passed"),
        ("c1", "passed"),
        ("d1", "failed"),
        ("e1", "failed"),
    ], "the coverage floor reaches every commit of the stack"

    a1 = StackCommit("a1", "m0", stack_artifacts("a1", 0.86))
    for name, commits in (
        ("a commit stacked on one nobody gave", [a1, StackCommit("x1", "zz9", stack_artifacts("x1", 0.86))]),
        ("commits that never reach the base", [a1, StackCommit("p1", "q1", None), StackCommit("q1", "p1", None)]),
        ("a sha given twice", [a1, StackCommit("a1", "m0", None)]),
    ):
        try:
            verify_stack("m0", 0.85, commits, secret=SECRET)
        except ValueError:
            continue
        pytest.fail(f"verify_stack must refuse {name}")
