"""Flat model adapter: primitive types and the source's legacy list[str]."""
import copy
import math
from .descriptors import SchemaField

TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}

def check_scalar_constraints(field):
    """Given shape checks; ordering contradictions belong to compile_model.

    Container fields cannot have scalar enum/bounds. A string enum is
    nonempty, ordered, and all strings. Bounds must be finite int/float.
    """
    if field.enum is not None:
        if field.field_type is not str or not isinstance(field.enum, list) or not field.enum or any(not isinstance(x, str) for x in field.enum):
            raise ValueError("enum requires nonempty string values on str")
    for bound in (field.minimum, field.maximum):
        if bound is not None:
            if field.field_type not in (int, float) or type(bound) not in (int, float) or (type(bound) is float and not math.isfinite(bound)):
                raise ValueError("numeric bounds require finite numbers on int/float")

def python_type_to_schema(field):
    """Return an independent flat fragment; zero bounds are present bounds.

    Only primitive or legacy list is accepted; default/required do not add
    schema keywords. Recursive descriptors belong to compile_model.
    """
    check_scalar_constraints(field)
    kind = field.field_type
    if kind is list:
        schema = {"type": "array", "items": {"type": "string"}}
    elif kind in (str, int, float, bool):
        schema = {"type": TYPE_MAP[kind]}
    else:
        raise ValueError("flat adapter requires a primitive or legacy list")
    if field.enum is not None:
        schema["enum"] = copy.deepcopy(list(field.enum))
    if field.minimum is not None:
        schema["minimum"] = field.minimum
    if field.maximum is not None:
        schema["maximum"] = field.maximum
    return schema

def model_to_schema(name, fields):
    """Compile a flat ordered field table in linear field-accumulation work.

    name labels the descriptor only. Explicit required flags decide presence;
    a default annotation, including None, never decides presence/nullability.
    The returned properties and enum lists belong to this result alone.
    """
    properties = {}
    required = []
    for field_name, field in fields.items():
        fragment = python_type_to_schema(field)
        properties[field_name] = fragment
        if field.required:
            required.append(field_name)
    return {"type": "object", "properties": properties, "required": required}
