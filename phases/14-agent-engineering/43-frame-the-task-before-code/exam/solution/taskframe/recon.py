"""Reconnaissance: read search hits until every planned decision has a constraint."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

# The lesson's six surfaces that constrain a change, in its order.
SURFACES = ("behavior", "test", "contract", "instructions", "build", "history")

_INSTRUCTIONS = {"AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"}
_BUILD = {"Makefile", "pyproject.toml", "setup.cfg", "tox.ini", "noxfile.py"}


@dataclass(frozen=True)
class Probe:
    """One search for a planned decision: a regular expression for the hit's text, and
    the surfaces whose files can settle the decision."""

    decision: str
    pattern: str
    surfaces: tuple[str, ...]


def surface_of(path: str) -> str:
    """Which reconnaissance surface a file belongs to. The first rule that matches wins:

        instructions  AGENTS.md, CLAUDE.md or CONTRIBUTING.md, in any directory
        build         Makefile, pyproject.toml, setup.cfg, tox.ini, noxfile.py, or a file
                      under .github/workflows/
        test          a file under tests/, or one named test_*.py or *_test.py
        contract      a file under api/ or schemas/, or a .proto, .graphql or openapi.* file
        history       CHANGELOG.md, or a file under docs/adr/
        behavior      any other file: the current behavior and its callers
    """
    parts = path.split("/")
    name = parts[-1]
    if name in _INSTRUCTIONS:
        return "instructions"
    if name in _BUILD or path.startswith(".github/workflows/"):
        return "build"
    if parts[0] == "tests" or (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py"):
        return "test"
    if parts[0] in ("api", "schemas") or name.endswith((".proto", ".graphql")) or name.startswith("openapi."):
        return "contract"
    if name == "CHANGELOG.md" or path.startswith("docs/adr/"):
        return "history"
    return "behavior"


async def recon(hits: AsyncIterator[str], probes: list[Probe]) -> AsyncIterator[str]:
    """Read search hits until every probed decision has a constraint, then stop reading.

    hits yields lines as grep -n prints them, "path:line:text", without the newline. The
    path ends at the first colon and the line number at the second; the text is the rest,
    colons included. Lines that are not hits, such as the "--" between context groups,
    are skipped.

    A hit settles a decision when one of the decision's probes accepts the hit's surface
    and finds its pattern (re.search) in the hit's text. Yield each hit that settles at
    least one decision still open, once, as "path:line:text\\n", as soon as it arrives.
    Pull nothing more once every decision is settled; with no probes, pull nothing.
    """
    pending: dict[str, list[tuple[Probe, re.Pattern[str]]]] = {}
    for probe in probes:
        pending.setdefault(probe.decision, []).append((probe, re.compile(probe.pattern)))
    if not pending:
        return
    async for line in hits:
        path, sep, rest = line.partition(":")
        number, sep2, text = rest.partition(":")
        if not (sep and sep2 and path and number.isdigit()):
            continue
        surface = surface_of(path)
        settled = [
            key
            for key, checks in pending.items()
            if any(surface in probe.surfaces and rx.search(text) for probe, rx in checks)
        ]
        if not settled:
            continue
        for key in settled:
            del pending[key]
        yield f"{path}:{number}:{text}\n"
        if not pending:
            return
