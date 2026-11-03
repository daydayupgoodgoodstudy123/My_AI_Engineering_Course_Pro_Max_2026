"""x-mcp-header: mirror annotated arguments into Mcp-Param-* headers, and check the mirror."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .wire import HEADER_MISMATCH, ContractViolation

HEADER_PREFIX = "Mcp-Param-"
SENTINEL_PREFIX = "=?base64?"
SENTINEL_SUFFIX = "?="
JS_SAFE_INTEGER_MAX = 2**53 - 1  # 9007199254740991
JS_SAFE_INTEGER_MIN = -JS_SAFE_INTEGER_MAX
REASONS = ("missing", "duplicated", "unexpected", "malformed", "mismatched")


@dataclass(frozen=True)
class Binding:
    argument: str  # the inputSchema property
    header: str  # Mcp-Param-{x-mcp-header}, spelled as the annotation spells it
    type: str  # string, integer or boolean


def bindings(tool: dict[str, Any]) -> list[Binding]:
    """The mirrored arguments of an admitted descriptor, in inputSchema.properties order.

    Only direct members of inputSchema.properties are mirrored. Admission
    (annotations.audit_header_annotations) has already refused annotations anywhere else.
    """
    properties = tool["inputSchema"].get("properties", {})
    return [
        Binding(name, HEADER_PREFIX + schema["x-mcp-header"], schema["type"])
        for name, schema in properties.items()
        if "x-mcp-header" in schema
    ]


class HeaderRejected(ContractViolation):
    """The mirrored headers disagree with the body. reason is one of REASONS."""

    def __init__(self, header: str, reason: str) -> None:
        super().__init__(f"{header}: {reason}")
        self.header = header
        self.reason = reason


def encode_header_value(text: str) -> str:
    """The header form of an argument's text.

    The text travels plain only when it is a non-empty run of visible ASCII, "!" through "~",
    that does not start with =?base64?. Everything else becomes
    =?base64?{standard base64 of the exact UTF-8 bytes}?=. Nothing is trimmed or normalized
    first.
    """
    raise NotImplementedError


def decode_header_value(value: str) -> str:
    """The text a received header value carries.

    A value that starts with =?base64? must be the exact sentinel form: the prefix, canonical
    standard base64 of UTF-8 bytes, then ?=. It is decoded once. Any other value must be
    non-empty visible ASCII and is taken as it is. Everything else raises ContractViolation.
    """
    raise NotImplementedError


def argument_text(value: Any, declared: str) -> str:
    """The text an argument of the declared type mirrors as.

    Strings as they are; booleans as true or false; integers in base 10, within
    JS_SAFE_INTEGER_MIN..JS_SAFE_INTEGER_MAX inclusive. A value that is not of the declared
    type (a bool is not an integer), or an integer outside that range, raises ContractViolation.
    """
    raise NotImplementedError


def build_parameter_headers(
    tool: dict[str, Any], arguments: dict[str, Any], audit: list[dict[str, Any]]
) -> list[tuple[str, str]]:
    """Client side: the Mcp-Param-* headers for one tools/call, in bindings order.

    Each bound argument present in arguments becomes (binding.header, encoded text); absent
    arguments get no header, and a value argument_text refuses raises ContractViolation.
    Appends {"event": "parameter_headers_built", "headers": [names], "encoded": [names whose
    value needed the sentinel]} to audit: header names, never values.
    """
    raise NotImplementedError


def check_parameter_headers(
    tool: dict[str, Any],
    arguments: dict[str, Any],
    headers: list[tuple[str, str]],
    audit: list[dict[str, Any]],
) -> None:
    """Server side, before dispatch: every recognized Mcp-Param-* header matches the body exactly.

    headers are (name, value) pairs as received. A header is recognized when its name equals a
    binding's header without regard to case. Bindings are checked in order; for each:

        missing     the body has the argument and no header carries it
        duplicated  more than one header carries it (names that differ only in case included)
        unexpected  a header carries it and the body has no such argument
        malformed   decode_header_value refuses the value
        mismatched  the decoded text is not exactly argument_text(body value), or the body
                    value has no header form

    The first problem appends {"event": "parameter_headers_rejected", "header": binding.header,
    "reason": reason} to audit and raises HeaderRejected(binding.header, reason). When every
    binding passes, appends {"event": "parameter_headers_checked", "headers": [the bindings'
    headers that were present, in bindings order]}. The audit never holds a value, plain or
    encoded. Headers that match no binding are left alone.
    """
    raise NotImplementedError


def http_tool_call(
    tool: dict[str, Any],
    request: dict[str, Any],
    headers: list[tuple[str, str]],
    dispatch: Callable[[dict[str, Any]], dict[str, Any]],
    audit: list[dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    """The Streamable HTTP boundary for one tools/call POST: (HTTP status, JSON-RPC body).

    The mirrored headers are checked before dispatch. A rejection answers HTTP 400 with JSON-RPC
    error -32020, whose data names the header and the reason, and dispatch is never called.
    Otherwise dispatch(request) answers with HTTP 200.
    """
    try:
        check_parameter_headers(tool, request["params"].get("arguments", {}), headers, audit)
    except HeaderRejected as exc:
        return 400, {
            "jsonrpc": "2.0",
            "id": request["id"],
            "error": {
                "code": HEADER_MISMATCH,
                "message": "parameter headers do not match the request body",
                "data": {"header": exc.header, "reason": exc.reason},
            },
        }
    return 200, dispatch(request)
