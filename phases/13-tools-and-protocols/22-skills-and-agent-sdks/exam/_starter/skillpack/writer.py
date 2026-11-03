"""Write SKILL.md files in the lesson's YAML subset, readable by any YAML host."""
from __future__ import annotations


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
    raise NotImplementedError
