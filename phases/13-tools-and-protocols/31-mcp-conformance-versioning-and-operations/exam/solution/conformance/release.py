"""The release gate: promote, roll back or hold, decided from redacted evidence."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from .evidence import canonical_json, digest, is_sha256_digest, redact

PIN_FIELDS = ("admissionEvidenceDigest", "artifactDigest", "descriptorDigest")
PROXY_DIGESTS = ("ingressDigest", "originDigest", "egressDigest")


@dataclass(frozen=True)
class CaseResult:
    """One transcript case after it ran, with the raw evidence it captured."""

    name: str
    passed: bool
    detail: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class HealthPolicy:
    """Health thresholds, fixed before the rollout starts."""

    min_samples: int = 100
    max_error_rate: float = 0.01
    max_p95_ms: float = 500.0


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_health(health: dict[str, Any], policy: HealthPolicy) -> tuple[bool, list[str]]:
    """Judge a canary health window against the policy. Returns (healthy, reasons).

    The window must carry sampleCount (an int, at least policy.min_samples), errorRate and
    p95Ms (ints or floats, at most their limits). An observation that is missing or of another
    type fails the window with a reason; it never stands in for a passing value.
    """
    reasons: list[str] = []
    samples = health.get("sampleCount")
    if not _is_int(samples):
        reasons.append("health window has no sample count")
    elif samples < policy.min_samples:
        reasons.append("health window has too few samples")
    error_rate = health.get("errorRate")
    if not _is_number(error_rate):
        reasons.append("health window has no error rate")
    elif not error_rate <= policy.max_error_rate:
        reasons.append("error rate exceeds the release threshold")
    p95 = health.get("p95Ms")
    if not _is_number(p95):
        reasons.append("health window has no p95 latency")
    elif not p95 <= policy.max_p95_ms:
        reasons.append("p95 latency exceeds the release threshold")
    return not reasons, reasons


def _sign(payload: dict[str, Any], signing_key: bytes) -> str:
    return hmac.new(signing_key, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def attach_rollback_attestation(
    evidence: dict[str, Any], signer: str, signing_key: bytes
) -> dict[str, Any]:
    """Return the rollback evidence with an hmac-sha256 authenticator over every other field."""
    payload = {key: value for key, value in evidence.items() if key != "authenticator"}
    return {
        **payload,
        "authenticator": {
            "algorithm": "hmac-sha256",
            "signer": signer,
            "signature": _sign(payload, signing_key),
        },
    }


def rollback_evidence_ready(rollback: Any, trusted_signers: dict[str, bytes]) -> bool:
    """A rollback target is ready only when its evidence is exact and authenticated.

    version is a non-empty string; healthy is exactly True; registryStatus is exactly the
    Registry's "active"; admissionEvidenceDigest, artifactDigest and descriptorDigest are
    SHA-256 hex digests; and authenticator is an hmac-sha256 signature, by a trusted signer,
    over every other field.
    """
    if not isinstance(rollback, dict):
        return False
    version = rollback.get("version")
    if not isinstance(version, str) or not version.strip():
        return False
    if rollback.get("healthy") is not True:
        return False
    if rollback.get("registryStatus") != "active":
        return False
    if not all(is_sha256_digest(rollback.get(field)) for field in PIN_FIELDS):
        return False
    authenticator = rollback.get("authenticator")
    if not isinstance(authenticator, dict) or authenticator.get("algorithm") != "hmac-sha256":
        return False
    signer = authenticator.get("signer")
    signature = authenticator.get("signature")
    signing_key = trusted_signers.get(signer) if isinstance(signer, str) else None
    if not isinstance(signing_key, bytes) or not isinstance(signature, str):
        return False
    payload = {key: value for key, value in rollback.items() if key != "authenticator"}
    return hmac.compare_digest(signature, _sign(payload, signing_key))


class ReleaseGate:
    """Joins transcript, SDK differential, proxy, health and rollback evidence into one decision."""

    def __init__(self, policy: HealthPolicy, trusted_signers: dict[str, bytes]) -> None:
        self.policy = policy
        self.trusted_signers = dict(trusted_signers)

    def evaluate(
        self,
        cases: list[CaseResult],
        sdk_reports: list[dict[str, Any]],
        proxy_reports: list[dict[str, Any]],
        health: dict[str, Any],
        rollback: dict[str, Any],
    ) -> dict[str, Any]:
        """Decide what happens to the candidate.

        promote: every case passed; SDK and proxy evidence is present, carries SHA-256 digests
        and passed; the health window is healthy; and the rollback target is ready.
        rollback: anything else, when the rollback target is ready. hold: anything else.

        The report holds the reasons it did not promote, the redacted evidence bundle, the
        digest of that bundle (evidenceDigest) and, by case name, the digest of each case's
        redacted evidence (caseDigests). Nothing in the report holds a secret.
        """
        reasons: list[str] = []
        if not cases:
            reasons.append("conformance transcript evidence is empty")
        reasons.extend(f"transcript failed: {case.name}" for case in cases if not case.passed)

        if not sdk_reports:
            reasons.append("SDK differential evidence is empty")
        elif not all(
            is_sha256_digest(report.get("rawDigest")) and is_sha256_digest(report.get("sdkDigest"))
            for report in sdk_reports
        ):
            reasons.append("SDK differential evidence has an invalid digest")
        reasons.extend(
            "SDK view lost or changed wire semantics"
            for report in sdk_reports
            if report.get("semanticMatch") is not True
        )

        if not proxy_reports:
            reasons.append("proxy evidence is empty")
        elif not all(
            is_sha256_digest(report.get(field)) for report in proxy_reports for field in PROXY_DIGESTS
        ):
            reasons.append("proxy evidence has an invalid digest")
        reasons.extend(
            f"proxy: {issue}" for report in proxy_reports for issue in report.get("issues", [])
        )
        reasons.extend(
            "proxy evidence did not pass"
            for report in proxy_reports
            if report.get("passed") is not True and not report.get("issues")
        )

        healthy, health_reasons = evaluate_health(health, self.policy)
        reasons.extend(health_reasons)
        ready = rollback_evidence_ready(rollback, self.trusted_signers)
        if not ready:
            reasons.append("no verified healthy rollback target")
        if not reasons:
            action = "promote"
        elif ready:
            action = "rollback"
        else:
            action = "hold"

        transcripts = self._transcripts(cases)
        case_digests = {name: digest(record["evidence"]) for name, record in transcripts.items()}
        evidence = {
            "transcripts": transcripts,
            "sdkDifferential": redact(sdk_reports),
            "proxy": redact(proxy_reports),
            "health": redact(health),
            "rollback": redact(rollback),
        }
        return {
            "action": action,
            "reasons": reasons,
            "healthy": healthy,
            "rollbackReady": ready,
            "caseDigests": case_digests,
            "evidence": evidence,
            "evidenceDigest": digest(evidence),
        }

    @staticmethod
    def _transcripts(cases: list[CaseResult]) -> dict[str, dict[str, Any]]:
        return {
            case.name: {"passed": case.passed, "detail": case.detail, "evidence": redact(case.evidence)}
            for case in cases
        }
