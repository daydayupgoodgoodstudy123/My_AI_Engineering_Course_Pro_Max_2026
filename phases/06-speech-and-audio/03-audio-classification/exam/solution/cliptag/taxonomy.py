"""Roll clip scores up an AudioSet-style label ontology."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Union

# {class name: children}. Children are a dict of named subtrees, or a list whose
# items are leaf class names or dicts of named subtrees.
Ontology = dict[str, Union["Ontology", list[Union[str, "Ontology"]]]]


def rollup(scores: dict[str, float], ontology: Ontology) -> dict[str, float]:
    """Give every class the max score found at it or anywhere below it.

    A class may sit under several parents (the ontology is a DAG written as nested trees).
    Classes with no score at or below them are left out of the result.
    """
    seen: set[str] = set()
    result: dict[str, float] = {}

    def visit(name: str, children, path: frozenset[str]) -> float | None:
        if name in path:
            raise ValueError(f"{name!r} appears inside itself")
        seen.add(name)
        best = scores.get(name)
        for child, grandchildren in _children(children):
            below = visit(child, grandchildren, path | {name})
            if below is not None and (best is None or below > best):
                best = below
        if best is not None:
            result[name] = max(best, result.get(name, best))
        return best

    for name, children in _children(ontology):
        visit(name, children, frozenset())
    unknown = sorted(set(scores) - seen)
    if unknown:
        raise ValueError(f"labels not in the ontology: {unknown}")
    return result


def _children(node) -> Iterator[tuple[str, object]]:
    if isinstance(node, dict):
        yield from node.items()
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                yield item, []
            elif isinstance(item, dict):
                yield from item.items()
            else:
                raise TypeError(f"unexpected ontology entry {item!r}")
    else:
        raise TypeError(f"unexpected ontology node {node!r}")
