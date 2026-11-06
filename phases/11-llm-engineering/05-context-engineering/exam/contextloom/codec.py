"""Given revision codec; exact text/provenance and integer estimate metadata."""
from .models import Component, component_value

def encode_component(component):
    component_value(component)
    return {"key": component.key, "role": component.role, "text": component.text,
            "revision": component.revision, "tokens": component.tokens,
            "provenance": list(component.provenance)}

def decode_component(value):
    component = Component(value["key"], value["role"], value["text"], value["revision"], tuple(value["provenance"]))
    component_value(component)
    if type(value["tokens"]) is not int or value["tokens"] != component.tokens:
        raise ValueError("stored token estimate disagrees with text")
    return component
