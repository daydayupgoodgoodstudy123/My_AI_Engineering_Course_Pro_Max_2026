"""Write agent-rules.md so that review sees exactly what changed."""
from __future__ import annotations

from .rules import Rule

TITLE = "# Agent Rules\n"


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
    raise NotImplementedError


def add_rule(text: str, rule: Rule) -> str:
    """text with one more rule at the top of its category, and nothing else changed.

    The new block, as write_rules writes it, goes right before the first rule of its category,
    with one blank line after it. When the category has no rule yet, it goes where the category
    starts: before the first rule of a later category, or at the end of the text after one
    blank line. ValueError for a rule write_rules would reject and for a slug text already has.
    """
    raise NotImplementedError


def remove_rule(text: str, slug: str) -> str:
    """text without one rule, and nothing else changed: stale rules are deleted, not commented out.

    The rule's heading and every line up to the next rule go. The last rule also takes the
    blank lines before it, so the text still ends with one newline. KeyError for an unknown slug.
    """
    raise NotImplementedError
