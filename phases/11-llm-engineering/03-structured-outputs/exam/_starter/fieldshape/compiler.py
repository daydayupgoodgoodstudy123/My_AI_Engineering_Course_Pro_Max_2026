"""Compose typed array/object descriptors using the repaired flat adapter."""
from . import flat
from .descriptors import ArrayOf, ModelSpec, SchemaField

def compile_model(model):
    """Compile a finite acyclic ModelSpec to a fresh schema tree.

    Traverse nested ModelSpec/ArrayOf in either order. A SchemaField wraps
    any field node; on array items it only supplies scalar constraints.
    required is collected independently at each object. Array cardinalities
    stay on that array; numeric bounds/enum stay on their scalar fragment.
    Use flat.python_type_to_schema for every primitive/legacy-list leaf.
    Defaults are annotation metadata only; do not emit default or nullable.

    Reject exactly these malformed declarations with ValueError:
    scalar constraints on wrong node types (the given flat shape helper),
    minimum > maximum; array sizes that are not nonnegative exact ints;
    min_items > max_items; unsupported nodes or a non-ModelSpec root.
    This is not a full schema satisfiability solver or a $ref compiler.
    """
    raise NotImplementedError
