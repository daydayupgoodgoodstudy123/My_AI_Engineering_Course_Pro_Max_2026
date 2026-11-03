"""Reading one Streamable HTTP POST: header lookup, the body, and the mirrored routing headers."""
from __future__ import annotations

import base64
from collections.abc import Callable, Iterable
from typing import Any, Protocol

from .protocol import HEADER_MISMATCH, VERSION_KEY, RpcFault

MAX_BODY_BYTES = 1_048_576
READ_SIZE = 65_536
NAMED_METHODS = ("tools/call", "prompts/get", "resources/read")
SENTINEL_PREFIX = "=?base64?"
SENTINEL_SUFFIX = "?="


class Readable(Protocol):
    def read(self, n: int, /) -> bytes: ...


class FramingError(ValueError):
    """The body cannot be delimited safely. The endpoint answers 400 with -32700."""


class DuplicateHeader(ValueError):
    """A header that may appear once arrived more than once."""


class HeaderMismatch(RpcFault):
    """A mirrored header is missing, repeated, malformed or different from the body: -32020."""

    def __init__(self, message: str) -> None:
        super().__init__(HEADER_MISMATCH, message)


class Headers:
    """Request headers in arrival order.

    Header names are case-insensitive, as HTTP defines them: an HTTP/2 hop delivers every name
    in lowercase, and get("Mcp-Method") still finds "mcp-method". Values are kept exactly as
    received.
    """

    def __init__(self, pairs: Iterable[tuple[str, str]]) -> None:
        self._pairs = list(pairs)

    def get_all(self, name: str) -> list[str]:
        """Every value sent under this name, in arrival order."""
        wanted = name.lower()
        return [value for key, value in self._pairs if key.lower() == wanted]

    def get(self, name: str) -> str | None:
        """The value of a header that may appear once: None if absent, DuplicateHeader if repeated."""
        values = self.get_all(name)
        if len(values) > 1:
            raise DuplicateHeader(name)
        return values[0] if values else None


def read_body(headers: Headers, stream: Readable, limit: int = MAX_BODY_BYTES) -> bytes:
    """Read the request body: exactly Content-Length bytes.

    The framing is checked before any body byte is read. Content-Length must be sent once, as
    ASCII decimal digits, from 1 through limit, and a request that also carries
    Transfer-Encoding is refused, because two parsers could split it differently. Any of these
    raises FramingError.

    stream.read(n) may return fewer than n bytes, and b"" means the client closed the
    connection, which is a FramingError too. Bytes after the body stay in the stream.
    """
    if headers.get_all("Transfer-Encoding"):
        raise FramingError("Transfer-Encoding is not supported")
    lengths = headers.get_all("Content-Length")
    if not lengths:
        raise FramingError("Content-Length is required")
    if len(lengths) > 1:
        raise FramingError("Content-Length must be sent once")
    raw = lengths[0]
    if not (raw.isascii() and raw.isdigit()):
        raise FramingError("Content-Length must be ASCII decimal digits")
    length = int(raw)
    if not 1 <= length <= limit:
        raise FramingError(f"Content-Length must be from 1 through {limit}")
    body = bytearray()
    while len(body) < length:
        chunk = stream.read(min(READ_SIZE, length - len(body)))
        if not chunk:
            raise FramingError("the body ended before Content-Length bytes arrived")
        body += chunk
    return bytes(body)


def check_mirrored_headers(headers: Headers, message: dict[str, Any]) -> None:
    """Compare the mirrored routing headers with the body they describe, before anything runs.

    message has passed validate_structure. MCP-Protocol-Version must equal the protocol version
    in params._meta and Mcp-Method the JSON-RPC method. tools/call, prompts/get and
    resources/read also carry Mcp-Name, which mirrors params.name, or params.uri for
    resources/read. Values are compared exactly, after decoding the =?base64?...?= form. A
    missing, repeated, malformed or different header raises HeaderMismatch.
    """
    _expect(headers, "MCP-Protocol-Version", message["params"]["_meta"][VERSION_KEY])
    _expect(headers, "Mcp-Method", message["method"])
    if message["method"] in NAMED_METHODS:
        _expect(headers, "Mcp-Name", body_name(message), decode=decode_header_value)


def body_name(message: dict[str, Any]) -> str | None:
    """The body value that Mcp-Name mirrors: params.uri for resources/read, else params.name."""
    key = "uri" if message.get("method") == "resources/read" else "name"
    value = message.get("params", {}).get(key)
    return value if isinstance(value, str) else None


def decode_header_value(value: str) -> str:
    """Undo the exact =?base64?{Base64}?= sentinel, UTF-8 inside; any other value must be visible ASCII."""
    if value.startswith(SENTINEL_PREFIX) and value.endswith(SENTINEL_SUFFIX):
        encoded = value[len(SENTINEL_PREFIX) : -len(SENTINEL_SUFFIX)]
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except ValueError as exc:  # binascii.Error and UnicodeDecodeError are both ValueErrors
            raise HeaderMismatch("Malformed Base64 MCP header value") from exc
    if not all(0x20 <= ord(character) <= 0x7E for character in value):
        raise HeaderMismatch("Malformed MCP header value")
    return value


def _expect(
    headers: Headers,
    name: str,
    expected: str | None,
    decode: Callable[[str], str] | None = None,
) -> None:
    values = headers.get_all(name)
    if len(values) != 1:
        raise HeaderMismatch(f"{name} must be sent exactly once")
    value = values[0] if decode is None else decode(values[0])
    if expected is None or value != expected:
        raise HeaderMismatch(f"Header mismatch: {name}")
