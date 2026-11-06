"""Progressive disclosure: AGENTS.md is a map, and every rule is at most two links away."""
from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path

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
    raise NotImplementedError
