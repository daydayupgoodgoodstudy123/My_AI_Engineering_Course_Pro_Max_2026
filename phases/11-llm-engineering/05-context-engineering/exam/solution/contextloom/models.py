"""Given local state descriptors; provenance is independent of summary text."""
from dataclasses import dataclass
import math
from .primitives import count_tokens

@dataclass(frozen=True)
class Component:
    key: str
    role: str
    text: str
    revision: int
    provenance: tuple[str, ...] = ()

    @property
    def tokens(self):
        return count_tokens(self.text)

@dataclass(frozen=True)
class ScoredDocument:
    component: Component
    score: float

@dataclass(frozen=True)
class Exchange:
    key: str
    user: str
    assistant: str

def component_value(component):
    if not isinstance(component, Component) or not isinstance(component.key, str) or not component.key or component.key in ("system", "query"):
        raise ValueError("component requires a nonempty key")
    if component.role not in ("retrieved", "history", "summary", "tool", "example") or not isinstance(component.text, str):
        raise ValueError("invalid component role or text")
    if type(component.revision) is not int or component.revision < 1:
        raise ValueError("revision must be a positive integer")
    if not isinstance(component.provenance, tuple) or any(not isinstance(value, str) for value in component.provenance):
        raise ValueError("provenance must be a tuple of string ids")
    return component

def scored_values(documents, scores):
    if len(documents) != len(scores):
        raise ValueError("document and score lengths must agree")
    for component, score in zip(documents, scores):
        component_value(component)
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("relevance score must be finite within [0,1]")
    return documents, scores
