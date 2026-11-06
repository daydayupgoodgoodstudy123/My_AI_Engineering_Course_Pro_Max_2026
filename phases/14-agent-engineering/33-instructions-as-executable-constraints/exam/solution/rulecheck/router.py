"""Progressive disclosure: AGENTS.md is a map, and every rule is at most two links away."""
from __future__ import annotations

import posixpath
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .rules import parse_rules

LINK = re.compile(r"\[[^\]]*\]\(([^()\s]+)\)")
CODE_SPAN = re.compile(r"`[^`]*`")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
ROUTER_BUDGET = 50
MAX_HOPS = 2


@dataclass(frozen=True)
class RouterReport:
    lines: int
    hops: dict[str, int]
    too_deep: list[str]
    unreachable: list[str]
    unlinked: list[str]
    broken: list[tuple[str, str]]
    startup_violations: list[str]

    @property
    def over_budget(self) -> bool:
        """The router should stay under ROUTER_BUDGET lines, short enough to reread on every PR."""
        return self.lines >= ROUTER_BUDGET


def is_rule_file(path: str) -> bool:
    """A rule file is a Markdown file whose name starts with "agent-rules"."""
    name = posixpath.basename(path)
    return name.startswith("agent-rules") and name.endswith(".md")


def audit_router(root: Path, router: str = "AGENTS.md") -> RouterReport:
    """Check that an agent can walk from the router to every rule.

    Links are Markdown links [text](target) in .md files, outside inline code spans (`...`);
    only .md files are read for links. A target with a scheme (https:, mailto:) leaves the
    repo and is skipped. Any other target is a path relative to the file that holds it,
    optionally followed by #anchor; a target that is only #anchor points into its own file.
    A link into a rule file uses the slug of one of its rules as the anchor.

    A link resolves when its path names a file under root and, in a link into a rule file,
    its anchor (when it has one) is the slug of a rule in that file. A link that does not
    resolve is broken; a broken link whose path names a file still takes the agent to it.

    lines: the router's line count (a final newline does not start another line).
    hops: every reachable rule's slug and the fewest links it takes from the router (0) to
        the rule file that holds it; rule files are read with parse_rules.
    too_deep: the rules more than MAX_HOPS links away, sorted.
    unreachable: the rules in rule files under root that the router never reaches, sorted.
    unlinked: the topic docs (the .md files directly in docs/, rule files aside) the router
        does not link itself, sorted: a topic doc is linked by path, not described in prose.
    broken: (file, target as written) for every broken link in the files the router reaches,
        sorted. Paths are relative to root, with "/".
    startup_violations: the targets of the router's own broken links, sorted. A pointer that
        no longer resolves is a worse failure than a missing rule.
    """
    root = Path(root)
    texts: dict[str, str] = {}
    slugs: dict[str, set[str]] = {}

    def text(rel: str) -> str:
        if rel not in texts:
            texts[rel] = (root / rel).read_text(encoding="utf-8")
        return texts[rel]

    def rules_in(rel: str) -> set[str]:
        if rel not in slugs:
            slugs[rel] = {rule.slug for rule in parse_rules(text(rel))}
        return slugs[rel]

    depth = {router: 0}
    queue = deque([router])
    broken: set[tuple[str, str]] = set()
    while queue:
        current = queue.popleft()
        if not current.endswith(".md"):
            continue
        for target in _links(text(current)):
            if SCHEME.match(target):
                continue
            path, _, anchor = target.partition("#")
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(current), path)) if path else current
            outside = path.startswith("/") or resolved == ".." or resolved.startswith("../")
            if outside or not (root / resolved).is_file():
                broken.add((current, target))
                continue
            if anchor and is_rule_file(resolved) and anchor not in rules_in(resolved):
                broken.add((current, target))
            if resolved not in depth:
                depth[resolved] = depth[current] + 1
                queue.append(resolved)

    hops: dict[str, int] = {}
    unreachable: list[str] = []
    for found in sorted(root.rglob("agent-rules*.md")):
        rel = found.relative_to(root).as_posix()
        if not found.is_file():
            continue
        for slug in rules_in(rel):
            if rel in depth:
                hops[slug] = min(depth[rel], hops.get(slug, depth[rel]))
            else:
                unreachable.append(slug)
    docs = root / "docs"
    topics = sorted(
        path.relative_to(root).as_posix()
        for path in (docs.glob("*.md") if docs.is_dir() else [])
        if path.is_file() and not is_rule_file(path.name)
    )
    return RouterReport(
        lines=len(text(router).splitlines()),
        hops=hops,
        too_deep=sorted(slug for slug, n in hops.items() if n > MAX_HOPS),
        unreachable=sorted(set(unreachable) - set(hops)),
        unlinked=[topic for topic in topics if depth.get(topic) != 1],
        broken=sorted(broken),
        startup_violations=sorted(target for source, target in broken if source == router),
    )


def _links(markdown: str) -> list[str]:
    targets: list[str] = []
    for line in markdown.splitlines():
        targets.extend(LINK.findall(CODE_SPAN.sub("", line)))
    return targets
