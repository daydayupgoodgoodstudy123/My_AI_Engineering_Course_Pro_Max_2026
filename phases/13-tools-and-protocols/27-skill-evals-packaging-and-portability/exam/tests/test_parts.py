import asyncio
import csv
import dataclasses
import json
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from skilleval.cases import TriggerCase
from skilleval.gate import LAYERS, EvidenceCheck, ReleaseEvidence, ReleasePolicy, TaskResult, release_gate
from skilleval.junit import Reply, junit_stream
from skilleval.manifest import RESERVED_MANIFEST_PATH, build_manifest, verify_manifest
from skilleval.metrics import trigger_report
from skilleval.portability import CAPABILITIES, UNCLAIMED, Claim, host_matrix
from skilleval.provenance import bytes_digest, observations_digest
from skilleval.runlog import COLUMNS, ObservationLog, RunObservation

SKILL = "release-readiness"
CLEAN = {"passed": True, "issues": [], "missing": [], "unexpected": [], "mismatched": []}


def make_bundle(root: Path, extra_references: int = 0) -> Path:
    """A release-readiness bundle as the lesson ships it: SKILL.md and its companion files."""
    for folder in ("references", "scripts", "assets", "evals"):
        (root / folder).mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: release-readiness\ndescription: Decide whether a tagged release can ship.\n---\n\n"
        "# Release readiness\n\nRead `references/release-policy.md`, then run `scripts/inspect_release.py`.\n",
        encoding="utf-8",
    )
    (root / "references" / "release-policy.md").write_text("# Release policy\n\nNo publish without approval.\n", encoding="utf-8")
    (root / "scripts" / "inspect_release.py").write_text("print('read-only inspection')\n", encoding="utf-8")
    (root / "assets" / "hosts.json").write_text('{"hosts": ["claude-code", "codex"]}\n', encoding="utf-8")
    (root / "assets" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (root / "evals" / "cases.json").write_text('{"cases": []}\n', encoding="utf-8")
    (root / "evals" / "manifest.json").write_text('{"suite": "trigger", "files": ["cases.json"]}\n', encoding="utf-8")
    for index in range(extra_references):
        (root / "references" / f"rule-{index:03d}.md").write_text(f"# Rule {index}\n\nCheck item {index}.\n", encoding="utf-8")
    return root


CASES = (
    TriggerCase("ship-3.1.0", "Can version 3.1.0 ship?", "positive", SKILL),
    TriggerCase("audit-tag", "Audit this tag before we publish it", "positive", SKILL),
    TriggerCase("batch-norm", "Explain batch normalization", "clear_negative", None),
    TriggerCase("build-failed", "Why did the package build fail?", "near_miss", "ci-triage"),
    TriggerCase("release-notes", "Draft the release notes", "competing", "release-notes"),
    TriggerCase("stack-trace", "Do not use release-readiness; explain this stack trace", "adversarial", None),
)
PREDICTIONS = {
    "ship-3.1.0": (SKILL, SKILL, SKILL),
    "audit-tag": (SKILL, None, SKILL),
    "batch-norm": (None, None, None),
    "build-failed": ("ci-triage", SKILL, SKILL),
    "release-notes": ("release-notes", "release-notes", SKILL),
    "stack-trace": (None, None, SKILL),
}


@pytest.mark.skip("Part 1")
def test_trigger_report_and_install_check(tmp_path) -> None:
    """The trigger report and the install check must say what the runs and the files really show."""
    report = trigger_report(CASES, PREDICTIONS, SKILL)
    assert report["metrics"] == {
        "true_positive": 5,
        "false_positive": 4,
        "true_negative": 8,
        "false_negative": 1,
        "precision": 0.5556,
        "recall": 0.8333,
        "f1": 0.6667,
        "accuracy": 0.7222,
    }, "the metrics pool every run of every case"
    assert [(case["id"], case["matched"], case["passed"]) for case in report["cases"]] == [
        ("ship-3.1.0", 3, True),
        ("audit-tag", 2, False),
        ("batch-norm", 3, True),
        ("build-failed", 1, False),
        ("release-notes", 2, False),
        ("stack-trace", 2, False),
    ], "a case passes only when every one of its runs matched"
    assert report["false_positives"] == {"clear_negative": 0, "near_miss": 2, "competing": 1, "adversarial": 1}, (
        "false positives are counted by the category of the case they happened on"
    )
    silent = trigger_report(CASES, {case.case_id: (None, None, None) for case in CASES}, SKILL)
    assert (silent["metrics"]["precision"], silent["metrics"]["recall"], silent["metrics"]["f1"]) == (0.0, 0.0, 0.0), (
        "a description that never fires scores 0, it does not crash the report"
    )

    bundle = make_bundle(tmp_path / "source" / SKILL, extra_references=200)
    manifest = build_manifest(bundle)
    installed = tmp_path / "installed" / SKILL
    shutil.copytree(bundle, installed)
    start = time.perf_counter()
    check = verify_manifest(installed, manifest)
    elapsed = time.perf_counter() - start
    assert check == CLEAN, "an untouched install matches the manifest built from its source"
    assert elapsed < 0.15, "verify_manifest should not slow down as the bundle grows"

    (installed / "references" / "release-policy.md").write_text("Publish whenever.\n", encoding="utf-8")
    (installed / "scripts" / "inspect_release.py").unlink()
    (installed / ".install-state").write_text("installer 0.9\n", encoding="utf-8")
    check = verify_manifest(installed, manifest)
    assert (check["passed"], check["mismatched"], check["missing"], check["unexpected"]) == (
        False,
        ["references/release-policy.md"],
        ["scripts/inspect_release.py"],
        [".install-state"],
    ), "an edited file, a lost file and a stale file left by an older install each show up"

    linked = tmp_path / "linked" / SKILL
    shutil.copytree(bundle, linked)
    outside = tmp_path / "outside-policy.md"
    outside.write_bytes((bundle / "references" / "release-policy.md").read_bytes())
    (linked / "references" / "release-policy.md").unlink()
    (linked / "references" / "release-policy.md").symlink_to(outside)
    check = verify_manifest(linked, manifest)
    assert not check["passed"] and any("symlink" in issue for issue in check["issues"]), (
        "a symlink in the install is refused, even when its target has the right bytes"
    )

    fresh = tmp_path / "fresh" / SKILL
    shutil.copytree(bundle, fresh)
    for canonical, written in (
        ("SKILL.md", "./SKILL.md"),
        ("references/release-policy.md", "references\\release-policy.md"),
        ("references/release-policy.md", "references//release-policy.md"),
    ):
        relabeled = {(written if key == canonical else key): digest for key, digest in manifest.items()}
        check = verify_manifest(fresh, relabeled)
        assert (check["passed"], check["issues"]) == (False, [f"invalid manifest path: {written!r}"]), (
            "manifest keys must already be canonical: they are rejected, not normalized"
        )
    for key in ("/SKILL.md", "../SKILL.md"):
        check = verify_manifest(fresh, {**manifest, key: manifest["SKILL.md"]})
        assert (check["passed"], check["issues"]) == (False, [f"invalid manifest path: {key!r}"]), (
            "absolute paths and parent segments are rejected"
        )

    shouted = "sha256:" + manifest["SKILL.md"].removeprefix("sha256:").upper()
    check = verify_manifest(fresh, {**manifest, "SKILL.md": shouted})
    assert (check["passed"], check["issues"]) == (False, ["invalid manifest digest: 'SKILL.md'"]), (
        "a digest is sha256: and lowercase hex, as written; it is not normalized either"
    )

    assert RESERVED_MANIFEST_PATH not in manifest, "the manifest never lists itself"
    assert "evals/manifest.json" in manifest, "only the exact path assets/manifest.json is reserved"
    written_manifest = json.dumps({"manifestVersion": 1, "algorithm": "sha256", "files": manifest}, indent=2)
    (fresh / RESERVED_MANIFEST_PATH).write_text(written_manifest + "\n", encoding="utf-8")
    assert verify_manifest(fresh, manifest) == CLEAN, "writing the manifest into the tree changes nothing it covers"
    own_digest = bytes_digest((fresh / RESERVED_MANIFEST_PATH).read_bytes())
    check = verify_manifest(fresh, {**manifest, RESERVED_MANIFEST_PATH: own_digest})
    assert (check["passed"], check["issues"]) == (False, [f"reserved manifest path must not be listed: {RESERVED_MANIFEST_PATH!r}"]), (
        "a manifest that lists itself is refused"
    )


OBSERVED = (
    RunObservation("ship-3.1.0", 0, "positive", SKILL, 812.0, "selected release-readiness (score 0.91)"),
    RunObservation("ship-3.1.0", 1, "positive", SKILL, 1e-07, "selected release-readiness, catalog cached"),
    RunObservation("ship-3.1.0", 2, "positive", SKILL, 1234.5678901234567, 'selected "release-readiness", 2 refs read'),
    RunObservation("audit-tag", 0, "positive", SKILL, 95.25, "matched: audit, publish"),
    RunObservation("audit-tag", 1, "positive", None, 0.1 + 0.2, "no skill matched\r\nanswered from the base model"),
    RunObservation("audit-tag", 2, "positive", SKILL, 2.5e-05, "  selected release-readiness\t"),
    RunObservation("build-failed", 0, "near_miss", "ci-triage", 100 / 3, "Build-Log geprüft; 构建失败 → ci-triage"),
    RunObservation("build-failed", 1, "near_miss", SKILL, 100.0, 'picked release-readiness: "package" matched\nfrom the description'),
    RunObservation("build-failed", 2, "near_miss", None, 7.0, ""),
)
FINISH_ORDER = (4, 8, 0, 3, 6, 2, 5, 1, 7)


@pytest.mark.skip("Part 2")
def test_observation_log_roundtrip(tmp_path) -> None:
    """Every run's raw observation survives the CSV log exactly, and so does the digest over them."""
    path = tmp_path / "observations.csv"
    worker_a, worker_b = ObservationLog(path), ObservationLog(path)
    for turn, index in enumerate(FINISH_ORDER):
        (worker_a if turn % 2 == 0 else worker_b).append(OBSERVED[index])
    loaded = ObservationLog(path).load()
    expected = {"ship-3.1.0": list(OBSERVED[0:3]), "audit-tag": list(OBSERVED[3:6]), "build-failed": list(OBSERVED[6:9])}
    assert loaded == expected, "every run reads back exactly, in run order"
    assert observations_digest(loaded) == observations_digest(expected), (
        "the digest recomputed from the log is the digest taken in memory"
    )

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == list(COLUMNS) and len(rows) == 1 + len(OBSERVED), "a plain CSV: one header row, then one row per run"
    assert rows[1] == ["audit-tag", "1", "positive", "", "0.30000000000000004", "no skill matched\r\nanswered from the base model"], (
        "an abstention is an empty cell, and a latency is written exactly"
    )

    before = path.read_bytes()
    for bad in (
        dataclasses.replace(OBSERVED[0], run=3, predicted_skill=""),
        dataclasses.replace(OBSERVED[0], run=3, predicted_skill="Release Readiness"),
        dataclasses.replace(OBSERVED[0], run=3, latency_ms=float("nan")),
        dataclasses.replace(OBSERVED[0], run=3, latency_ms=float("inf")),
        dataclasses.replace(OBSERVED[0], run=3, latency_ms=-1.0),
        dataclasses.replace(OBSERVED[0], run=3, latency_ms=5),
        dataclasses.replace(OBSERVED[0], run=3, category="paraphrase"),
    ):
        with pytest.raises(ValueError):
            worker_a.append(bad)
    assert path.read_bytes() == before, "a refused observation leaves the log as it was"

    ObservationLog(path).append(dataclasses.replace(OBSERVED[0], run=3, latency_ms=5.0))
    assert [run.latency_ms for run in ObservationLog(path).load()["ship-3.1.0"]] == [812.0, 1e-07, 1234.5678901234567, 5.0], (
        "a reopened log keeps its rows and takes more"
    )

    twice = tmp_path / "twice.csv"
    ObservationLog(twice).append(OBSERVED[0])
    with pytest.raises(ValueError):  # refused when it is appended, or when the log is read
        ObservationLog(twice).append(OBSERVED[0])
        ObservationLog(twice).load()
    gap = tmp_path / "gap.csv"
    ObservationLog(gap).append(OBSERVED[0])
    ObservationLog(gap).append(OBSERVED[2])
    with pytest.raises(ValueError):
        ObservationLog(gap).load()


GATE_CASES = (
    TriggerCase("ship", "Can version 3.1.0 ship?", "positive", SKILL),
    TriggerCase("audit", "Audit this tag before we publish it", "positive", SKILL),
    TriggerCase("candidate", "Is the 3.2.0 candidate ready to release?", "positive", SKILL),
    TriggerCase("gate", "Run the release gate on this bundle", "positive", SKILL),
    TriggerCase("build", "Why did the package build fail?", "near_miss", "ci-triage"),
    TriggerCase("rollback", "Roll back yesterday's release", "near_miss", None),
    TriggerCase("notes", "Draft the release notes", "competing", "release-notes"),
    TriggerCase("batchnorm", "Explain batch normalization", "clear_negative", None),
    TriggerCase("stack", "Do not use release-readiness; explain this stack trace", "adversarial", None),
)
GATE_PREDICTIONS = {
    "ship": (SKILL,) * 10,
    "audit": (SKILL,) * 9 + (None,),
    "candidate": (SKILL,) * 10,
    "gate": (None,) + (SKILL,) * 9,
    "build": ("ci-triage",) * 4 + (SKILL,) + ("ci-triage",) * 5,
    "rollback": (None,) * 10,
    "notes": ("release-notes",) * 9 + (SKILL,),
    "batchnorm": (None,) * 10,
    "stack": (None,) * 10,
}
TASKS = (
    TaskResult("release-report", (False, False, True, False, True), (True,) * 5),
    TaskResult("evidence-paths", (True, False, False, False, False), (False, True, True, True, True)),
    TaskResult("blocking-findings", (False,) * 5, (True, False, True, False, True)),
    TaskResult("no-publish", (True,) * 5, (True,) * 5),
)
SCRIPT_CHECKS = (
    EvidenceCheck("unit-fixtures", True, "12 fixture tests passed"),
    EvidenceCheck("repeat-run", True, "a second run gave the same report"),
)
SAFETY_CHECKS = tuple(
    EvidenceCheck(check_id, True, evidence)
    for check_id, evidence in (
        ("out-of-scope-request", "declined and named the scope"),
        ("malicious-reference", "ignored instructions inside the reference input"),
        ("path-escape", "../ reference rejected"),
        ("symlink-escape", "workspace symlink outside the root refused"),
        ("undeclared-network", "egress to an undeclared host refused"),
        ("ambient-credentials", "no command used ambient credentials"),
        ("unapproved-publish", "publish stopped at the approval prompt"),
        ("oversized-output", "output capped at 64 KiB"),
        ("skill-cycle", "a skill-to-skill cycle was stopped"),
        ("duplicate-on-resume", "a resumed run did not repeat its side effect"),
    )
)
POLICY = ReleasePolicy(required_hosts=("claude-code", "codex"), min_artifact_pass_rate=0.85)
CAPTURED = {
    "mode": "captured",
    "sources": {"triggers": "router-run-42", "artifacts": "runtime-run-42", "checks": "ci-run-42", "hosts": "host-probe-42"},
}


@pytest.mark.skip("Part 3")
def test_release_gate(tmp_path) -> None:
    """Each layer is judged on its own against thresholds declared up front; a release needs a trusted attestation."""
    bundle = make_bundle(tmp_path / "source" / SKILL)
    installed = tmp_path / "installed" / SKILL
    shutil.copytree(bundle, installed)
    evidence = ReleaseEvidence(
        skill=SKILL,
        lint_issues=("W_DESCRIPTION_NEAR_LIMIT", "W_LONG_REFERENCE"),
        cases=GATE_CASES,
        predictions=GATE_PREDICTIONS,
        tasks=TASKS,
        script_checks=SCRIPT_CHECKS,
        safety_checks=SAFETY_CHECKS,
        host_verdicts={"claude-code": "native", "codex": "degraded", "prompt-only": "blocked"},
        manifest=build_manifest(bundle),
    )

    def judge(policy=POLICY, attestation=None, trusted=None, **changes):
        return release_gate(policy, dataclasses.replace(evidence, **changes), installed, attestation, trusted)

    fixture = judge()
    assert fixture["checks"] == dict.fromkeys(LAYERS, True), (
        "every layer passes; precision, near misses and the artifact pass rate sit exactly on their thresholds"
    )
    assert [fixture[key] for key in ("checks_passed", "fixture_passed", "local_evidence_ready", "trust_anchor_valid", "passed")] == [
        True,
        True,
        False,
        False,
        False,
    ], "a fixture pass shows the gate works; it is not a release"

    regressed = (
        TASKS[0],
        TaskResult("evidence-paths", (True,) * 5, TASKS[1].with_skill),
        TaskResult("blocking-findings", (True, True, True, True, False), TASKS[2].with_skill),
        TASKS[3],
    )
    result = judge(tasks=regressed)
    assert (result["failed"], result["regressions"]) == (["no_regression"], ["evidence-paths", "blocking-findings"]), (
        "a task that got worse blocks the release even though the average went up; regressions are in task order"
    )
    uneven = (
        TaskResult("quick-check", (True,), (True,)),
        TaskResult("full-audit", (True,) * 16 + (False,) * 4, (True,) * 16 + (False,) * 4),
    )
    assert judge(tasks=uneven)["failed"] == ["artifact_pass_rate"], (
        "the artifact pass rate is over every with-skill run, not an average of task rates"
    )
    assert judge(lint_issues=("W_DESCRIPTION_NEAR_LIMIT", "name-directory"))["failed"] == ["structure"], (
        "every lint issue that is not a reviewed W_ warning is a structure error"
    )
    one_unsafe = SAFETY_CHECKS[:6] + (EvidenceCheck("unapproved-publish", False, "published without approval"),) + SAFETY_CHECKS[7:]
    assert judge(safety_checks=one_unsafe)["failed"] == ["safety"], "9 of 10 safety cases is a failed safety layer"
    flaky = (SCRIPT_CHECKS[0], EvidenceCheck("repeat-run", False, "a second run wrote a different report"))
    assert judge(script_checks=flaky)["failed"] == ["scripts"], "every script check must pass"
    assert (judge(script_checks=())["failed"], judge(safety_checks=())["failed"]) == (["scripts"], ["safety"]), (
        "a layer with no evidence has not passed"
    )
    no_near_misses = tuple(case for case in GATE_CASES if case.category != "near_miss")
    picks = {case.case_id: GATE_PREDICTIONS[case.case_id] for case in no_near_misses}
    assert judge(cases=no_near_misses, predictions=picks)["failed"] == ["near_miss"], (
        "a boundary with no near-miss cases has not been tested"
    )
    two_in_one_case = ("ci-triage",) * 3 + (SKILL, SKILL) + ("ci-triage",) * 5
    assert judge(predictions={**GATE_PREDICTIONS, "build": two_in_one_case})["failed"] == ["precision", "near_miss"], (
        "a second near-miss false positive is over the limit, even in the same case"
    )
    assert judge(host_verdicts={"claude-code": "native", "prompt-only": "native"})["failed"] == ["portability"], (
        "a required host with no verdict fails portability"
    )
    assert judge(host_verdicts={"claude-code": "adapter", "codex": "blocked"})["failed"] == ["portability"], (
        "a blocked required host fails portability"
    )

    many = tuple(TriggerCase(f"ship-{n}", f"Can build {n} ship?", "positive", SKILL) for n in range(2500)) + GATE_CASES[4:]
    picks = {case.case_id: (SKILL,) * 10 for case in many[:2500]}
    picks.update({f"ship-{n}": (None,) * 10 for n in range(500)})
    picks["ship-500"] = (None,) + (SKILL,) * 9
    picks.update({case.case_id: GATE_PREDICTIONS[case.case_id] for case in GATE_CASES[4:]})
    big = judge(policy=dataclasses.replace(POLICY, min_recall=0.8), cases=many, predictions=picks)
    assert big["triggers"]["metrics"]["recall"] == 0.8 and big["failed"] == ["recall"], (
        "thresholds are compared with the raw counts: 19999/25000 is below 0.8, though the report rounds it to 0.8"
    )

    tampered = tmp_path / "tampered" / SKILL
    shutil.copytree(bundle, tampered)
    (tampered / "references" / "release-policy.md").write_text("Publish whenever.\n", encoding="utf-8")
    result = release_gate(POLICY, evidence, tampered)
    assert (result["failed"], result["installed_tree"]["mismatched"]) == (["installed_tree"], ["references/release-policy.md"]), (
        "the installed copy is checked against the manifest"
    )

    local = judge(**CAPTURED)
    assert [local[key] for key in ("checks_passed", "fixture_passed", "local_evidence_ready", "trust_anchor_valid", "passed")] == [
        True,
        False,
        True,
        False,
        False,
    ], "relabeled evidence with sources is consistent locally, and still not a release"
    root = local["evidence_root"]
    attestation = json.dumps({"evidenceRoot": root, "attestationVersion": 1}, indent=2).encode("utf-8") + b"\n"
    trusted = bytes_digest(attestation)
    released = judge(attestation=attestation, trusted=trusted, **CAPTURED)
    assert (released["trust_anchor_valid"], released["production_ready"], released["passed"]) == (True, True, True), (
        "an attestation of the evidence root, trusted by the digest of its exact bytes, makes it a release"
    )
    loosened = dataclasses.replace(POLICY, min_precision=0.9)
    assert not judge(policy=loosened, attestation=attestation, trusted=trusted, **CAPTURED)["passed"], (
        "the evidence root binds the thresholds: changing them afterwards voids the attestation"
    )
    reordered = {**GATE_PREDICTIONS, "audit": (SKILL, None) + (SKILL,) * 8}
    assert not judge(predictions=reordered, attestation=attestation, trusted=trusted, **CAPTURED)["passed"], (
        "the evidence root binds every raw run, not just the first run and the pass rate"
    )
    shuffled = dict(reversed(list(GATE_PREDICTIONS.items())))
    assert judge(predictions=shuffled, **CAPTURED)["evidence_root"] == root, (
        "the evidence root does not depend on the order a mapping was built in"
    )
    for fake in (
        json.dumps({"attestationVersion": True, "evidenceRoot": root}).encode("utf-8"),
        json.dumps({"attestationVersion": 1.0, "evidenceRoot": root}).encode("utf-8"),
        json.dumps([1, root]).encode("utf-8"),
        b"attestationVersion=1 evidenceRoot=" + root.encode("utf-8"),
        b"\xff" + attestation,
    ):
        assert not judge(attestation=fake, trusted=bytes_digest(fake), **CAPTURED)["trust_anchor_valid"], (
            "an attestation is a JSON object with the integer attestationVersion 1"
        )
    assert not judge(attestation=attestation, trusted=bytes_digest(attestation.strip()), **CAPTURED)["passed"], (
        "the trusted digest is of the exact attestation bytes"
    )
    unsafe_root = judge(safety_checks=one_unsafe, **CAPTURED)["evidence_root"]
    unsafe_attestation = json.dumps({"attestationVersion": 1, "evidenceRoot": unsafe_root}).encode("utf-8")
    overridden = judge(safety_checks=one_unsafe, attestation=unsafe_attestation, trusted=bytes_digest(unsafe_attestation), **CAPTURED)
    assert (overridden["trust_anchor_valid"], overridden["passed"]) == (True, False), (
        "an attestation does not make up for a failed layer"
    )
    sourced_fixture = judge(sources=CAPTURED["sources"])
    fixture_attestation = json.dumps({"attestationVersion": 1, "evidenceRoot": sourced_fixture["evidence_root"]}).encode("utf-8")
    anchored = judge(attestation=fixture_attestation, trusted=bytes_digest(fixture_attestation), sources=CAPTURED["sources"])
    assert (anchored["trust_anchor_valid"], anchored["local_evidence_ready"], anchored["passed"]) == (True, False, False), (
        "a fixture run is never a release, even with sources and an attestation"
    )
    unsourced = {"mode": "captured", "sources": {**CAPTURED["sources"], "hosts": "  "}}
    assert not judge(**unsourced)["local_evidence_ready"], "captured evidence needs a source for every layer"


STREAM_CASES = (
    TriggerCase("ship-3.1.0", "Can version 3.1.0 ship?", "positive", SKILL),
    TriggerCase("audit-tag", "Audit this tag before we publish it:\nv3.1.0-rc.2", "positive", SKILL),
    TriggerCase("build-failed", "Why did <make release> fail & exit 2?", "near_miss", "ci-triage"),
    TriggerCase("release-notes", "Draft the release notes for 3.1.0", "competing", "release-notes"),
    TriggerCase("stack-trace", 'Do not use "release-readiness"; explain this stack trace', "adversarial", None),
)
# (picked skill, latency in ms, how many times the call hands the event loop back before answering)
STREAM_SCRIPT = {
    "ship-3.1.0": [(SKILL, 400.0, 1), (SKILL, 450.5, 1), (SKILL, 399.5, 1)],
    "audit-tag": [(SKILL, 820.0, 40), (None, 95.0, 40), (SKILL, 610.0, 40)],
    "build-failed": [("ci-triage", 120.0, 1), (SKILL, 130.0, 1), (SKILL, 125.0, 1)],
    "release-notes": [("release-notes", 200.0, 1), ("release-notes", 210.0, 1), ("release-notes", 190.0, 1)],
    "stack-trace": [(None, 50.0, 60), (SKILL, 60.0, 1), (None, 55.0, 1)],
}


def trace_of(case_id: str, run: int) -> str:
    picked = STREAM_SCRIPT[case_id][run][0]
    return f'{picked or "no skill"} <- matched "{case_id}" & {run + 1} of 3'


class ScriptedHost:
    """A stand-in for the target runtime: every (prompt, run) has a scripted reply, and a call hands
    the event loop back a scripted number of times before it answers, so the test decides which runs
    finish first. It records the calls, the finished runs and the peak number of calls in flight."""

    def __init__(self) -> None:
        self.case_of = {case.prompt: case.case_id for case in STREAM_CASES}
        self.calls: list[tuple[str, int]] = []
        self.finished: list[tuple[str, int]] = []
        self.active = 0
        self.peak = 0

    async def __call__(self, prompt: str, run: int) -> Reply:
        case_id = self.case_of[prompt]
        picked, latency_ms, hops = STREAM_SCRIPT[case_id][run]
        self.calls.append((case_id, run))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            for _ in range(hops):
                await asyncio.sleep(0)
        finally:
            self.active -= 1
        self.finished.append((case_id, run))
        return Reply(picked, latency_ms, trace_of(case_id, run))


def stream(host: ScriptedHost, runs: int = 3, concurrency: int = 4) -> tuple[list[str], list[list[tuple[str, int]]]]:
    """Every chunk, and which runs had finished when it arrived. A stream that stalls fails after 2 s."""

    async def drain():
        chunks, finished = [], []
        async for chunk in junit_stream(STREAM_CASES, host, SKILL, runs, concurrency):
            chunks.append(chunk)
            finished.append(list(host.finished))
        return chunks, finished

    return asyncio.run(asyncio.wait_for(drain(), timeout=2))


@pytest.mark.skip("Part 4")
def test_junit_stream() -> None:
    """Repeated runs stream to CI as JUnit XML: one testcase per case, in declared order, as soon as it can go."""
    host = ScriptedHost()
    chunks, finished = stream(host)
    suite = ET.fromstring("".join(chunks))
    assert (suite.tag, suite.get("name"), suite.get("tests")) == ("testsuite", SKILL, "5"), (
        "the suite is named after the skill and counts its cases"
    )
    testcases = suite.findall("testcase")
    assert [(tc.get("classname"), tc.get("name")) for tc in testcases] == [(c.category, c.case_id) for c in STREAM_CASES], (
        "one testcase per case, in declared order"
    )
    failures = {tc.get("name"): tc.find("failure") for tc in testcases}
    assert {name: failure.get("message") for name, failure in failures.items() if failure is not None} == {
        "audit-tag": "2/3 runs matched: Audit this tag before we publish it:\nv3.1.0-rc.2",
        "build-failed": "1/3 runs matched: Why did <make release> fail & exit 2?",
        "stack-trace": '2/3 runs matched: Do not use "release-readiness"; explain this stack trace',
    }, "a failure says how many runs matched, and attribute values reach the parser unchanged"
    assert {failure.get("type") for failure in failures.values() if failure is not None} == {"trigger-mismatch"}, (
        "every failure has the type trigger-mismatch"
    )
    assert {name: failure.text for name, failure in failures.items() if failure is not None} == {
        name: "\n".join(f"run {run}: {trace_of(name, run)}" for run in range(3)) for name in ("audit-tag", "build-failed", "stack-trace")
    }, "a failure lists every run's trace, in run order"
    assert [float(tc.get("time")) for tc in testcases] == pytest.approx([1.25, 1.525, 0.375, 0.6, 0.165]), (
        "time is the case's total router latency, in seconds"
    )
    assert {p.get("name"): p.get("value") for p in suite.iter("property")} == {"failures": "3", "runs": "15", "matched": "11"}, (
        "the suite ends with its counts: failed cases, then runs and matched runs"
    )
    assert sorted(host.calls) == sorted((case.case_id, run) for case in STREAM_CASES for run in range(3)), (
        "every case runs exactly runs times"
    )
    assert host.peak == 4, "runs of every case share the concurrency limit, and use all of it"

    assert "<testsuite" in chunks[0] and "<testcase" not in chunks[0] and finished[0] == [], (
        "the suite opens before any run has finished"
    )
    at = [index for index, chunk in enumerate(chunks) if "<testcase" in chunk]
    assert [ET.fromstring(chunks[index]).get("name") for index in at] == [case.case_id for case in STREAM_CASES], (
        "each testcase is one chunk, a complete element"
    )
    assert not {("audit-tag", run) for run in range(3)} <= set(finished[at[0]]), (
        "a case goes out as soon as it and every case before it are done"
    )
    assert {("build-failed", run) for run in range(3)} <= set(finished[at[1]]), (
        "later cases keep running while an earlier one is slow"
    )

    serial = ScriptedHost()
    again, _ = stream(serial, concurrency=1)
    assert ("".join(again), serial.peak) == ("".join(chunks), 1), "the report does not depend on the concurrency"

    idle = ScriptedHost()
    for runs, concurrency in ((0, 4), (3, 0)):
        with pytest.raises(ValueError):
            stream(idle, runs=runs, concurrency=concurrency)
    assert idle.calls == [], "bad settings are refused before any run"


REQUIRED = ("catalog-entry", "body-activation", "companion-files", "script-execution", "explicit-invocation")
OPTIONAL = ("implicit-invocation", "invocation-policy", "argument-binding")
FALLBACKS = {
    "body-activation": "explicit file loading adapter",
    "explicit-invocation": "name the skill in ordinary text",
    "implicit-invocation": "application activates explicitly",
}


def probed(overrides: dict | None = None, missing: tuple[str, ...] = ()) -> dict[str, Claim]:
    """Every capability probed as supported, except the overrides; missing ones have no claim at all."""
    claims = {name: Claim("supported", f"probe:{name}@2026-10-28") for name in CAPABILITIES if name not in missing}
    claims.update(overrides or {})
    return claims


SKILL_LOADER = "adapter:skill-loader 1.4, tested 2026-10-27"
NO_ROUTER = "contract:host docs, checked 2026-10-01"
COPIES_ENTRY = "probe:installer copies SKILL.md only@2026-10-28"
HOSTS = {
    "native-host": probed(),
    "adapter-host": probed(
        {
            "body-activation": Claim("adapter", SKILL_LOADER),
            "script-execution": Claim("adapter", "adapter:sandbox-runner 0.9, tested 2026-10-27"),
            "host-router": Claim("unsupported", NO_ROUTER),
        }
    ),
    "no-ui-host": probed(
        {
            "body-activation": Claim("adapter", SKILL_LOADER),
            "explicit-invocation": Claim("unsupported", "contract:no slash commands, checked 2026-10-01"),
        }
    ),
    "copy-entry-host": probed(
        {
            "companion-files": Claim("degraded", COPIES_ENTRY),
            "explicit-invocation": Claim("supported", " "),
        }
    ),
    "legacy-host": probed(
        {
            "host-router": Claim("degraded", "probe:router ignores invocation flags@2026-10-28"),
            "body-activation": Claim("degraded", "probe:body cut at 4000 characters@2026-10-28"),
        }
    ),
    "prompt-only-host": probed(missing=("process-tools", "host-router", "host-extension", "host-parser")),
}


def row(outcome: str, cause: str, evidence: str, required: bool = True, fallback: str | None = None) -> dict:
    return {"required": required, "outcome": outcome, "fallback": fallback, "cause": cause, "evidence": evidence}


@pytest.mark.skip("Part 5")
def test_portability_matrix() -> None:
    """A host's verdict follows from what every capability really gets there, through its dependencies."""
    matrix = host_matrix(CAPABILITIES, REQUIRED, OPTIONAL, FALLBACKS, HOSTS)
    assert {host: (result["verdict"], result["blocking"]) for host, result in matrix.items()} == {
        "native-host": ("native", []),
        "adapter-host": ("adapter", []),
        "no-ui-host": ("degraded", []),
        "copy-entry-host": ("blocked", ["companion-files", "script-execution"]),
        "legacy-host": ("blocked", ["companion-files", "script-execution"]),
        "prompt-only-host": ("blocked", ["script-execution"]),
    }, "each host's verdict and what blocks it"
    assert [matrix[host]["installable"] for host in HOSTS] == [True, True, True, False, False, False]

    adapter = matrix["adapter-host"]["capabilities"]
    assert list(adapter) == [*REQUIRED, *OPTIONAL], "required capabilities first, then optional ones"
    assert adapter["companion-files"] == row("adapter", "body-activation", SKILL_LOADER), (
        "a dependency's adapter carries over to what depends on it"
    )
    assert adapter["body-activation"] == row("adapter", "body-activation", SKILL_LOADER), (
        "a documented fallback shows only when it is in use"
    )
    assert adapter["script-execution"]["cause"] == "script-execution", (
        "a capability's own claim is the cause when nothing below it is worse"
    )
    assert adapter["implicit-invocation"] == row(
        "degraded", "host-router", NO_ROUTER, required=False, fallback="application activates explicitly"
    ), "a missing host router degrades implicit invocation to its documented fallback"
    assert adapter["invocation-policy"] == row("unsupported", "host-router", NO_ROUTER, required=False), (
        "degradation travels through every level of dependencies; an optional capability does not block"
    )
    assert matrix["no-ui-host"]["capabilities"]["argument-binding"] == row(
        "unsupported", "explicit-invocation", "contract:no slash commands, checked 2026-10-01", required=False
    )

    copied = matrix["copy-entry-host"]["capabilities"]
    assert copied["script-execution"] == row("silent-degradation", "companion-files", COPIES_ENTRY), (
        "losing companion files with no documented fallback is silent degradation, and so is everything built on it"
    )
    assert copied["explicit-invocation"] == row(
        "degraded", "explicit-invocation", UNCLAIMED, fallback="name the skill in ordinary text"
    ), "a claim without evidence is no claim"
    legacy = matrix["legacy-host"]["capabilities"]
    assert (legacy["body-activation"]["outcome"], legacy["implicit-invocation"]["cause"]) == ("degraded", "host-router"), (
        "between equally bad dependencies, the first one declared is the cause"
    )
    prompt_only = matrix["prompt-only-host"]["capabilities"]
    assert prompt_only["script-execution"] == row("unsupported", "process-tools", UNCLAIMED), (
        "a capability the host never claimed is unsupported"
    )
    assert prompt_only["invocation-policy"]["cause"] == "host-extension"

    for broken in (
        {**CAPABILITIES, "catalog-entry": ("script-execution",)},
        {**CAPABILITIES, "lifecycle-hooks": ("hook-runner",)},
        {**CAPABILITIES, "lifecycle-hooks": ("context-preservation",), "context-preservation": ("lifecycle-hooks",)},
    ):
        with pytest.raises(ValueError):
            host_matrix(broken, REQUIRED, OPTIONAL, FALLBACKS, HOSTS)
    with pytest.raises(ValueError):
        host_matrix(CAPABILITIES, REQUIRED, OPTIONAL, FALLBACKS, {"odd-host": probed({"host-router": Claim("partial", NO_ROUTER)})})
    with pytest.raises(ValueError):
        host_matrix(CAPABILITIES, (*REQUIRED, "sub-agents"), OPTIONAL, FALLBACKS, HOSTS)
    for optional, fallbacks in (
        (OPTIONAL, {**FALLBACKS, "sub-agents": "run in the current context"}),
        ((*OPTIONAL, "catalog-entry"), FALLBACKS),
    ):
        with pytest.raises(ValueError):
            host_matrix(CAPABILITIES, REQUIRED, optional, fallbacks, HOSTS)
