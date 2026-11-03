"""Admission and consumption checks: tool descriptors, content blocks and tool results."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from .schema import check_schema, validate_json_schema
from .wire import ContractViolation


def validate_tool_descriptor(tool: Any) -> None:
    """Admission checks for one tools/list entry.

    The name is a non-empty string, inputSchema is an object schema ("type": "object") and
    outputSchema, when the tool publishes one, is a schema. Both must pass check_schema.
    """
    if not isinstance(tool, dict):
        raise ContractViolation("a tool descriptor must be an object")
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise ContractViolation("tool name must be a non-empty string")
    input_schema = tool.get("inputSchema")
    if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
        raise ContractViolation("inputSchema must be an object schema")
    check_schema(input_schema, "$.inputSchema")
    if "outputSchema" in tool:
        check_schema(tool["outputSchema"], "$.outputSchema")


def _check_base64(value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise ContractViolation(f"{where} must be a base64 string")
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ContractViolation(f"{where} is not standard base64") from exc


def validate_content_block(block: Any, where: str = "$") -> None:
    """Check one content block before the host uses it.

    text           {"type": "text", "text": str}
    image, audio   {"type", "data": standard base64, "mimeType": "image/..." or "audio/..."}
    resource_link  {"type", "uri": str, "name": str, "mimeType"?: str}; the link is not followed
    resource       {"type", "resource": {"uri": str, "mimeType"?: str, and exactly one of
                   "text": str or "blob": standard base64}}
    Any other type is refused.
    """
    if not isinstance(block, dict):
        raise ContractViolation(f"{where}: a content block must be an object")
    kind = block.get("type")
    if kind == "text":
        if not isinstance(block.get("text"), str):
            raise ContractViolation(f"{where}: text content needs text")
    elif kind in ("image", "audio"):
        _check_base64(block.get("data"), f"{where}.data")
        mime = block.get("mimeType")
        if not isinstance(mime, str) or not mime.startswith(f"{kind}/"):
            raise ContractViolation(f"{where}: {kind} content needs a {kind}/* mimeType")
    elif kind == "resource_link":
        if not isinstance(block.get("uri"), str) or not isinstance(block.get("name"), str):
            raise ContractViolation(f"{where}: a resource_link needs uri and name")
        if not isinstance(block.get("mimeType", ""), str):
            raise ContractViolation(f"{where}: mimeType must be a string")
    elif kind == "resource":
        resource = block.get("resource")
        if not isinstance(resource, dict) or not isinstance(resource.get("uri"), str):
            raise ContractViolation(f"{where}: an embedded resource needs a uri")
        if ("text" in resource) == ("blob" in resource):
            raise ContractViolation(f"{where}: an embedded resource carries text or blob")
        if "text" in resource and not isinstance(resource["text"], str):
            raise ContractViolation(f"{where}.resource.text must be a string")
        if "blob" in resource:
            _check_base64(resource["blob"], f"{where}.resource.blob")
        if not isinstance(resource.get("mimeType", ""), str):
            raise ContractViolation(f"{where}.resource.mimeType must be a string")
    else:
        raise ContractViolation(f"{where}: unknown content block type {kind!r}")


def validate_tool_result(tool: dict[str, Any], result: Any) -> None:
    """Check a tools/call result against the tool's contract before anyone uses it.

    The result is complete and has at least one content block, each valid. When the tool
    publishes an outputSchema, structuredContent must be present and conform to it.
    structuredContent may be any JSON value: an object, an array, a string, a number, a
    boolean or null. The contract also binds results with isError true: the flag classifies
    the outcome, it does not waive the published schema. A structured result also carries a
    text block (its serialized JSON, for older clients); that text is not what is validated.
    """
    if not isinstance(result, dict) or result.get("resultType") != "complete":
        raise ContractViolation("a tool result must be complete")
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise ContractViolation("a tool result needs at least one content block")
    for index, block in enumerate(content):
        validate_content_block(block, f"$.content[{index}]")
    schema = tool.get("outputSchema")
    if schema is None:
        return
    if "structuredContent" not in result:
        raise ContractViolation("outputSchema requires structuredContent")
    structured = result["structuredContent"]
    validate_json_schema(structured, schema, "$.structuredContent")
    if not any(block["type"] == "text" for block in content):
        raise ContractViolation("a structured result needs a text block for older clients")
