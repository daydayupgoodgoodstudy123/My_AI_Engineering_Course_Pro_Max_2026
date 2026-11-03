"""Lint a tool registry against the lesson's design rules.

  names:        snake_case, no tense markers, no argument values, no long single words
  descriptions: 40 to 1024 characters, "Use when" and "Do not use for", no injection keywords
  schemas:      an object root, a required list, typed fields, described strings, no monolithic action
  registry:     no duplicate names
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
EMBEDDED_ARGUMENT = re.compile(r"_(in|for|at|by)_(\w+)$")
INJECTION_PATTERNS = [
    r"<system>",
    r"ignore (previous|all) (instructions|prompts)",
    r"bit\.ly|tinyurl",
    r"you must now",
]
TENSE_MARKERS = ("_was_", "_will_", "_been_", "_yesterday", "_tomorrow")
MIN_DESCRIPTION = 40
MAX_DESCRIPTION = 1024


@dataclass(frozen=True)
class Finding:
    severity: str  # block / warn / nit
    path: str  # tool name, or tool.field
    message: str

    def __str__(self) -> str:
        return f"[{self.severity:5s}] {self.path}: {self.message}"


def lint_name(name: str, params: Collection[str] = ()) -> list[Finding]:
    """Naming rules. params holds the names of the tool's parameters.

    A trailing _in_x, _for_x, _at_x or _by_x is an argument value written into the name
    (get_weather_in_tokyo) unless x is one of the parameters (get_weather_for_city(city)).
    """
    f: list[Finding] = []
    if not SNAKE_CASE.match(name):
        f.append(Finding("block", name, "name must be snake_case"))
    if any(m in name for m in TENSE_MARKERS):
        f.append(Finding("warn", name, "name includes tense marker"))
    m = EMBEDDED_ARGUMENT.search(name)
    if m and m.group(2) not in params:
        f.append(Finding("warn", name, "argument appears embedded in name"))
    if "_" not in name and len(name) > 12:
        f.append(Finding("nit", name, "long single-word name"))
    return f


def lint_description(desc: str, tool_name: str) -> list[Finding]:
    """Description rules. The length bounds count characters, like the lesson's 1024 limit."""
    f: list[Finding] = []
    length = len(desc)
    if length < MIN_DESCRIPTION:
        f.append(Finding("block", tool_name, f"description under {MIN_DESCRIPTION} chars: {length}"))
    if length > MAX_DESCRIPTION:
        f.append(Finding("block", tool_name, f"description over {MAX_DESCRIPTION} chars: {length}"))
    low = desc.lower()
    if "use when" not in low:
        f.append(Finding("warn", tool_name, "description missing 'Use when' pattern"))
    if "do not use" not in low:
        f.append(Finding("warn", tool_name, "description missing 'Do not use for' disambiguation"))
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, low):
            f.append(Finding("block", tool_name, f"possible tool-poisoning pattern: {pattern!r}"))
    return f


def lint_schema(schema: dict, tool_name: str) -> list[Finding]:
    """Schema rules for the top-level properties of a tool's input schema."""
    f: list[Finding] = []
    if schema.get("type") != "object":
        f.append(Finding("block", tool_name, "schema root must be object"))
        return f
    if "required" not in schema:
        f.append(Finding("warn", tool_name, "schema missing 'required' list"))
    props = schema.get("properties", {})
    for key, sub in props.items():
        path = f"{tool_name}.{key}"
        if "type" not in sub:
            f.append(Finding("block", path, "field has no type"))
        if sub.get("type") == "string" and "description" not in sub:
            if key not in ("id", "uuid"):
                f.append(Finding("nit", path, "string field lacks description"))
        if key == "action" and sub.get("type") == "string":
            values = sub.get("enum", [])
            if len(values) > 3 or not values:
                f.append(Finding("warn", tool_name,
                                 f"monolithic 'action' string (enum len={len(values)}); "
                                 "split into atomic tools"))
    return f


def lint_tool(tool: dict) -> list[Finding]:
    """Every finding for one tool: its name, then its description, then its schema.

    lint_name gets the tool's parameters: the properties of its input schema.
    """
    name = tool.get("name", "")
    schema = tool.get("input_schema", {})
    findings = lint_name(name, schema.get("properties", {}))
    findings.extend(lint_description(tool.get("description", ""), name))
    findings.extend(lint_schema(schema, name))
    return findings


def duplicate_names(names: list[str]) -> list[str]:
    """Every name that occurs more than once, listed once, in the order the names first appear."""
    counts = Counter(names)
    return [name for name, n in counts.items() if n > 1]


def lint_registry(registry: list[dict]) -> list[Finding]:
    """Lint a whole registry.

    Registry findings come first: one block finding per duplicated name, in the order the names
    first appear. Then every tool's own findings, in registry order.
    """
    names = [tool.get("name", "") for tool in registry]
    findings = [Finding("block", name, "duplicate tool name") for name in duplicate_names(names)]
    for tool in registry:
        findings.extend(lint_tool(tool))
    return findings


def summary_line(findings: Iterable[Finding]) -> str:
    """The lesson's report summary, e.g. 'summary: 20 findings (6 block, 11 warn, 3 nit)'."""
    counts = Counter(f.severity for f in findings)
    return (
        f"summary: {sum(counts.values())} findings "
        f"({counts['block']} block, {counts['warn']} warn, {counts['nit']} nit)"
    )
