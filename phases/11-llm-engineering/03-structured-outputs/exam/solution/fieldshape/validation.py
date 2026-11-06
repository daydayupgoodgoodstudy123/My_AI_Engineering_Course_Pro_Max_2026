"""Given application validator for this exercise's finite schema subset.

Unknown object keys are allowed. Missing optional differs from explicit null.
No coercion, defaults, oneOf, references or full JSON Schema compliance.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ValidationIssue:
    path: tuple[str | int, ...]
    code: str
    message: str

def validate_schema(data, schema):
    issues = []
    _validate(data, schema, (), issues)
    return issues

def _validate(data, schema, path, issues):
    kind = schema.get("type")
    def add(code, message, at=path):
        issues.append(ValidationIssue(at, code, message))
    if kind == "object":
        if not isinstance(data, dict):
            add("type", "expected object")
            return
        for name in schema.get("required", []):
            if name not in data:
                add("required", "required field missing", path + (name,))
        for name, child in schema.get("properties", {}).items():
            if name in data:
                _validate(data[name], child, path + (name,), issues)
    elif kind == "array":
        if not isinstance(data, list):
            add("type", "expected array")
            return
        if len(data) < schema.get("minItems", 0):
            add("minItems", "array shorter than minimum")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            add("maxItems", "array longer than maximum")
        for index, item in enumerate(data):
            _validate(item, schema.get("items", {}), path + (index,), issues)
    elif kind == "string":
        if not isinstance(data, str):
            add("type", "expected string")
            return
        if "enum" in schema and data not in schema["enum"]:
            add("enum", "string outside allowed values")
    elif kind in ("integer", "number"):
        valid = type(data) is int if kind == "integer" else type(data) in (int, float)
        if not valid or (type(data) is float and not math.isfinite(data)):
            add("type", "expected finite " + kind)
            return
        if "minimum" in schema and data < schema["minimum"]:
            add("minimum", "number below minimum")
        if "maximum" in schema and data > schema["maximum"]:
            add("maximum", "number above maximum")
    elif kind == "boolean":
        if type(data) is not bool:
            add("type", "expected boolean")
    else:
        raise ValueError("unsupported schema type")
