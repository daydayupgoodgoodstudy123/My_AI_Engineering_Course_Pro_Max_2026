"""Given descriptor declarations. Defaults are annotations, not nullability."""
from dataclasses import dataclass
from typing import Any, Mapping

class _Missing:
    def __repr__(self):
        return "MISSING"
    def __deepcopy__(self, memo):
        return self
MISSING = _Missing()

@dataclass(frozen=True)
class SchemaField:
    """required controls a model key; default is never injected or compiled.

    field_type is str/int/float/bool, legacy list[str] (spelled list),
    ArrayOf, or ModelSpec. enum is a nonempty list of strings for str;
    minimum/maximum are finite numeric bounds for int/float only.
    """
    field_type: Any
    required: bool = True
    default: Any = MISSING
    enum: Any = None
    minimum: Any = None
    maximum: Any = None

@dataclass(frozen=True)
class ArrayOf:
    """Typed items may themselves be primitive, ArrayOf, ModelSpec or SchemaField.

    A SchemaField item wrapper carries scalar constraints, not key presence:
    its required/default annotations have no effect on element existence.
    min_items/max_items must be nonnegative exact integers when supplied.
    """
    item: Any
    min_items: int | None = None
    max_items: int | None = None

@dataclass(frozen=True)
class ModelSpec:
    """Ordered string-key fields. name is a label, not a reference registry."""
    name: str
    fields: Mapping[str, SchemaField]
