"""The reference graph of one skill package: what SKILL.md reaches, and in how many links."""
from __future__ import annotations

import posixpath
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

LINK = re.compile(r"\[[^\]]*\]\(([^()\s]+)\)")
FENCE = re.compile(r" {0,3}(```|~~~)")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


@dataclass(frozen=True)
class ReferenceReport:
    depth: dict[str, int]
    deep: list[str]
    dead: list[str]
    directory_links: list[tuple[str, str]]
    broken: list[tuple[str, str]]


def reference_graph(package: Path) -> ReferenceReport:
    """Follow the Markdown links of a package, starting at SKILL.md.

    A link is [text](target) in a Markdown (.md) file, outside fenced code blocks (``` or ~~~);
    other files are not read for links. A target is relative to the directory of the file that
    holds the link, and its #fragment and ?query are dropped. Targets with a scheme (https:,
    mailto:) and fragment-only targets are not references. Report paths are package-relative
    POSIX paths.

    depth: every file reachable from SKILL.md, with the fewest links it takes (SKILL.md is 0).
    deep: the reachable files that take two or more links, sorted.
    dead: the files under references/ that nothing reaches, sorted.
    directory_links: (file, directory) for links that name a whole directory; they are reported
        and not followed. Sorted.
    broken: (file, target) for links to no file inside the package, a missing file or a path
        outside the package, with the target as written minus its fragment and query. Sorted.
    """
    depth = {"SKILL.md": 0}
    queue = deque(["SKILL.md"])
    directory_links: set[tuple[str, str]] = set()
    broken: set[tuple[str, str]] = set()
    while queue:
        current = queue.popleft()
        if not current.lower().endswith(".md"):
            continue
        base = posixpath.dirname(current)
        for raw in _links((package / current).read_text(encoding="utf-8")):
            target = raw.split("#", 1)[0].split("?", 1)[0]
            if not target or SCHEME.match(target):
                continue
            resolved = posixpath.normpath(posixpath.join(base, target))
            if target.startswith("/") or resolved == ".." or resolved.startswith("../"):
                broken.add((current, target))
                continue
            path = package / resolved
            if path.is_dir():
                directory_links.add((current, resolved))
            elif not path.is_file():
                broken.add((current, target))
            elif resolved not in depth:
                depth[resolved] = depth[current] + 1
                queue.append(resolved)
    references = package / "references"
    dead = sorted(
        path.relative_to(package).as_posix()
        for path in (references.rglob("*") if references.is_dir() else [])
        if path.is_file() and path.relative_to(package).as_posix() not in depth
    )
    return ReferenceReport(
        depth,
        sorted(name for name, hops in depth.items() if hops >= 2),
        dead,
        sorted(directory_links),
        sorted(broken),
    )


def _links(text: str) -> list[str]:
    targets: list[str] = []
    fence = None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = None
            continue
        if fence is None:
            targets.extend(LINK.findall(line))
    return targets
