"""Discovered skills: the SKILL.md frontmatter that routing reads."""
from __future__ import annotations

from dataclasses import dataclass, field

# Agent Skills portable fields. Every other frontmatter field is a host extension.
PORTABLE_FIELDS = frozenset({"name", "description", "license", "compatibility", "metadata", "allowed-tools"})


@dataclass(frozen=True)
class SkillMetadata:
    """Routing identity of one discovered skill.

    runtime_extensions holds every non-portable field as the frontmatter wrote it:
    unquoted true and false are booleans, every other value is text.
    """

    name: str
    description: str
    runtime_extensions: dict[str, object] = field(default_factory=dict)


def parse_frontmatter(text: str) -> SkillMetadata:
    """Parse the frontmatter block at the top of a SKILL.md.

    The block opens and closes with a line holding only ---. In between are flat
    key: value lines. A value wrapped in single or double quotes is text without the
    quotes; unquoted true and false are booleans; any other value is text as written.
    Blank lines and lines starting with # are skipped. Whatever follows the block is
    the body, which routing never reads.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("frontmatter must open with ---")
    fields: dict[str, object] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, raw = stripped.partition(":")
        if not sep or not key.strip():
            raise ValueError(f"not a key: value line: {line!r}")
        fields[key.strip()] = _value(raw.strip())
    else:
        raise ValueError("frontmatter is not closed with ---")
    name = fields.pop("name", None)
    description = fields.pop("description", None)
    if not isinstance(name, str) or not name:
        raise ValueError("frontmatter needs a name")
    if not isinstance(description, str):
        raise ValueError(f"{name}: frontmatter needs a description")
    extensions = {key: value for key, value in fields.items() if key not in PORTABLE_FIELDS}
    return SkillMetadata(name, description, extensions)


def _value(raw: str) -> object:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    return raw
