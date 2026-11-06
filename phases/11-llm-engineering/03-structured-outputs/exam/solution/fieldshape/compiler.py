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
    if not isinstance(model, ModelSpec):
        raise ValueError("root must be ModelSpec")
    def node_schema(node):
        field = node if isinstance(node, SchemaField) else SchemaField(node)
        flat.check_scalar_constraints(field)
        if field.minimum is not None and field.maximum is not None and field.minimum > field.maximum:
            raise ValueError("minimum exceeds maximum")
        kind = field.field_type
        if isinstance(kind, ModelSpec):
            properties = {}
            required = []
            for name, child in kind.fields.items():
                properties[name] = node_schema(child)
                if child.required:
                    required.append(name)
            return {"type": "object", "properties": properties, "required": required}
        if isinstance(kind, ArrayOf):
            for bound in (kind.min_items, kind.max_items):
                if bound is not None and (type(bound) is not int or bound < 0):
                    raise ValueError("array sizes must be nonnegative integers")
            if kind.min_items is not None and kind.max_items is not None and kind.min_items > kind.max_items:
                raise ValueError("minimum array size exceeds maximum")
            schema = {"type": "array", "items": node_schema(kind.item)}
            if kind.min_items is not None:
                schema["minItems"] = kind.min_items
            if kind.max_items is not None:
                schema["maxItems"] = kind.max_items
            return schema
        return flat.python_type_to_schema(field)
    return node_schema(model)
