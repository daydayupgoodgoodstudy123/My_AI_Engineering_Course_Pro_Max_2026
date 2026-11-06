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
    raise NotImplementedError
