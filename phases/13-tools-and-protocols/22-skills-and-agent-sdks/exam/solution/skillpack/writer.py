"""Write SKILL.md files in the lesson's YAML subset, readable by any YAML host."""
from __future__ import annotations

import json

from .contract import CORE_FIELDS
from .frontmatter import FIELD_NAME

INDICATORS = frozenset("-?:,[]{}#&*!|>'\"%@`")
YAML_WORDS = frozenset({"true", "false", "yes", "no", "on", "off", "null"})


def render_skill(fields: dict, body: str) -> str:
    """Write a SKILL.md that parse_frontmatter reads back as exactly (fields, body).

    The fields come in the order given, one `key: value` line each, between two --- lines,
    and the body follows the closing line exactly as given. Every value is a string, except
    that metadata may be a non-empty map of strings, written as indented `key: value` lines.
    Keys, metadata keys included, follow the field-name rule. Anything else is a ValueError.

    A value is written plain when YAML reads it back as the same string, and otherwise as a
    JSON string in double quotes (json.dumps with ensure_ascii=False). It needs quotes when it
      - is empty, or starts or ends with whitespace;
      - starts with one of  - ? : , [ ] { } # & * ! | > ' " % @ `
      - contains ": " or " #", or ends with ":";
      - contains a character that str.isprintable() rejects;
      - is the value of a core field or a metadata entry and YAML would read it as a number,
        a boolean or null: it starts with a digit, ".", "+" or "~", or it is true, false, yes,
        no, on, off or null in any capitalization. Runtime extension fields are typed by their
        host, so `user-invocable: false` stays plain.
    A top-level value with line breaks becomes a `|` block instead, each line indented by two
    spaces and empty lines left empty, when it has no "\\r", does not start or end with
    whitespace, and every line is printable and does not start with whitespace.
    """
    out = ["---\n"]
    for key, value in fields.items():
        _check_key(key)
        if key == "metadata" and isinstance(value, dict):
            if not value:
                raise ValueError("metadata needs at least one entry")
            out.append("metadata:\n")
            for entry, text in value.items():
                _check_key(entry)
                if not isinstance(text, str):
                    raise ValueError(f"metadata {entry!r} must be a string")
                out.append(f"  {entry}: {_scalar(text, typed=True)}\n")
        elif isinstance(value, str):
            if _block_ok(value):
                out.append(f"{key}: |\n")
                out.extend(f"  {line}\n" if line else "\n" for line in value.split("\n"))
            else:
                out.append(f"{key}: {_scalar(value, typed=key in CORE_FIELDS)}\n")
        else:
            raise ValueError(f"{key!r} must be a string")
    out.append("---\n")
    return "".join(out) + body


def _check_key(key: object) -> None:
    if not isinstance(key, str) or not FIELD_NAME.fullmatch(key):
        raise ValueError(f"{key!r} is not a field name the frontmatter can hold")


def _scalar(value: str, typed: bool) -> str:
    return value if _plain_ok(value, typed) else json.dumps(value, ensure_ascii=False)


def _plain_ok(value: str, typed: bool) -> bool:
    if not value or value != value.strip() or value[0] in INDICATORS:
        return False
    if ": " in value or " #" in value or value.endswith(":") or not value.isprintable():
        return False
    if typed and (value[0] in "0123456789.+~" or value.lower() in YAML_WORDS):
        return False
    return True


def _block_ok(value: str) -> bool:
    if "\n" not in value or "\r" in value or value != value.strip():
        return False
    return all(line.isprintable() and not line[:1].isspace() for line in value.split("\n"))
