"""Write agent-rules.md so that review sees exactly what changed."""
from __future__ import annotations

import re

from .rules import CATEGORIES, FIELD, SEVERITIES, Rule, parse_rules

TITLE = "# Agent Rules\n"
HEADING = re.compile(r"^## ", flags=re.MULTILINE)


def write_rules(rules: list[Rule]) -> str:
    """The agent-rules.md text for a rule set; parse_rules reads it back as the same rules.

    The text is the title line "# Agent Rules", then one block per rule, each after one
    blank line:

        ## <slug>
        - category: <category>
        - check: <check>
        - severity: <severity>
        <description>

    Rules are grouped by category in CATEGORIES order; inside a category they keep the order
    they are given in (newest first). The severity is always written, the default too. A rule
    with an empty description has no description line. A description line that parse_rules
    would not read back as itself gets one backslash in front; no other line does. The text
    ends with a newline.

    ValueError for a rule that cannot be written: an empty slug or one holding whitespace, an
    unknown category or severity, a check that is not a Python identifier, a description that
    holds a line break or has whitespace at either end, and two rules with one slug.
    """
    seen: set[str] = set()
    for rule in rules:
        _check(rule)
        if rule.slug in seen:
            raise ValueError(f"two rules are called {rule.slug}")
        seen.add(rule.slug)
    ordered = sorted(rules, key=lambda rule: CATEGORIES.index(rule.category))
    return TITLE + "".join("\n" + _block(rule) for rule in ordered)


def add_rule(text: str, rule: Rule) -> str:
    """text with one more rule at the top of its category, and nothing else changed.

    The new block, as write_rules writes it, goes right before the first rule of its category,
    with one blank line after it. When the category has no rule yet, it goes where the category
    starts: before the first rule of a later category, or at the end of the text after one
    blank line. ValueError for a rule write_rules would reject and for a slug text already has.
    """
    _check(rule)
    existing = parse_rules(text)
    if any(other.slug == rule.slug for other in existing):
        raise ValueError(f"{rule.slug} is already a rule")
    rank = CATEGORIES.index(rule.category)
    starts = [match.start() for match in HEADING.finditer(text)]
    for start, other in zip(starts, existing):
        if CATEGORIES.index(other.category) >= rank:
            return text[:start] + _block(rule) + "\n" + text[start:]
    if not text.strip():
        return write_rules([rule])
    return (text if text.endswith("\n") else text + "\n") + "\n" + _block(rule)


def remove_rule(text: str, slug: str) -> str:
    """text without one rule, and nothing else changed: stale rules are deleted, not commented out.

    The rule's heading and every line up to the next rule go. The last rule also takes the
    blank lines before it, so the text still ends with one newline. KeyError for an unknown slug.
    """
    existing = parse_rules(text)
    starts = [match.start() for match in HEADING.finditer(text)]
    for k, (start, rule) in enumerate(zip(starts, existing)):
        if rule.slug != slug:
            continue
        if k + 1 < len(starts):
            return text[:start] + text[starts[k + 1]:]
        head = text[:start].rstrip("\n")
        return head + "\n" if head else ""
    raise KeyError(slug)


def _block(rule: Rule) -> str:
    lines = [
        f"## {rule.slug}",
        f"- category: {rule.category}",
        f"- check: {rule.check}",
        f"- severity: {rule.severity}",
    ]
    if rule.description:
        lines.append(_escape(rule.description))
    return "\n".join(lines) + "\n"


def _escape(line: str) -> str:
    if line.startswith(("## ", "\\")) or FIELD.fullmatch(line):
        return "\\" + line
    return line


def _check(rule: Rule) -> None:
    if not rule.slug or any(ch.isspace() for ch in rule.slug):
        raise ValueError(f"slug {rule.slug!r} is empty or holds whitespace")
    if rule.category not in CATEGORIES:
        raise ValueError(f"{rule.slug}: unknown category {rule.category!r}")
    if rule.severity not in SEVERITIES:
        raise ValueError(f"{rule.slug}: unknown severity {rule.severity!r}")
    if not rule.check.isidentifier():
        raise ValueError(f"{rule.slug}: check {rule.check!r} is not an identifier")
    text = rule.description
    if text != text.strip() or (text and text.splitlines() != [text]):
        raise ValueError(f"{rule.slug}: a description is one line with no whitespace at either end")
