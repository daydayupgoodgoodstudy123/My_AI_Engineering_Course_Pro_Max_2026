"""Durable controls promoted from observed corrections, not from one-off preferences."""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class Correction:
    symptom: str
    cause: str
    recurrence: int
    consequence: str

@dataclass(frozen=True)
class Control:
    target: str
    rule: str
    verification: str
    fingerprint: str
    symptom: str
    cause: str
    recurrence: int
    consequence: str

VERIFY = {"test":"Run the regression test", "scope":"Run the scope scenario", "automation":"Run the preflight", "example":"Run the canonical example validator", "instruction":"Run the scenario check", "human":"Record the human decision"}

def normalize_cause(cause: str) -> str:
    """Canonical cause identity: collapse whitespace, lowercase, remove final periods.

    Displayed cause and symptom remain unchanged. This is a finite identity rule, not
    semantic understanding of arbitrary paraphrases.
    """
    return " ".join(cause.split()).rstrip(".").lower()

def choose_target(correction: Correction) -> str:
    """The first matching owning layer: product disagreement, wrong result, scope,
    setup, output format, otherwise local instruction. Matching uses lowercase text.
    """
    text = (correction.symptom + " " + correction.cause).lower()
    if "product disagreement" in text:
        return "human"
    if any(x in text for x in ("regression", "wrong result", "edge case")):
        return "test"
    if any(x in text for x in ("scope", "permission", "unrelated file")):
        return "scope"
    if any(x in text for x in ("setup", "command", "environment")):
        return "automation"
    if any(x in text for x in ("format", "canonical example")):
        return "example"
    return "instruction"

def promote(correction: Correction) -> Control:
    """Make one control, preserving correction text. Consequence is minor or severe;
    recurrence is a nonnegative integer. The caller decides whether to promote yet.
    """
    if type(correction.recurrence) is not int or correction.recurrence < 0:
        raise ValueError("invalid recurrence")
    if correction.consequence not in ("minor", "severe"):
        raise ValueError("invalid consequence")
    target = choose_target(correction)
    key = target + "|" + normalize_cause(correction.cause)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return Control(target, "Prevent " + normalize_cause(correction.cause), VERIFY[target], digest,
                   correction.symptom, correction.cause, correction.recurrence, correction.consequence)

def _eligible(correction: Correction) -> bool:
    return correction.recurrence >= 2 or correction.consequence == "severe"

def ratchet(corrections: list[Correction]) -> list[Control]:
    """Promote recurring (at least two) or severe corrections. Each input is an
    independent observation with its own recurrence increment; identical observations
    are not retries. Same fingerprint counts add, first display text stays, and severe
    wins. Eligibility is evaluated after grouping. Return target/fingerprint order.
    """
    grouped: dict[str, Control] = {}
    for correction in corrections:
        control = promote(correction)
        old = grouped.get(control.fingerprint)
        if old is not None:
            control = replace(old, recurrence=old.recurrence + control.recurrence,
                              consequence="severe" if "severe" in (old.consequence, control.consequence) else "minor")
        grouped[control.fingerprint] = control
    return sorted((c for c in grouped.values() if _eligible(c)), key=lambda c:(c.target,c.fingerprint))
