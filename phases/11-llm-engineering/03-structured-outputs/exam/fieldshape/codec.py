"""Given tagged descriptor codec. This is a local file format, not a protocol.

Ordered fields are entry lists. has_default distinguishes MISSING from an
explicit JSON null. Default metadata and ordered string enums round-trip as
JSON values; numeric source spellings such as 1e0 are not retained.
"""
import json
from .descriptors import ArrayOf, ModelSpec, SchemaField, MISSING
TAGS = {str: "str", int: "int", float: "float", bool: "bool", list: "list_str"}

def encode_node(node):
    if isinstance(node, ModelSpec):
        return {"tag": "model", "name": node.name, "fields": [[name, encode_node(field)] for name, field in node.fields.items()]}
    if isinstance(node, ArrayOf):
        return {"tag": "array", "item": encode_node(node.item), "min_items": node.min_items, "max_items": node.max_items}
    if isinstance(node, SchemaField):
        out = {"tag": "field", "node": encode_node(node.field_type), "required": node.required,
               "has_default": node.default is not MISSING, "enum": node.enum,
               "minimum": node.minimum, "maximum": node.maximum}
        if node.default is not MISSING:
            out["default"] = node.default
        return out
    if node in (str, int, float, bool, list):
        return {"tag": TAGS[node]}
    raise ValueError("unsupported descriptor")

def decode_node(value):
    tag = value["tag"]
    if tag == "model":
        return ModelSpec(value["name"], {name: decode_node(field) for name, field in value["fields"]})
    if tag == "array":
        return ArrayOf(decode_node(value["item"]), value["min_items"], value["max_items"])
    if tag == "field":
        return SchemaField(decode_node(value["node"]), value["required"],
            value["default"] if value["has_default"] else MISSING,
            value["enum"], value["minimum"], value["maximum"])
    reverse = {name: kind for kind, name in TAGS.items()}
    return reverse[tag]

def snapshot_text(model):
    """Fully encode before any destination write; enum/default values are JSON."""
    return json.dumps({"format": "fieldshape-1", "model": encode_node(model)}, ensure_ascii=False, allow_nan=False)

def parse_snapshot(text):
    value = json.loads(text)
    if value["format"] != "fieldshape-1":
        raise ValueError("unsupported snapshot format")
    return decode_node(value["model"])
