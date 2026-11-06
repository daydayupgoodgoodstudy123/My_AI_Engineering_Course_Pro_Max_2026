"""agent-rules.md: one rule per heading, read into Rule objects."""
from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORIES = ("startup", "forbidden", "definition_of_done", "uncertainty", "approval")
SEVERITIES = ("block", "warn", "info")
FIELD = re.compile(r"-\s*(category|check|severity):\s*(\S+)")


class BrokenRule(Exception):
    """A rule the workbench cannot enforce: no check, an unknown category, a check that does not resolve."""


@dataclass(frozen=True)
class Rule:
    slug: str
    category: str
    check: str
    description: str = ""
    severity: str = "block"


def parse_rules(text: str) -> list[Rule]:
    """Every rule in an agent-rules.md text, in file order.

    A rule starts at a line that begins with "## "; the rest of that line is its slug. Text
    before the first rule heading (a "# Agent Rules" title, an introduction) belongs to no
    rule, and a file may just as well start right at its first rule.

    Inside a rule, a line that matches FIELD as a whole sets that field: "- category: startup",
    "- check: state_file_fresh", "- severity: warn". Every other non-blank line is description:
    the description is those lines, stripped and joined with single spaces, in file order,
    whether they come before or after the fields. A line that starts with a backslash is
    description without that one backslash; that is how a description line that would read
    as a heading or a field is written.

    severity defaults to "block". BrokenRule for a heading with no slug, a rule with no
    category or no check, a category or severity outside CATEGORIES or SEVERITIES, a field
    set twice, or a slug used twice: a rule without a check is a wish, not a rule.
    """
    rules: list[Rule] = []
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        head, _, body = block.partition("\n")
        slug = head.strip()
        fields: dict[str, str] = {}
        prose: list[str] = []
        for raw in body.splitlines():
            line = raw.strip()
            field = FIELD.fullmatch(line)
            if line.startswith("\\"):
                prose.append(line[1:])
            elif field:
                name, value = field.groups()
                if name in fields:
                    raise BrokenRule(f"{slug}: {name} is set twice")
                fields[name] = value
            elif line:
                prose.append(line)
        rules.append(_rule(slug, fields, " ".join(prose)))
    seen: set[str] = set()
    for rule in rules:
        if rule.slug in seen:
            raise BrokenRule(f"two rules are called {rule.slug}")
        seen.add(rule.slug)
    return rules


def _rule(slug: str, fields: dict[str, str], description: str) -> Rule:
    if not slug:
        raise BrokenRule("a rule heading has no slug")
    for name in ("category", "check"):
        if name not in fields:
            raise BrokenRule(f"{slug}: no {name}; a rule without a check is a wish, not a rule")
    severity = fields.get("severity", "block")
    if fields["category"] not in CATEGORIES:
        raise BrokenRule(f"{slug}: unknown category {fields['category']!r}")
    if severity not in SEVERITIES:
        raise BrokenRule(f"{slug}: unknown severity {severity!r}")
    return Rule(slug, fields["category"], fields["check"], description, severity)
