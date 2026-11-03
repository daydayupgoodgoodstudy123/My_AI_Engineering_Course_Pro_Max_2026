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
    allowed = set(allowed_runtime_extensions)
    try:
        fields, body = parse_frontmatter(text)
    except FrontmatterSyntaxError as error:
        issue = ValidationIssue("frontmatter-syntax", str(error))
        return SkillReport(False, None, None, "", (), (), (issue,))

    name = fields.get("name") if isinstance(fields.get("name"), str) else None
    description = fields.get("description") if isinstance(fields.get("description"), str) else None
    issues: list[ValidationIssue] = []

    problem = name_issue(name, directory_name)
    if problem is not None:
        issues.append(problem)

    if description is None or not description.strip():
        issues.append(ValidationIssue("description-required", "description must explain when to use the skill"))
    elif len(description) > MAX_DESCRIPTION:
        issues.append(ValidationIssue("description-too-long", f"description must be at most {MAX_DESCRIPTION} characters"))

    if "compatibility" in fields:
        compatibility = fields["compatibility"]
        if not isinstance(compatibility, str) or not compatibility.strip():
            issues.append(ValidationIssue("compatibility-empty", "compatibility must be a non-empty string when present"))
        elif len(compatibility) > MAX_COMPATIBILITY:
            issues.append(
                ValidationIssue("compatibility-too-long", f"compatibility must be at most {MAX_COMPATIBILITY} characters")
            )

    if "metadata" in fields:
        metadata = fields["metadata"]
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
        ):
            issues.append(ValidationIssue("metadata-shape", "metadata must map string keys to string values"))

    if "allowed-tools" in fields:
        tools = fields["allowed-tools"]
        if (
            not isinstance(tools, str)
            or not tools.strip()
            or any(char.isspace() and char != " " for char in tools)
        ):
            issues.append(ValidationIssue("allowed-tools-shape", "allowed-tools must be tool names separated by spaces"))

    if not body.strip():
        issues.append(ValidationIssue("body-required", "SKILL.md needs instructions after the frontmatter"))

    extensions = sorted(set(fields) - CORE_FIELDS)
    for field in extensions:
        if field not in allowed:
            issues.append(
                ValidationIssue(
                    "unsupported-runtime-field",
                    f"{field!r} is not part of the portable contract or this host's policy",
                )
            )

    return SkillReport(
        valid=not issues,
        name=name,
        description=description,
        body=body,
        core_fields=tuple(sorted(set(fields) & CORE_FIELDS)),
        runtime_extensions=tuple(extensions),
        issues=tuple(issues),
    )
