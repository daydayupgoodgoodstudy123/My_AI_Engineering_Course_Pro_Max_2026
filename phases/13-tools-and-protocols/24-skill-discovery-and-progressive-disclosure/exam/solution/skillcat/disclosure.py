"""Level 2 and Level 3 loading during a session, logged as one logfmt line per event."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from .catalog import CatalogEntry
from .frontmatter import load_body
from .resources import ReferencePathError, validate_reference

BRANCH = re.compile(r"- (?P<condition>[^\[\]]+?), read \[[^\]]*\]\((?P<target>[^()\s]+)\)\.?")
BARE_VALUE = re.compile(r'[^\s"=\\\x00-\x1f\x7f]+')
ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


@dataclass(frozen=True)
class Activate:
    skill: str


@dataclass(frozen=True)
class Read:
    skill: str
    resource: str
    reason: str


Request = Union[Activate, Read]


def decision_map(body: str) -> dict[str, str]:
    """The branches a SKILL.md body declares, as {resource: condition}.

    A branch is a list item such as
    "- For a Python package, read [python-release.md](references/python-release.md)."
    """
    branches: dict[str, str] = {}
    for line in body.splitlines():
        match = BRANCH.fullmatch(line.strip())
        if match:
            branches.setdefault(match["target"], match["condition"])
    return branches


def format_event(fields: list[tuple[str, object]]) -> str:
    r"""One logfmt line: key=value pairs in the given order, one space apart, then a newline.

    A value that is empty or holds whitespace, '"', '=', a backslash or a control character is
    quoted: wrapped in double quotes, with backslash, double quote, newline, carriage return and
    tab written as \\, \", \n, \r and \t, and any other control character as \u00XX. Every
    other value is written bare.
    """
    return " ".join(f"{key}={_logfmt_value(str(value))}" for key, value in fields) + "\n"


def _logfmt_value(text: str) -> str:
    if BARE_VALUE.fullmatch(text):
        return text
    out = []
    for char in text:
        if char in ESCAPES:
            out.append(ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


async def disclosure_events(
    requests: AsyncIterator[Request],
    entries: Iterable[CatalogEntry],
    max_read_bytes: int = 4096,
) -> AsyncIterator[str]:
    """Serve a session's activations and reads as they arrive, one event line per request.

    Each line is yielded as soon as its request is handled. Content is never logged.

    Activate(skill) for a skill in entries loads its SKILL.md body (frontmatter.load_body):
        event=skill.activated skill=<name> bytes=<UTF-8 bytes of the body>
    Activate(skill) for any other name:
        event=skill.refused skill=<name> reason=not_in_catalog
    Read(skill, resource, reason) loads the file when the skill is active in this session,
    its SKILL.md declares the resource as a branch (decision_map), resources.validate_reference
    accepts it, and it holds at most max_read_bytes bytes:
        event=skill.resource.loaded skill=<name> resource=<resource> reason=<reason> bytes=<file bytes>
    Otherwise the read is refused with the first of these that applies, in this order:
        event=skill.resource.refused skill=<name> resource=<resource> reason=<not_active|not_declared|invalid_path|too_large>

    Lines are written with format_event.
    """
    catalog = {entry.name: entry for entry in entries}
    active: dict[str, dict[str, str]] = {}
    async for request in requests:
        if isinstance(request, Activate):
            entry = catalog.get(request.skill)
            if entry is None:
                yield format_event([("event", "skill.refused"), ("skill", request.skill), ("reason", "not_in_catalog")])
                continue
            body = load_body(Path(entry.source) / "SKILL.md")
            active[request.skill] = decision_map(body)
            yield format_event(
                [("event", "skill.activated"), ("skill", request.skill), ("bytes", len(body.encode("utf-8")))]
            )
            continue
        loaded = _read(request, catalog, active, max_read_bytes)
        if isinstance(loaded, str):
            yield format_event(
                [
                    ("event", "skill.resource.refused"),
                    ("skill", request.skill),
                    ("resource", request.resource),
                    ("reason", loaded),
                ]
            )
        else:
            yield format_event(
                [
                    ("event", "skill.resource.loaded"),
                    ("skill", request.skill),
                    ("resource", request.resource),
                    ("reason", request.reason),
                    ("bytes", len(loaded)),
                ]
            )


def _read(
    request: Read,
    catalog: dict[str, CatalogEntry],
    active: dict[str, dict[str, str]],
    max_read_bytes: int,
) -> Union[str, bytes]:
    """The file's bytes, or the refusal reason."""
    branches = active.get(request.skill)
    if branches is None:
        return "not_active"
    if request.resource not in branches:
        return "not_declared"
    try:
        target = validate_reference(Path(catalog[request.skill].source), request.resource)
    except ReferencePathError:
        return "invalid_path"
    with target.open("rb") as handle:
        data = handle.read(max_read_bytes + 1)
    if len(data) > max_read_bytes:
        return "too_large"
    return data
