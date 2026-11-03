"""Level 2 and Level 3 loading during a session, logged as one logfmt line per event."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Union

from .catalog import CatalogEntry

BRANCH = re.compile(r"- (?P<condition>[^\[\]]+?), read \[[^\]]*\]\((?P<target>[^()\s]+)\)\.?")


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
    raise NotImplementedError


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
    raise NotImplementedError
