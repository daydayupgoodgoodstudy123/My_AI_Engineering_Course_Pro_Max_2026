"""The reference graph of one skill package: what SKILL.md reaches, and in how many links."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LINK = re.compile(r"\[[^\]]*\]\(([^()\s]+)\)")


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
    raise NotImplementedError
