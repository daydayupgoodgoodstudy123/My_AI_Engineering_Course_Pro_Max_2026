"""Classify what changed between two releases of a tool registry, by the lesson's versioning rules."""
from __future__ import annotations

from typing import NamedTuple


class Change(NamedTuple):
    path: str  # tool name, or tool.parameter
    change: str
    severity: str  # "breaking" or "safe"


def diff_releases(old: list[dict], new: list[dict]) -> list[Change]:
    """Every contract change from the old release to the new one, sorted by path, then change.

    Tools are matched by name only, so a renamed tool is a removal plus an addition.

      tool                     path              severity
      added                    tool              safe
      deprecated               tool              safe       gains "deprecated": true
      removed                  tool              safe if the old release marked it
                                                            "deprecated": true, else breaking
      parameter (a top-level property of input_schema)
      added optional           tool.param        safe
      added required           tool.param        breaking
      removed                  tool.param        breaking
      type changed             tool.param        breaking   any change to the set of JSON types
                                                            the parameter accepts, loosening too
      made required            tool.param        breaking
      made optional            tool.param        safe

    "type": "string" and "type": ["string"] accept the same set; a parameter without "type"
    accepts any type. A schema without "properties" has no parameters, and one without
    "required" requires nothing. Descriptions and the order of keys or of type lists are not
    part of the contract.
    """
    before = {tool["name"]: tool for tool in old}
    after = {tool["name"]: tool for tool in new}
    changes: list[Change] = []
    for name, tool in before.items():
        if name not in after:
            severity = "safe" if tool.get("deprecated") is True else "breaking"
            changes.append(Change(name, "removed", severity))
    for name, tool in after.items():
        if name not in before:
            changes.append(Change(name, "added", "safe"))
            continue
        if tool.get("deprecated") is True and before[name].get("deprecated") is not True:
            changes.append(Change(name, "deprecated", "safe"))
        changes.extend(_parameter_changes(name, before[name], tool))
    return sorted(changes)


def _parameters(tool: dict) -> tuple[dict, set[str]]:
    schema = tool.get("input_schema", {})
    return schema.get("properties", {}), set(schema.get("required", []))


def _types(prop: dict) -> frozenset[str] | None:
    """The JSON types a parameter accepts; None means any type."""
    declared = prop.get("type")
    if declared is None:
        return None
    return frozenset([declared] if isinstance(declared, str) else declared)


def _parameter_changes(name: str, old_tool: dict, new_tool: dict) -> list[Change]:
    old_props, old_required = _parameters(old_tool)
    new_props, new_required = _parameters(new_tool)
    changes = []
    for param, prop in old_props.items():
        path = f"{name}.{param}"
        if param not in new_props:
            changes.append(Change(path, "removed", "breaking"))
            continue
        if _types(prop) != _types(new_props[param]):
            changes.append(Change(path, "type changed", "breaking"))
        if param in new_required and param not in old_required:
            changes.append(Change(path, "made required", "breaking"))
        if param in old_required and param not in new_required:
            changes.append(Change(path, "made optional", "safe"))
    for param in new_props:
        if param not in old_props:
            if param in new_required:
                changes.append(Change(f"{name}.{param}", "added required", "breaking"))
            else:
                changes.append(Change(f"{name}.{param}", "added optional", "safe"))
    return changes
