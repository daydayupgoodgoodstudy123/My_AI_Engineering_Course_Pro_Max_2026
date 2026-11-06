"""A binary container that archives the content array of a tool result."""
from __future__ import annotations

import base64
from collections.abc import Iterator
from dataclasses import dataclass
import json
import struct
from typing import Any

from .contract import validate_content_block
from .wire import ContractViolation

MAGIC = b"MCB1"
# Record tags.
TEXT = 1
IMAGE = 2
AUDIO = 3
RESOURCE_LINK = 4
RESOURCE_TEXT = 5
RESOURCE_BLOB = 6

_LENGTH = struct.Struct(">I")


@dataclass(frozen=True)
class PayloadLimits:
    """Local per-block payload limits in bytes; None leaves that content kind unlimited.

    These are exercise/deployment settings, not MCP protocol maxima. image and audio count
    decoded media bytes; resource counts its embedded text's UTF-8 or decoded blob bytes.
    Plain text and resource_link have no embedded-media limit. A link is never fetched.
    """

    image: int | None = None
    audio: int | None = None
    resource: int | None = None

    def __post_init__(self) -> None:
        for value in (self.image, self.audio, self.resource):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("a payload limit is a non-negative byte count or None")


def _pack_record(tag: int, meta: dict[str, Any], body: bytes) -> bytes:
    """Provided physical codec: one tag and two byte-counted fields."""
    head = json.dumps(meta).encode("utf-8")
    return b"".join([bytes([tag]), _LENGTH.pack(len(head)), head, _LENGTH.pack(len(body)), body])


def _read_records(data: bytes) -> Iterator[tuple[int, dict[str, Any], bytes]]:
    """Provided physical codec: strict MCB1 framing and UTF-8 object metadata."""
    if data[: len(MAGIC)] != MAGIC:
        raise ContractViolation("not a content container")
    pos = len(MAGIC)
    while pos < len(data):
        tag = data[pos]
        head, pos = _field(data, pos + 1)
        body, pos = _field(data, pos)
        try:
            meta = json.loads(head.decode("utf-8"))
        except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
            raise ContractViolation("record metadata is not UTF-8 JSON") from exc
        if not isinstance(meta, dict):
            raise ContractViolation("record metadata must be a JSON object")
        yield tag, meta, body


def _field(data: bytes, pos: int) -> tuple[bytes, int]:
    start = pos + _LENGTH.size
    if start > len(data):
        raise ContractViolation("container is truncated")
    (length,) = _LENGTH.unpack_from(data, pos)
    end = start + length
    if end > len(data):
        raise ContractViolation("container is truncated")
    return data[start:end], end


def _text(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractViolation("text is not UTF-8") from exc


def pack_content(content: list[dict[str, Any]], limits: PayloadLimits | None = None) -> bytes:
    """Serialize a content array into the archive's binary container.

    Layout: MAGIC, then one record per block, in order:

        tag    1 byte (TEXT, IMAGE, AUDIO, RESOURCE_LINK, RESOURCE_TEXT or RESOURCE_BLOB)
        meta   4-byte big-endian length, then a UTF-8 JSON object: the block without "type"
               and without the field that goes in body
        body   4-byte big-endian length, then the payload

    Use the supplied _pack_record for physical framing; it writes byte lengths correctly.
    The payload of each kind of block:

        text           the UTF-8 bytes of "text"
        image, audio   the decoded bytes of "data"
        resource_link  nothing; the link stays in meta as given and is never followed
        resource       the UTF-8 bytes of resource["text"] (RESOURCE_TEXT), or the decoded
                       bytes of resource["blob"] (RESOURCE_BLOB)

    Every block must pass validate_content_block. Base64 must be canonical standard base64,
    exactly what base64.b64encode writes: anything else could not be given back unchanged, so
    it raises ContractViolation. The blocks passed in are left unchanged.

    limits applies independently to each image, audio or embedded resource, after decoding
    its payload. Exactly the configured byte limit is allowed. Text blocks and links are
    unaffected; links stay references, without a fetch. None preserves unlimited archiving.
    """
    parts = [MAGIC]
    for index, block in enumerate(content):
        validate_content_block(block, f"$.content[{index}]")
        meta = {key: value for key, value in block.items() if key != "type"}
        kind = block["type"]
        if kind == "text":
            tag, body = TEXT, meta.pop("text").encode("utf-8")
        elif kind in ("image", "audio"):
            tag, body = (IMAGE if kind == "image" else AUDIO), _decoded(meta.pop("data"))
        elif kind == "resource_link":
            tag, body = RESOURCE_LINK, b""
        else:
            resource = dict(meta["resource"])
            if "text" in resource:
                tag, body = RESOURCE_TEXT, resource.pop("text").encode("utf-8")
            else:
                tag, body = RESOURCE_BLOB, _decoded(resource.pop("blob"))
            meta["resource"] = resource
        _check_limit(kind, body, limits)
        parts.append(_pack_record(tag, meta, body))
    return b"".join(parts)


def unpack_content(data: bytes, limits: PayloadLimits | None = None) -> list[dict[str, Any]]:
    """Read a container written by pack_content back into the blocks that were packed.

    Base64 comes back as standard base64 with padding and without line breaks. Wrong magic,
    an unknown tag, a length that runs past the end, metadata that is not a UTF-8 JSON object,
    text that is not UTF-8, a block that fails validate_content_block, or bytes left after the
    last record raise ContractViolation. Use the supplied _read_records to read physical
    records. Apply the same local per-block limits as pack_content before returning a block,
    including when this container was written by a caller with no limits.
    """
    blocks: list[dict[str, Any]] = []
    for tag, meta, body in _read_records(data):
        block = _block(tag, meta, body)
        validate_content_block(block, f"$.content[{len(blocks)}]")
        _check_limit(block["type"], body, limits)
        blocks.append(block)
    return blocks


def _decoded(value: str) -> bytes:
    raw = base64.b64decode(value, validate=True)
    if base64.b64encode(raw).decode("ascii") != value:
        raise ContractViolation("base64 is not canonical; the archive could not give it back unchanged")
    return raw


def _check_limit(kind: str, body: bytes, limits: PayloadLimits | None) -> None:
    if limits is None or kind not in ("image", "audio", "resource"):
        return
    maximum = getattr(limits, kind)
    if maximum is not None and len(body) > maximum:
        raise ContractViolation(f"{kind} payload exceeds its local byte limit")



def _block(tag: int, meta: dict[str, Any], body: bytes) -> dict[str, Any]:
    if tag == TEXT:
        return {**meta, "type": "text", "text": _text(body)}
    if tag in (IMAGE, AUDIO):
        kind = "image" if tag == IMAGE else "audio"
        return {**meta, "type": kind, "data": base64.b64encode(body).decode("ascii")}
    if tag == RESOURCE_LINK:
        if body:
            raise ContractViolation("a resource_link record has no body")
        return {**meta, "type": "resource_link"}
    if tag in (RESOURCE_TEXT, RESOURCE_BLOB):
        resource = meta.get("resource")
        if not isinstance(resource, dict):
            raise ContractViolation("an embedded resource record needs its resource")
        if tag == RESOURCE_TEXT:
            resource = {**resource, "text": _text(body)}
        else:
            resource = {**resource, "blob": base64.b64encode(body).decode("ascii")}
        return {**meta, "type": "resource", "resource": resource}
    raise ContractViolation(f"unknown record tag {tag}")
