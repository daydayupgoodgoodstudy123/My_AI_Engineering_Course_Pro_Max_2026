"""Audit records with the policy's sensitive values replaced by keyed digests."""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable, Iterator
from typing import Any

from .scanner import canonical_json

_SEGMENT = re.compile(r"([^.\[\]]+)((?:\[\*\])*)")


def parse_path(path: str) -> list[str | None]:
    """The steps of a policy path: a str is an object key, None means every element of a list.

    A path is object keys joined by "."; a key may be followed by one or more "[*]", each standing
    for every element of the list found there, as in "arguments.recipients[*].email". Anything
    else, an index such as [0] or an empty key included, raises ValueError.
    """
    if not isinstance(path, str) or not path:
        raise ValueError(f"cannot parse redaction path {path!r}")
    steps: list[str | None] = []
    for segment in path.split("."):
        match = _SEGMENT.fullmatch(segment)
        if match is None:
            raise ValueError(f"cannot parse redaction path {path!r}")
        steps.append(match.group(1))
        steps.extend([None] * (len(match.group(2)) // 3))
    return steps


def redact(record: Any, paths: Iterable[str], key: bytes) -> Any:
    """A copy of an audit record with the value at every policy path replaced by its keyed digest.

    Only the paths decide what is sensitive: a key with the same name anywhere else stays as it is.
    The value at a path is replaced whole, whatever it is (string, number, object, list), by
    "hmac-sha256:" followed by the hex HMAC-SHA256, under `key`, of its canonical_json. Equal values
    get equal digests in every record, whatever the key order inside them, so records can be
    matched up without storing the secret. When one path lies inside another, the outer value is
    digested as it is in the record. Every path is parsed first (parse_path); a path that leads
    nowhere in this record is skipped. The record passed in is never modified.
    """
    targets: set[tuple] = set()
    for steps in [parse_path(path) for path in paths]:
        targets.update(_locate(record, steps, ()))
    return _rebuild(record, (), targets, key)


def _locate(value: Any, steps: list[str | None], at: tuple) -> Iterator[tuple]:
    if not steps:
        yield at
        return
    step, rest = steps[0], steps[1:]
    if step is None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                yield from _locate(item, rest, at + (index,))
    elif isinstance(value, dict) and step in value:
        yield from _locate(value[step], rest, at + (step,))


def _rebuild(value: Any, at: tuple, targets: set[tuple], key: bytes) -> Any:
    if at in targets:
        return _mark(value, key)
    if isinstance(value, dict):
        return {k: _rebuild(v, at + (k,), targets, key) for k, v in value.items()}
    if isinstance(value, list):
        return [_rebuild(v, at + (i,), targets, key) for i, v in enumerate(value)]
    return value


def _mark(value: Any, key: bytes) -> str:
    digest = hmac.new(key, canonical_json(value).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"
