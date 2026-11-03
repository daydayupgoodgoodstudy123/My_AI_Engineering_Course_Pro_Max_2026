"""SKILL.md frontmatter: the scalar subset this host reads for its catalog.

A production host should use a safe YAML parser with an explicit schema. This one reads
top-level scalars, folded (>) and literal (|) blocks and one nested metadata map, and
rejects anything else instead of guessing.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTMATTER_LIMIT = 8_192
FIELD_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


class DiscoveryError(ValueError):
    """A SKILL.md whose frontmatter this host cannot read."""


def _frontmatter_lines(skill_md: Path) -> list[str]:
    lines: list[str] = []
    consumed = 0
    with skill_md.open("r", encoding="utf-8") as handle:
        for raw in handle:
            consumed += len(raw.encode("utf-8"))
            if consumed > FRONTMATTER_LIMIT:
                raise DiscoveryError(f"frontmatter is longer than {FRONTMATTER_LIMIT} bytes")
            line = raw.rstrip("\r\n")
            if not lines and line != "---":
                break
            lines.append(line)
            if len(lines) > 1 and line == "---":
                return lines[1:-1]
    raise DiscoveryError("SKILL.md must open with a frontmatter block between --- lines")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _metadata(block: list[str]) -> dict[str, str]:
    nested: dict[str, str] = {}
    for line in block:
        if not line:
            continue
        if ":" not in line:
            raise DiscoveryError(f"malformed metadata line {line!r}")
        key, value = (part.strip() for part in line.split(":", 1))
        if not FIELD_NAME.fullmatch(key) or key in nested:
            raise DiscoveryError(f"invalid metadata field {key!r}")
        nested[key] = _unquote(value)
    return nested


def parse_frontmatter(skill_md: Path) -> dict:
    """The frontmatter fields of a SKILL.md, without reading its instruction body.

    Values are strings, except metadata, which is a dict of strings. name and description
    are required and non-empty.
    """
    lines = _frontmatter_lines(skill_md)
    fields: dict = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() or ":" not in line:
            raise DiscoveryError(f"malformed frontmatter line {line!r}")
        key, value = (part.strip() for part in line.split(":", 1))
        if not FIELD_NAME.fullmatch(key):
            raise DiscoveryError(f"invalid frontmatter field {key!r}")
        if key in fields:
            raise DiscoveryError(f"duplicate frontmatter field {key!r}")
        if value in {">", "|"} or (key == "metadata" and not value):
            block: list[str] = []
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                block.append(lines[index].strip())
                index += 1
            if key == "metadata":
                fields[key] = _metadata(block)
            else:
                fields[key] = (" " if value == ">" else "\n").join(block).strip()
        else:
            fields[key] = _unquote(value)
    for required in ("name", "description"):
        if not isinstance(fields.get(required), str) or not fields[required]:
            raise DiscoveryError(f"frontmatter needs a non-empty {required}")
    return fields


def load_body(skill_md: Path) -> str:
    """The instruction body of a SKILL.md: everything after the frontmatter, trimmed."""
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise DiscoveryError("SKILL.md must open with a frontmatter block between --- lines")
    end = lines.index("---", 1)
    return "\n".join(lines[end + 1 :]).strip()
