"""Read SKILL.md: frontmatter in the lesson's YAML subset between two --- lines, then the body.

The subset: top-level `key: value` scalars, `|` and `>` block scalars, and a one-level
`metadata` map. Every value reads back as a string, and metadata as a map of strings.
"""
from __future__ import annotations

import json
import re

FIELD_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


class FrontmatterSyntaxError(ValueError):
    """The text is not frontmatter in the subset this package reads."""


def split_lines(text: str) -> list[str]:
    """Cut text into lines that keep their line endings, so "".join(split_lines(text)) == text.

    A line ends after each "\\n"; a last line without one is still a line.
    """
    lines: list[str] = []
    start = 0
    while start < len(text):
        cut = text.find("\n", start) + 1 or len(text)
        lines.append(text[start:cut])
        start = cut
    return lines


def line_content(line: str) -> str:
    """A line without its line ending, which is "\\n", or "\\r\\n" in a file saved on Windows."""
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line


def decode_scalar(raw: str) -> str:
    """Decode one scalar: plain, "double-quoted" (JSON escapes) or 'single-quoted'.

    Inside single quotes, '' stands for one '. Flow collections, anchors, aliases and tags
    ([ { & * !) are outside the subset.
    """
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise FrontmatterSyntaxError(f"invalid double-quoted scalar: {error.msg}") from error
        if not isinstance(decoded, str):
            raise FrontmatterSyntaxError("a double-quoted scalar must be a string")
        return decoded
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise FrontmatterSyntaxError("unterminated single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value[0] in "[{&*!":
        raise FrontmatterSyntaxError("unsupported YAML construct in the portable subset")
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split SKILL.md into its frontmatter fields and its body.

    The first line is exactly ---, and the frontmatter runs to the next line that is exactly
    ---. Lines end with "\\n" or "\\r\\n". Blank lines and # comment lines are skipped. A field
    is `key: scalar`; `key: |` or `key: >` takes the indented lines below it, joined with line
    breaks or with spaces; `metadata:` with no value takes the indented `key: scalar` lines
    below it as a one-level map. The body is everything after the closing line.
    """
    raw = split_lines(text)
    if not raw or line_content(raw[0]) != "---":
        raise FrontmatterSyntaxError("SKILL.md must begin with an exact --- line")
    end = 1
    while end < len(raw) and line_content(raw[end]) != "---":
        end += 1
    if end == len(raw):
        raise FrontmatterSyntaxError("frontmatter needs a closing --- line")
    lines = [line_content(line) for line in raw[:end]]

    fields: dict = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[:1].isspace() or ":" not in line:
            raise FrontmatterSyntaxError(f"malformed top-level line {index + 1}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not FIELD_NAME.fullmatch(key):
            raise FrontmatterSyntaxError(f"invalid field name {key!r}")
        if key in fields:
            raise FrontmatterSyntaxError(f"duplicate field {key!r}")
        value = raw_value.strip()
        if value in {">", "|"}:
            block: list[str] = []
            index += 1
            while index < end and (not lines[index] or lines[index][:1].isspace()):
                block.append(lines[index].lstrip())
                index += 1
            fields[key] = (" " if value == ">" else "\n").join(block).strip()
            continue
        if key == "metadata" and not value:
            nested: dict[str, str] = {}
            index += 1
            while index < end and (not lines[index] or lines[index][:1].isspace()):
                nested_line = lines[index].strip()
                if nested_line:
                    if ":" not in nested_line:
                        raise FrontmatterSyntaxError(f"malformed metadata line {index + 1}")
                    nested_key, nested_value = nested_line.split(":", 1)
                    nested_key = nested_key.strip()
                    if nested_key in nested:
                        raise FrontmatterSyntaxError(f"duplicate metadata field {nested_key!r}")
                    nested[nested_key] = decode_scalar(nested_value)
                index += 1
            fields[key] = nested
            continue
        fields[key] = decode_scalar(value)
        index += 1
    return fields, "".join(raw[end + 1 :])
