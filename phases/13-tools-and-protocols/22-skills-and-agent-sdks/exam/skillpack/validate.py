"""Check one SKILL.md before a host puts the skill in its catalog."""
from __future__ import annotations

from collections.abc import Iterable

from .contract import (
    CORE_FIELDS,
    MAX_COMPATIBILITY,
    MAX_DESCRIPTION,
    SkillReport,
    ValidationIssue,
    name_issue,
)
from .frontmatter import FrontmatterSyntaxError, parse_frontmatter


def validate_skill_text(
    text: str,
    directory_name: str,
    allowed_runtime_extensions: Iterable[str] = (),
) -> SkillReport:
    """Validate a SKILL.md the way the lesson orders it: cheap structural checks first.

    Frontmatter that does not parse gives one issue, frontmatter-syntax, and nothing else.
    Otherwise the issues come in this order, at most one from each line:
      1. name_issue: name-required, name-too-long, name-format or directory-mismatch
      2. description-required (missing or blank), or description-too-long (over 1024)
      3. if compatibility is present: compatibility-empty (blank), or compatibility-too-long
         (over 500)
      4. if metadata is present: metadata-shape, unless it maps strings to strings
      5. if allowed-tools is present: allowed-tools-shape, unless it is a string that names
         at least one tool and separates tools with spaces only (no tabs or line breaks)
      6. body-required, when the body has no text
      7. unsupported-runtime-field, once per field outside the portable core that the host
         does not allow, in field-name order
    Lengths count characters. The report's name and description are the parsed strings (None
    when absent), core_fields and runtime_extensions list the fields present, sorted, and
    runtime_extensions lists every non-core field, allowed or not.
    """
    raise NotImplementedError
