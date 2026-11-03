"""OTLP/JSON for spans: what the exporter sends and what the span log stores.

A finished span is written as

    {"traceId": "<32 hex>", "spanId": "<16 hex>", "parentSpanId": "<16 hex>", or "" for a span with no parent,
     "name": "...", "kind": SPAN_KIND[kind],
     "startTimeUnixNano": "<decimal>", "endTimeUnixNano": "<decimal>",
     "attributes": [{"key": "...", "value": <AnyValue>}, ...],
     "events": [{"timeUnixNano": "<decimal>", "name": "...", "attributes": [...]}, ...]}

Timestamps and integer values are decimal strings: they are 64-bit integers, and a reader whose JSON
numbers are doubles (JavaScript, jq) would round anything above 2**53. Attributes and events keep their
order.
"""
from __future__ import annotations

import re

from .tracer import AttrValue, Event, Span

SPAN_KIND = {"INTERNAL": 1, "SERVER": 2, "CLIENT": 3}
KIND_NAMES = {number: name for name, number in SPAN_KIND.items()}
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX16 = re.compile(r"[0-9a-f]{16}")
_DECIMAL = re.compile(r"-?[0-9]+")


def encode_value(value: AttrValue) -> dict:
    """The OTLP AnyValue for one attribute value.

        str   -> {"stringValue": value}
        bool  -> {"boolValue": value}
        int   -> {"intValue": "<decimal>"}
        float -> {"doubleValue": value}
        list  -> {"arrayValue": {"values": [<AnyValue>, ...]}}

    Anything else raises ValueError: an int outside the signed 64-bit range, a list whose items are not
    all of one of the four scalar types (bool and int count as different types here, and so do int and
    float), a nested list, None, a dict.
    """
    raise NotImplementedError


def encode_attributes(attrs: dict[str, AttrValue]) -> list[dict]:
    return [{"key": key, "value": encode_value(value)} for key, value in attrs.items()]


def to_otlp(span: Span) -> dict:
    """The OTLP/JSON object for a finished span, as the module docstring lays it out.

    A span that has not ended has nothing to put in endTimeUnixNano: ValueError.
    """
    raise NotImplementedError


def decode_value(value: dict) -> AttrValue:
    """The attribute value an AnyValue written by encode_value stands for."""
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError(f"not an AnyValue: {value!r}")
    ((tag, raw),) = value.items()
    if tag == "stringValue" and isinstance(raw, str):
        return raw
    if tag == "boolValue" and isinstance(raw, bool):
        return raw
    if tag == "intValue" and isinstance(raw, str) and _DECIMAL.fullmatch(raw):
        return int(raw)
    if tag == "doubleValue" and isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if tag == "arrayValue" and isinstance(raw, dict):
        return [decode_value(item) for item in raw.get("values", [])]
    raise ValueError(f"bad AnyValue {value!r}")


def decode_attributes(items: list[dict]) -> dict[str, AttrValue]:
    return {item["key"]: decode_value(item["value"]) for item in items}


def from_otlp(obj: dict) -> Span:
    """The Span an OTLP/JSON object written by to_otlp stands for."""
    trace_id, span_id = obj["traceId"], obj["spanId"]
    parent = obj.get("parentSpanId") or ""
    if not (_HEX32.fullmatch(trace_id) and _HEX16.fullmatch(span_id) and (not parent or _HEX16.fullmatch(parent))):
        raise ValueError(f"bad ids in span {obj.get('name')!r}")
    kind = obj["kind"]
    if isinstance(kind, bool) or kind not in KIND_NAMES:
        raise ValueError(f"unknown span kind {kind!r}")
    return Span(
        name=obj["name"],
        kind=KIND_NAMES[kind],
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent or None,
        start_ns=_nanos(obj["startTimeUnixNano"]),
        end_ns=_nanos(obj["endTimeUnixNano"]),
        attrs=decode_attributes(obj.get("attributes", [])),
        events=[
            Event(event["name"], _nanos(event["timeUnixNano"]), decode_attributes(event.get("attributes", [])))
            for event in obj.get("events", [])
        ],
    )


def _nanos(raw: object) -> int:
    if not isinstance(raw, str) or not _DECIMAL.fullmatch(raw):
        raise ValueError(f"a timestamp is a decimal string of nanoseconds, got {raw!r}")
    return int(raw)
