"""The portable Agent Skills contract: core fields, limits and the name rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

# The two required fields and the four optional ones. Anything else is a runtime extension.
CORE_FIELDS = frozenset({"name", "description", "license", "compatibility", "metadata", "allowed-tools"})
NAME_PATTERN = re.compile(r"[a-z0-9-]+")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class SkillReport:
    """What a validator found in one SKILL.md. It is valid when there are no issues."""

    valid: bool
    name: str | None
    description: str | None
    body: str
    core_fields: tuple[str, ...]
    runtime_extensions: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]


def name_issue(name: str | None, directory_name: str) -> ValidationIssue | None:
    """The first problem with a skill's name, or None when the name is fine.

    Checked in this order: the name is missing or empty (name-required), longer than 64
    characters (name-too-long), not lowercase letters and digits joined by single hyphens
    (name-format), or not exactly the name of its directory (directory-mismatch).
    """
    if not name:
        return ValidationIssue("name-required", "name must be a non-empty string")
    if len(name) > MAX_NAME:
        return ValidationIssue("name-too-long", f"name must be at most {MAX_NAME} characters")
    if not NAME_PATTERN.fullmatch(name):
        return ValidationIssue("name-format", "name must use lowercase letters, digits and single hyphens")
    if name.lower() != directory_name.lower():
        return ValidationIssue("directory-mismatch", f"name {name!r} must match directory {directory_name!r}")
    return None
