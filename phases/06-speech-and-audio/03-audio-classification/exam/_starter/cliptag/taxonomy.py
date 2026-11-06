"""Roll clip scores up an AudioSet-style label ontology."""
from __future__ import annotations

from typing import Union

# {class name: children}. Children are a dict of named subtrees, or a list whose
# items are leaf class names or dicts of named subtrees.
Ontology = dict[str, Union["Ontology", list[Union[str, "Ontology"]]]]


def rollup(scores: dict[str, float], ontology: Ontology) -> dict[str, float]:
    """Give every class the max score found at it or anywhere below it.

    A class may sit under several parents (the ontology is a DAG written as nested trees).
    Classes with no score at or below them are left out of the result.
    """
    raise NotImplementedError
