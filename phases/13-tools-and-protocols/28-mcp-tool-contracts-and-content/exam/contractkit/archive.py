"""A binary container that archives the content array of a tool result."""
from __future__ import annotations

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


def pack_content(content: list[dict[str, Any]]) -> bytes:
    """Serialize a content array into the archive's binary container.

    Layout: MAGIC, then one record per block, in order:

        tag    1 byte (TEXT, IMAGE, AUDIO, RESOURCE_LINK, RESOURCE_TEXT or RESOURCE_BLOB)
        meta   4-byte big-endian length, then a UTF-8 JSON object: the block without "type"
               and without the field that goes in body
        body   4-byte big-endian length, then the payload

    Lengths count bytes. The payload of each kind of block:

        text           the UTF-8 bytes of "text"
        image, audio   the decoded bytes of "data"
        resource_link  nothing; the link stays in meta as given and is never followed
        resource       the UTF-8 bytes of resource["text"] (RESOURCE_TEXT), or the decoded
                       bytes of resource["blob"] (RESOURCE_BLOB)

    Every block must pass validate_content_block. Base64 must be canonical standard base64,
    exactly what base64.b64encode writes: anything else could not be given back unchanged, so
    it raises ContractViolation. The blocks passed in are left unchanged.
    """
    raise NotImplementedError


def unpack_content(data: bytes) -> list[dict[str, Any]]:
    """Read a container written by pack_content back into the blocks that were packed.

    Base64 comes back as standard base64 with padding and without line breaks. Wrong magic,
    an unknown tag, a length that runs past the end, metadata that is not a UTF-8 JSON object,
    text that is not UTF-8, a block that fails validate_content_block, or bytes left after the
    last record raise ContractViolation.
    """
    raise NotImplementedError
