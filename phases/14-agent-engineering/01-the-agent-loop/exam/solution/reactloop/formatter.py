"""The observation formatter: any tool result as a short string the model can read."""
from __future__ import annotations

import json
from typing import Any

TRUNCATED = "…[truncated]"


def format_observation(value: Any, *, max_items: int = 8, max_depth: int = 3, budget: int = 2000) -> str:
    """Render a tool result as a deterministic observation string of at most budget characters.

    - A string result is the observation as it is.
    - Inside a result, None, booleans, numbers and strings are written as JSON: strings double-quoted,
      with newlines, tabs, quotes and backslashes escaped, other characters kept as they are.
    - A dict is written {"key": value, ...} with its keys in sorted order; a list or a tuple is
      written [value, ...].
    - A container shows at most max_items entries, then "… k more" for the rest: [1, 2, … 3 more].
    - The result itself is at depth 1. A non-empty container deeper than max_depth is written {…}
      or […]; an empty one stays {} or [].
    - A container inside itself is written [cycle] where it comes round again. The same object
      reached twice along different paths is not a cycle, and is written out both times.
    - Anything else is written as the JSON string of its str().
    - A rendering longer than budget is cut so that, with TRUNCATED at its end, it is exactly budget
      characters long.

        format_observation({"b": [1, 2, 3], "a": {"x": {"y": 1}}}, max_items=2, max_depth=2)
        == '{"a": {"x": {…}}, "b": [1, 2, … 1 more]}'
    """
    text = value if isinstance(value, str) else _render(value, 1, max_items, max_depth, set())
    if len(text) > budget:
        text = text[: budget - len(TRUNCATED)] + TRUNCATED
    return text


def _render(value: Any, depth: int, max_items: int, max_depth: int, path: set[int]) -> str:
    if isinstance(value, (dict, list, tuple)):
        is_dict = isinstance(value, dict)
        opening, closing = ("{", "}") if is_dict else ("[", "]")
        if id(value) in path:
            return "[cycle]"
        if not value:
            return opening + closing
        if depth > max_depth:
            return opening + "…" + closing
        path.add(id(value))
        try:
            if is_dict:
                keys = sorted(value)[:max_items]
                parts = [
                    f"{json.dumps(key, ensure_ascii=False)}: "
                    f"{_render(value[key], depth + 1, max_items, max_depth, path)}"
                    for key in keys
                ]
            else:
                parts = [_render(item, depth + 1, max_items, max_depth, path) for item in value[:max_items]]
        finally:
            path.discard(id(value))
        if len(value) > max_items:
            parts.append(f"… {len(value) - max_items} more")
        return opening + ", ".join(parts) + closing
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)
