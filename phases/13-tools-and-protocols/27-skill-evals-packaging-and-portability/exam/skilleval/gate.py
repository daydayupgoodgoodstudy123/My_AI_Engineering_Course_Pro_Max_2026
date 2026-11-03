"""The release gate: thresholds declared up front, judged layer by layer, and the evidence boundaries."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .cases import TriggerCase
from .manifest import verify_manifest
from .metrics import trigger_report
from .provenance import SHA256, bytes_digest, canonical_digest

LAYERS = (
    "structure",
    "precision",
    "recall",
    "near_miss",
    "artifact_pass_rate",
    "no_regression",
    "scripts",
    "safety",
    "portability",
    "installed_tree",
)
EVIDENCE_LAYERS = ("triggers", "artifacts", "checks", "hosts")
MODES = ("fixture", "captured")
INSTALLABLE_VERDICTS = ("native", "adapter", "degraded")
ATTESTATION_VERSION = 1


@dataclass(frozen=True)
class ReleasePolicy:
    """Release thresholds, declared before anyone looks at the results."""

    required_hosts: tuple[str, ...]
    max_structure_errors: int = 0
    min_precision: float = 0.95
    min_recall: float = 0.90
    max_near_miss_false_positives: int = 1
    min_artifact_pass_rate: float = 0.90

    def __post_init__(self) -> None:
        if not self.required_hosts or len(set(self.required_hosts)) != len(self.required_hosts):
            raise ValueError("a policy names at least one required host, each once")
        for name in ("max_structure_errors", "max_near_miss_false_positives"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        for name in ("min_precision", "min_recall", "min_artifact_pass_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a number from 0 to 1")


@dataclass(frozen=True)
class TaskResult:
    """Repeated runs of one behavior task: whether each run's artifact met the contract.

    baseline and with_skill use the same model, tools, task and budget; only the skill differs.
    """

    task_id: str
    baseline: tuple[bool, ...]
    with_skill: tuple[bool, ...]


@dataclass(frozen=True)
class EvidenceCheck:
    """One explicit script or safety check: its verdict and what shows it."""

    check_id: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class ReleaseEvidence:
    """Everything one release decision rests on.

    lint_issues are the structure lint's issue codes. predictions are the router's raw picks for
    every run of every case (None: it abstained). host_verdicts maps each evaluated host to its
    portability verdict. manifest is the source bundle's manifest. mode is "fixture" for the
    deterministic lesson fixture and "captured" for results captured from the target runtime;
    sources names, for each of EVIDENCE_LAYERS, where captured results came from.
    """

    skill: str
    lint_issues: tuple[str, ...]
    cases: tuple[TriggerCase, ...]
    predictions: Mapping[str, tuple[str | None, ...]]
    tasks: tuple[TaskResult, ...]
    script_checks: tuple[EvidenceCheck, ...]
    safety_checks: tuple[EvidenceCheck, ...]
    host_verdicts: Mapping[str, str]
    manifest: Mapping[str, str]
    mode: str = "fixture"
    sources: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids) or any(not t.baseline or not t.with_skill for t in self.tasks):
            raise ValueError("tasks need unique ids and at least one run in each condition")
        for check in (*self.script_checks, *self.safety_checks):
            if type(check.passed) is not bool or not check.evidence.strip():
                raise ValueError(f"check {check.check_id!r} needs a boolean verdict and evidence")


def evidence_root(policy: ReleasePolicy, evidence: ReleaseEvidence) -> str:
    """One SHA-256 over the declared policy and every piece of evidence, raw per-run picks included.

    Equal policy and evidence give the same root, whatever order their mappings were built in.
    """
    raise NotImplementedError


def release_gate(
    policy: ReleasePolicy,
    evidence: ReleaseEvidence,
    installed_root: Path,
    attestation: bytes | None = None,
    trusted_digest: str | None = None,
) -> dict[str, object]:
    """Judge a release, one verdict per layer; no layer's result can make up for another's.

    checks maps every name in LAYERS to a bool:
      structure           every lint issue that is not a reviewed W_ warning is an error, and
                          there are at most max_structure_errors of them
      precision, recall   from trigger_report over every run, at least the minimum; thresholds
                          are compared with tp / (tp + fp) and tp / (tp + fn) from the raw
                          counts, not with the report's rounded ratios
      near_miss           the trigger set has near-miss cases, and the near-miss false positives
                          are at most max_near_miss_false_positives
      artifact_pass_rate  with-skill runs that met the artifact contract over all with-skill runs,
                          at least the minimum
      no_regression       no task's with-skill pass rate is below its baseline pass rate
      scripts, safety     at least one check, and every check passed
      portability         every required host has a verdict, and it is native, adapter or degraded
      installed_tree      verify_manifest(installed_root, evidence.manifest) passed

    checks_passed: every check passed. fixture_passed: checks passed in fixture mode.
    local_evidence_ready: captured mode, with a non-blank source for every name in EVIDENCE_LAYERS.
    trust_anchor_valid: attestation is the exact bytes whose bytes_digest is trusted_digest, and
    they decode to a JSON object whose attestationVersion is the integer 1 and whose evidenceRoot
    is this evidence_root. production_ready needs checks_passed, local_evidence_ready and
    trust_anchor_valid, and passed is production_ready.

    Also returns failed (the failed layers, in LAYERS order), regressions (the regressed task
    ids, in task order), triggers (the trigger report), installed_tree (the verify_manifest
    report) and evidence_root.
    """
    raise NotImplementedError
