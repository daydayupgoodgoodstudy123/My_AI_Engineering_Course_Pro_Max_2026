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
    raise NotImplementedError
