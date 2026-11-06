"""Consent policies: nested all / any / not rules over purpose, region and time."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# A rule is a JSON object with exactly one key:
#   {"all": [rule, ...]}       allows when every rule allows
#   {"any": [rule, ...]}       allows when at least one rule allows
#   {"not": rule}              allows when the rule denies
#   {"purpose": [name, ...]}   allows when the request's purpose is listed
#   {"region": [code, ...]}    allows when the request's region is listed
#   {"from": "<ISO 8601>"}     allows from that moment on
#   {"until": "<ISO 8601>"}    allows before that moment
Rule = dict


@dataclass(frozen=True)
class Request:
    purpose: str
    region: str
    at: datetime


@dataclass(frozen=True)
class Decision:
    allowed: bool
    denied_by: str | None = None


def evaluate(policy: Rule, request: Request) -> Decision:
    """Decide a request against a policy, and name the rule that denied it.

    denied_by is None when the request is allowed. Otherwise it is the JSON Pointer
    (RFC 6901, "" for the root) of the deciding rule: the first rule of an all that denies,
    an any none of whose rules allows, a not whose rule allows, or a leaf. Times in rules and
    requests must carry an offset and compare as moments. A malformed rule anywhere in the
    policy, even in a branch this request never reaches, raises ValueError.
    """
    _check(policy, "")
    if request.at.utcoffset() is None:
        raise ValueError("the request time has no offset")
    allowed, culprit = _decide(policy, request, "")
    return Decision(allowed, None if allowed else culprit)


def _check(rule: object, pointer: str) -> None:
    if not isinstance(rule, dict) or len(rule) != 1:
        raise ValueError(f"{pointer!r}: a rule is an object with exactly one key")
    ((kind, arg),) = rule.items()
    if kind in ("all", "any"):
        if not isinstance(arg, list):
            raise ValueError(f"{pointer!r}: {kind} takes a list of rules")
        for i, child in enumerate(arg):
            _check(child, f"{pointer}/{kind}/{i}")
    elif kind == "not":
        _check(arg, f"{pointer}/not")
    elif kind in ("purpose", "region"):
        if not isinstance(arg, list) or not all(isinstance(item, str) for item in arg):
            raise ValueError(f"{pointer!r}: {kind} takes a list of strings")
    elif kind in ("from", "until"):
        _moment(arg, pointer)
    else:
        raise ValueError(f"{pointer!r}: unknown rule {kind!r}")


def _moment(text: object, pointer: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{pointer!r}: {text!r} is not an ISO 8601 time") from None
    if moment.utcoffset() is None:
        raise ValueError(f"{pointer!r}: {text!r} has no offset")
    return moment


def _decide(rule: Rule, request: Request, pointer: str) -> tuple[bool, str | None]:
    ((kind, arg),) = rule.items()
    if kind == "all":
        for i, child in enumerate(arg):
            allowed, culprit = _decide(child, request, f"{pointer}/all/{i}")
            if not allowed:
                return False, culprit
        return True, None
    if kind == "any":
        for i, child in enumerate(arg):
            if _decide(child, request, f"{pointer}/any/{i}")[0]:
                return True, None
        return False, pointer
    if kind == "not":
        inner, _ = _decide(arg, request, f"{pointer}/not")
        return (not inner), (pointer if inner else None)
    if kind == "purpose":
        allowed = request.purpose in arg
    elif kind == "region":
        allowed = request.region in arg
    elif kind == "from":
        allowed = request.at >= _moment(arg, pointer)
    else:
        allowed = request.at < _moment(arg, pointer)
    return allowed, (None if allowed else pointer)
