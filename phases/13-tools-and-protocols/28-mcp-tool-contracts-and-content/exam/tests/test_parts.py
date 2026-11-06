import base64
import copy
import gc
import itertools
import json
import time

import pytest
from contractkit.annotations import Finding, audit_header_annotations
from contractkit.archive import MAGIC, PayloadLimits, pack_content, unpack_content
from contractkit.client import ContractClient
from contractkit.completion import CompletionBox
from contractkit.headers import (
    JS_SAFE_INTEGER_MAX,
    build_parameter_headers,
    decode_header_value,
    encode_header_value,
    http_tool_call,
)
from contractkit.wire import ContractViolation, complete, make_request, request_meta

FIRST = object()  # the first tools/list request carries no cursor
OMIT = object()  # the page leaves nextCursor out


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def structured(value, *, error: bool = False) -> dict:
    """A tool result whose structuredContent also travels as JSON text for older clients."""
    return complete(content=[text(json.dumps(value))], structuredContent=value, isError=error)


def raises(error: type, call, *args) -> bool:
    try:
        call(*args)
    except error:
        return True
    return False


def tool(name: str, properties: dict | None = None, required: tuple = (), output: dict | None = None) -> dict:
    descriptor = {
        "name": name,
        "description": f"Fixture tool {name}.",
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
    }
    if output is not None:
        descriptor["outputSchema"] = output
    return descriptor


class CatalogServer:
    """A scripted MCP server. tools/list pages are keyed by the exact cursor sent; tools/call runs a handler."""

    def __init__(self, pages: dict, handlers: dict) -> None:
        self.pages = dict(pages)
        self.handlers = dict(handlers)
        self.requests: list[dict] = []

    def __call__(self, request: dict) -> dict:
        self.requests.append(request)
        params = request["params"]
        if request["method"] == "tools/list":
            page = self.pages.get(params.get("cursor", FIRST))
            if page is None:
                return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32602, "message": "invalid cursor"}}
            tools, next_cursor = page
            fields = {"tools": tools} if next_cursor is OMIT else {"tools": tools, "nextCursor": next_cursor}
            return {"jsonrpc": "2.0", "id": request["id"], "result": complete(**fields)}
        result = self.handlers[params["name"]](params["arguments"])
        return {"jsonrpc": "2.0", "id": request["id"], "result": result}

    def sent(self, method: str) -> list[dict]:
        return [request["params"] for request in self.requests if request["method"] == method]


ROUTED = {
    "type": "object",
    "properties": {"region": {"type": "string"}, "accepted": {"type": "boolean"}},
    "required": ["region", "accepted"],
    "additionalProperties": False,
}
EVIDENCE = tool(
    "evidence_bundle",
    output={
        "type": "object",
        "properties": {"artifact": {"type": "string"}, "blockCount": {"type": "integer"}},
        "required": ["artifact", "blockCount"],
        "additionalProperties": False,
    },
)
BROKEN = {
    "name": "broken_route",
    "description": "Its inputSchema never says it is an object.",
    "inputSchema": {"properties": {"region": {"type": "string"}}},
}
ROUTE = tool(
    "route_report",
    {"region": {"type": "string"}, "report": {"type": "string", "minLength": 1}},
    ("region", "report"),
    ROUTED,
)
OWNER = tool("find_owner", {"path": {"type": "string"}}, ("path",), {"type": ["string", "null"]})
TAGS = tool("tag_catalog", output={"type": "array", "items": {"type": "string"}})
SUMMARY = tool("summarize", {"topic": {"type": "string"}}, ("topic",), {"type": "string"})
OPAQUE = "eyJwYWdlIjozfQ"  # the server's own business; the client never looks inside
PAGES = {
    FIRST: ([EVIDENCE, BROKEN], ""),
    "": ([ROUTE, OWNER], OPAQUE),
    OPAQUE: ([TAGS, SUMMARY], OMIT),
}


REPORT_LINK = {
    "type": "resource_link",
    "uri": "evidence://contract-report",
    "name": "contract-report",
    "mimeType": "application/json",
}


def evidence_bundle(arguments: dict) -> dict:
    summary = {"artifact": "contract-report", "blockCount": 5}
    return complete(
        content=[
            text(json.dumps(summary)),
            {"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"},
            {"type": "audio", "data": "UklGRg==", "mimeType": "audio/wav"},
            dict(REPORT_LINK),
            {
                "type": "resource",
                "resource": {
                    "uri": "evidence://contract-report/summary",
                    "mimeType": "text/plain",
                    "text": "All contract checks passed.",
                },
            },
        ],
        structuredContent=summary,
        isError=False,
    )


def route_report(arguments: dict) -> dict:
    region, report = arguments.get("region"), arguments.get("report")
    if report == "unavailable":
        failure = {"region": region, "accepted": False}
        return complete(content=[text("Report source is unavailable.")], structuredContent=failure, isError=True)
    if report == "archived":
        return complete(content=[text("Report is archived.")], isError=True)
    if report == "legacy":
        refused = text("Legacy reports are not routed.")
        return complete(content=[refused], structuredContent={"error": "legacy"}, isError=True)
    return structured({"region": region, "accepted": True})


def find_owner(arguments: dict) -> dict:
    if arguments["path"] == "/srv/shared":
        return structured(None)
    if arguments["path"] == "/srv/lost":
        return complete(content=[text("null")], isError=False)
    return structured("alice")


HANDLERS = {
    "evidence_bundle": evidence_bundle,
    "broken_route": lambda arguments: complete(content=[text("routed")], isError=False),
    "route_report": route_report,
    "find_owner": find_owner,
    "tag_catalog": lambda arguments: structured(["contracts", "mcp", "stateless"]),
    "summarize": lambda arguments: structured("Three tools share one contract."),
}


def big_catalog(count: int, per_page: int) -> tuple[list[str], CatalogServer]:
    """count report tools served per_page at a time."""
    names = [f"report_{index:04d}" for index in range(count)]
    properties = {
        "region": {"type": "string", "minLength": 2},
        "quarter": {"type": "integer"},
        "format": {"type": "string", "enum": ["pdf", "html"]},
    }
    tools = [tool(name, properties, ("region",), ROUTED) for name in names]
    cursors = [FIRST] + [f"page-{index}" for index in range(1, count // per_page)]
    pages = {}
    for index, cursor in enumerate(cursors):
        following = cursors[index + 1] if index + 1 < len(cursors) else OMIT
        pages[cursor] = (tools[index * per_page : (index + 1) * per_page], following)
    accept = lambda arguments: structured({"region": arguments["region"], "accepted": True})  # noqa: E731
    return names, CatalogServer(pages, {name: accept for name in names})


@pytest.mark.skip("Part 1")
def test_discover_and_call() -> None:
    """Discovery follows every cursor, results keep their published contract, and calls stay fast."""
    server = CatalogServer(PAGES, HANDLERS)
    client = ContractClient(server)
    tools = client.discover_tools()
    tags = client.call("tag_catalog", {})
    assert tags["structuredContent"] == ["contracts", "mcp", "stateless"], "an array is a valid structuredContent"
    assert [params.get("cursor", FIRST) for params in server.sent("tools/list")] == [FIRST, "", OPAQUE], (
        "each cursor goes back exactly as the server sent it"
    )
    assert sorted(tools) == ["evidence_bundle", "find_owner", "route_report", "summarize", "tag_catalog"], (
        "every valid descriptor on every page is admitted"
    )
    assert [rejected["tool"] for rejected in client.rejections] == ["broken_route"], (
        "a broken descriptor is rejected on its own"
    )
    ended = CatalogServer({FIRST: ([TAGS], ""), "": ([SUMMARY], None)}, HANDLERS)
    assert sorted(ContractClient(ended).discover_tools()) == ["summarize", "tag_catalog"] and len(
        ended.sent("tools/list")
    ) == 2, "nextCursor null ends the listing, the same as no nextCursor"
    looping = CatalogServer({FIRST: ([TAGS], "again"), "again": ([SUMMARY], "again")}, HANDLERS)
    assert raises(ContractViolation, ContractClient(looping).discover_tools) and len(looping.sent("tools/list")) == 2, (
        "a repeated cursor ends discovery before it is sent again"
    )
    numbered = CatalogServer({FIRST: ([TAGS], 0), 0: ([SUMMARY], OMIT)}, HANDLERS)
    assert raises(ContractViolation, ContractClient(numbered).discover_tools), "a cursor that is not a string is refused"
    pages_sent: list[dict] = []

    def endless(request: dict) -> dict:
        pages_sent.append(request)
        assert len(pages_sent) <= 20, "discovery keeps paging past max_pages"
        return {"jsonrpc": "2.0", "id": request["id"], "result": complete(tools=[], nextCursor=f"page-{len(pages_sent)}")}

    assert raises(ContractViolation, ContractClient(endless, max_pages=5).discover_tools) and len(pages_sent) == 5, (
        "discovery stops after max_pages pages"
    )

    bundle = client.call("evidence_bundle", {})
    assert [block["type"] for block in bundle["content"]] == ["text", "image", "audio", "resource_link", "resource"]
    assert client.call("summarize", {"topic": "contracts"})["structuredContent"] == "Three tools share one contract.", (
        "a string is a valid structuredContent"
    )
    assert client.call("find_owner", {"path": "/srv/shared"})["structuredContent"] is None, (
        "null is a valid structuredContent"
    )
    assert raises(ContractViolation, client.call, "find_owner", {"path": "/srv/lost"}), (
        "a result without structuredContent is not a null result"
    )
    server.handlers["tag_catalog"] = lambda arguments: structured({"tags": []})
    assert raises(ContractViolation, client.call, "tag_catalog", {}), "an object does not pass an array outputSchema"
    server.handlers["summarize"] = lambda arguments: complete(content=[], structuredContent="ok", isError=False)
    assert raises(ContractViolation, client.call, "summarize", {"topic": "contracts"}), (
        "a result carries at least one content block"
    )
    torn = {"type": "image", "data": "not base64!", "mimeType": "image/png"}
    server.handlers["summarize"] = lambda arguments: complete(content=[text('"ok"'), torn], structuredContent="ok", isError=False)
    assert raises(ContractViolation, client.call, "summarize", {"topic": "contracts"}), "every content block is checked"

    failed = client.call("route_report", {"region": "eu-west", "report": "unavailable"})
    assert failed["isError"] is True and failed["structuredContent"] == {"region": "eu-west", "accepted": False}, (
        "a tool error inside the published schema is an ordinary result"
    )
    assert raises(ContractViolation, client.call, "route_report", {"region": "eu-west", "report": "archived"}), (
        "isError does not waive outputSchema: structuredContent is still required"
    )
    assert raises(ContractViolation, client.call, "route_report", {"region": "eu-west", "report": "legacy"}), (
        "isError does not waive outputSchema: structuredContent must still conform"
    )
    picture = {"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"}
    server.handlers["summarize"] = lambda arguments: complete(content=[picture], structuredContent="ok", isError=False)
    assert raises(ContractViolation, client.call, "summarize", {"topic": "contracts"}), (
        "a structured result also carries a text block for older clients"
    )

    names, busy_server = big_catalog(2000, 100)
    busy = ContractClient(busy_server)
    busy.discover_tools()
    gc.collect()
    start = time.perf_counter()
    for name in names[::12]:
        busy.call(name, {"region": "eu-west", "quarter": 3})
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, "calls should not slow down as the catalog grows"

    calls = len(server.sent("tools/call"))
    assert raises(ContractViolation, client.call, "broken_route", {"region": "eu-west"}), (
        "a rejected descriptor stays uncallable"
    )
    for arguments in (
        {"region": "eu-west"},
        {"region": "eu-west", "report": ""},
        {"region": 7, "report": "q3"},
        {"region": "eu-west", "report": "q3", "format": "pdf"},
    ):
        assert raises(ContractViolation, client.call, "route_report", arguments), (
            f"arguments are checked against inputSchema before the call: {arguments}"
        )
    assert len(server.sent("tools/call")) == calls, "nothing is sent for a call the client refuses"
    server.handlers["route_report"] = lambda arguments: structured({"region": arguments["region"]})
    assert raises(ContractViolation, client.call, "route_report", {"region": "eu-west", "report": "q3"}), (
        "every result is checked before it is returned"
    )
    server.pages = {FIRST: ([EVIDENCE, ROUTE, SUMMARY], OMIT)}
    assert sorted(client.discover_tools()) == ["evidence_bundle", "route_report", "summarize"], (
        "discovering again replaces the admitted catalog"
    )
    assert client.rejections == [], "rejections describe the latest discovery"
    calls = len(server.sent("tools/call"))
    assert raises(ContractViolation, client.call, "find_owner", {"path": "/srv/a"}) and len(
        server.sent("tools/call")
    ) == calls, "a tool that left the catalog can no longer be called"


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


PIXELS = bytes(range(256)) * 2 + b"\xfb\xff"  # 514 bytes; its base64 has + and /, == padding, and is longer than 76
CHIRP = b"RIFF" + bytes(range(97))  # 101 bytes, one = of padding
DUMP = bytes((index * 7) % 251 for index in range(70_000))  # more than 65,535 bytes
CONTENT = [
    text("Résumé ✓ 📎\r\nline two\u2028three\x00end"),
    {"type": "image", "data": b64(PIXELS), "mimeType": "image/png"},
    {"type": "audio", "data": b64(CHIRP), "mimeType": "audio/wav"},
    dict(REPORT_LINK),
    {"type": "resource_link", "uri": "evidence://raw/λ", "name": "raw λ"},
    {
        "type": "resource",
        "resource": {"uri": "evidence://contract-report/summary", "mimeType": "text/plain", "text": "All checks passed."},
    },
    text(""),
    {"type": "resource", "resource": {"uri": "evidence://empty", "mimeType": "text/plain", "text": ""}},
    {"type": "resource", "resource": {"uri": "evidence://dump", "mimeType": "application/octet-stream", "blob": b64(DUMP)}},
]


def records(data: bytes) -> list[tuple[int, dict, bytes]] | None:
    """The test's own reading of the container: (tag, meta, body) per record, or None if it does not parse."""
    found, pos = [], len(MAGIC)
    try:
        while pos < len(data):
            tag, size = data[pos], int.from_bytes(data[pos + 1 : pos + 5], "big")
            meta = json.loads(data[pos + 5 : pos + 5 + size].decode("utf-8"))
            pos += 5 + size
            size = int.from_bytes(data[pos : pos + 4], "big")
            found.append((tag, meta, data[pos + 4 : pos + 4 + size]))
            pos += 4 + size
    except ValueError:
        return None
    return found


@pytest.mark.skip("Part 2")
def test_content_container_roundtrip(tmp_path) -> None:
    """Content blocks come back from the binary container exactly; a damaged container is refused."""
    assert pack_content([]) == MAGIC and unpack_content(MAGIC) == [], "a container starts with MAGIC, even an empty one"
    assert pack_content([text("λ")]) == MAGIC + b"\x01" + b"\x00\x00\x00\x02{}" + b"\x00\x00\x00\x02\xce\xbb", (
        "a record is its tag, then meta and body, each after its length in bytes"
    )

    before = copy.deepcopy(CONTENT)
    packed = pack_content(CONTENT)
    assert CONTENT == before, "pack_content leaves the blocks it is given unchanged"
    assert records(packed) == [
        (1, {}, CONTENT[0]["text"].encode("utf-8")),
        (2, {"mimeType": "image/png"}, PIXELS),
        (3, {"mimeType": "audio/wav"}, CHIRP),
        (4, {"uri": "evidence://contract-report", "name": "contract-report", "mimeType": "application/json"}, b""),
        (4, {"uri": "evidence://raw/λ", "name": "raw λ"}, b""),
        (5, {"resource": {"uri": "evidence://contract-report/summary", "mimeType": "text/plain"}}, b"All checks passed."),
        (1, {}, b""),
        (5, {"resource": {"uri": "evidence://empty", "mimeType": "text/plain"}}, b""),
        (6, {"resource": {"uri": "evidence://dump", "mimeType": "application/octet-stream"}}, DUMP),
    ], "one record per block: meta holds its other fields, body its payload, with base64 stored as the decoded bytes"
    path = tmp_path / "call-17.mcb"
    path.write_bytes(packed)
    assert unpack_content(path.read_bytes()) == CONTENT, "content blocks round-trip exactly"

    for block in (
        {"type": "image", "data": "QR==", "mimeType": "image/png"},
        {"type": "audio", "data": "AAB=", "mimeType": "audio/wav"},
        {"type": "resource", "resource": {"uri": "evidence://x", "blob": "QR=="}},
        {"type": "audio", "data": "-_8=", "mimeType": "audio/wav"},
        {"type": "resource", "resource": {"uri": "evidence://x", "blob": "AAE"}},
        {"type": "video", "data": "AAEC", "mimeType": "video/mp4"},
    ):
        assert raises(ContractViolation, pack_content, [block]), (
            f"a block the archive could not give back exactly is refused: {block}"
        )

    damaged = {
        "wrong magic": b"MCB2" + packed[4:],
        "cut short": packed[:-1],
        "a stray byte after the last record": packed + b"\x00",
        "unknown tag": packed[:4] + b"\x09" + packed[5:],
        "text that is not UTF-8": MAGIC + b"\x01\x00\x00\x00\x02{}\x00\x00\x00\x01\xff",
        "meta that is not an object": MAGIC + b"\x01\x00\x00\x00\x02[]\x00\x00\x00\x00",
        "meta that is not UTF-8": MAGIC + b"\x01\x00\x00\x00\x06" + "\ufeff{}".encode("utf-16-le") + b"\x00\x00\x00\x00",
        "an image without a mimeType": MAGIC + b"\x02\x00\x00\x00\x02{}\x00\x00\x00\x01\x00",
        "a length past the end": MAGIC + b"\x01\xff\xff\xff\xff{}",
    }
    for label, data in damaged.items():
        assert raises(ContractViolation, unpack_content, data), f"a damaged container raises ContractViolation: {label}"


    # Limits are local settings, not fixed MCP maxima; they apply to each decoded payload.
    image = {"type": "image", "data": "AAE=", "mimeType": "image/png"}
    audio = {"type": "audio", "data": "AAECAw==", "mimeType": "audio/wav"}
    embedded_text = {"type": "resource", "resource": {"uri": "evidence://local/text", "text": "λ"}}
    embedded_blob = {"type": "resource", "resource": {"uri": "evidence://local/blob", "blob": "AAE="}}
    link = {"type": "resource_link", "uri": "https://unreachable.invalid/" + "x" * 2000, "name": "not fetched"}
    limits = PayloadLimits(image=2, audio=4, resource=2)
    bounded = [image, audio, embedded_text, embedded_blob, link, text("prose " * 100)]
    encoded = pack_content(bounded, limits)
    assert unpack_content(encoded, limits) == bounded, "local limits count decoded payloads per kind, not base64 or metadata"
    assert pack_content(bounded, limits) == pack_content(bounded), "limits do not change the archive's bytes"
    assert unpack_content(pack_content([image, image]), PayloadLimits(image=2)) == [image, image], (
        "a local payload limit applies per block, not to the sum of a kind"
    )
    zero = PayloadLimits(image=0, audio=0, resource=0)
    empty = [
        {"type": "image", "data": "", "mimeType": "image/png"},
        {"type": "audio", "data": "", "mimeType": "audio/wav"},
        {"type": "resource", "resource": {"uri": "evidence://empty-text", "text": ""}},
        {"type": "resource", "resource": {"uri": "evidence://empty-blob", "blob": ""}},
        link, text("unbounded prose"),
    ]
    assert unpack_content(pack_content(empty, zero), zero) == empty, "zero admits empty embedded payloads and never fetches a resource_link"
    one_byte_image = {"type": "image", "data": "AA==", "mimeType": "image/png"}
    assert raises(ContractViolation, pack_content, [one_byte_image], zero), "packing refuses an oversized local image payload at zero"
    for kind, block, size in (("image", image, 2), ("audio", audio, 4), ("resource", embedded_text, 2), ("resource", embedded_blob, 2)):
        exact_limit = PayloadLimits(**{kind: size})
        over_limit = PayloadLimits(**{kind: size - 1})
        assert unpack_content(pack_content([block], exact_limit), exact_limit) == [block], (
            f"an exact local {kind} payload limit is inclusive"
        )
        assert raises(ContractViolation, pack_content, [block], over_limit), f"packing refuses an oversized local {kind} payload"
        assert raises(ContractViolation, unpack_content, pack_content([block]), over_limit), (
            f"reading independently enforces the local {kind} payload limit"
        )
    assert unpack_content(pack_content([audio]), PayloadLimits(image=0)) == [audio], "one kind's local limit does not constrain another"


TOOL = {
    "name": "route_report",
    "inputSchema": {
        "type": "object",
        "properties": {
            "region": {"type": "string", "x-mcp-header": "Region"},
            "shard": {"type": "integer", "x-mcp-header": "Shard"},
            "dry_run": {"type": "boolean", "x-mcp-header": "Dry-Run"},
            "report": {"type": "string"},
        },
        "required": ["region", "report"],
        "additionalProperties": False,
    },
}


def post(arguments: dict, headers: list[tuple[str, str]]) -> tuple[int, dict, list, list]:
    """One tools/call POST through the HTTP boundary: (status, body, audit, requests dispatched)."""
    audit: list[dict] = []
    dispatched: list[dict] = []

    def dispatch(request: dict) -> dict:
        dispatched.append(request)
        return {"jsonrpc": "2.0", "id": request["id"], "result": complete(content=[text("routed")], isError=False)}

    request = make_request(9, "tools/call", {"name": "route_report", "arguments": arguments})
    status, body = http_tool_call(TOOL, request, headers, dispatch, audit)
    return status, body, audit, dispatched


@pytest.mark.skip("Part 3")
def test_parameter_headers() -> None:
    """Mirrored arguments are encoded exactly, and the server refuses any header that disagrees with the body."""
    for value, header in (
        ("eu-west", "eu-west"),
        ("!a~", "!a~"),
        ("münchen", "=?base64?bcO8bmNoZW4=?="),
        ("", "=?base64??="),
        (" eu-west ", "=?base64?IGV1LXdlc3Qg?="),
        ("eu west", "=?base64?ZXUgd2VzdA==?="),
        ("eu\twest", "=?base64?ZXUJd2VzdA==?="),
        ("eu\r\nwest", "=?base64?ZXUNCndlc3Q=?="),
        ("\x7f", "=?base64?fw==?="),
        ("=?base64?SGVsbG8=?=", "=?base64?PT9iYXNlNjQ/U0dWc2JHOD0/PQ==?="),
        ("A\u030a", "=?base64?QcyK?="),
    ):
        assert encode_header_value(value) == header, f"the header form of {value!r}"
        assert decode_header_value(header) == value, f"{header!r} decodes back to {value!r}"

    audit: list[dict] = []
    arguments = {"report": "q3", "dry_run": False, "region": "eu-west", "shard": 7}
    assert build_parameter_headers(TOOL, arguments, audit) == [
        ("Mcp-Param-Region", "eu-west"),
        ("Mcp-Param-Shard", "7"),
        ("Mcp-Param-Dry-Run", "false"),
    ], "one header per mirrored argument, in property order, booleans in lowercase"
    assert build_parameter_headers(TOOL, {"region": "eu-west", "report": "q3", "dry_run": True}, audit) == [
        ("Mcp-Param-Region", "eu-west"),
        ("Mcp-Param-Dry-Run", "true"),
    ], "an argument that is absent gets no header"
    for shard in (JS_SAFE_INTEGER_MAX, -JS_SAFE_INTEGER_MAX):
        headers = build_parameter_headers(TOOL, {"region": "eu-west", "report": "q3", "shard": shard}, audit)
        assert headers[1] == ("Mcp-Param-Shard", str(shard)), "the JavaScript safe integer bounds are mirrored"
    for shard in (JS_SAFE_INTEGER_MAX + 1, -JS_SAFE_INTEGER_MAX - 1, True, 7.0, "7"):
        arguments = {"region": "eu-west", "report": "q3", "shard": shard}
        assert raises(ContractViolation, build_parameter_headers, TOOL, arguments, []), (
            f"an integer header carries a safe integer and nothing else: {shard!r}"
        )
    for arguments in (
        {"region": 7, "report": "q3"},
        {"region": "eu-west", "report": "q3", "dry_run": "false"},
        {"region": "eu-west", "report": "q3", "dry_run": 0},
    ):
        assert raises(ContractViolation, build_parameter_headers, TOOL, arguments, []), (
            f"a header carries a value of its declared type and nothing else: {arguments}"
        )
    built = build_parameter_headers(TOOL, {"region": "private-λ\n", "report": "q3", "shard": 7}, audit)
    assert audit[-1] == {
        "event": "parameter_headers_built",
        "headers": ["Mcp-Param-Region", "Mcp-Param-Shard"],
        "encoded": ["Mcp-Param-Region"],
    }, "the client audit lists the headers and which of them needed the sentinel"
    assert "private" not in json.dumps(audit) and built[0][1] not in json.dumps(audit), (
        "the client audit holds header names, never values"
    )

    for region in ("eu-west", "münchen", "", " eu-west ", "eu\r\nwest", "=?base64?SGVsbG8=?=", "private-λ\n"):
        arguments = {"region": region, "report": "q3", "shard": -JS_SAFE_INTEGER_MAX, "dry_run": True}
        headers = [(name.swapcase(), value) for name, value in build_parameter_headers(TOOL, arguments, [])]
        received = [("Accept", "*/*")] + headers[::-1] + [("Mcp-Param-Region-Backup", "x")]
        status, body, audit, dispatched = post(arguments, received)
        assert (status, len(dispatched)) == (200, 1), (
            f"headers that mirror the body pass, whatever the value and the case of their names: {region!r}"
        )
        assert audit == [
            {"event": "parameter_headers_checked", "headers": ["Mcp-Param-Region", "Mcp-Param-Shard", "Mcp-Param-Dry-Run"]}
        ], "the server audit lists the headers it checked, in bindings order"

    status, body, audit, dispatched = post({"region": "eu-west", "report": "q3"}, [("Mcp-Param-Region", "eu-west")])
    assert (status, audit) == (200, [{"event": "parameter_headers_checked", "headers": ["Mcp-Param-Region"]}]), (
        "the server audit lists the headers it checked"
    )

    body_region = {"region": "eu-west", "report": "q3"}
    for arguments, headers, header, reason in (
        (body_region, [], "Mcp-Param-Region", "missing"),
        (body_region, [("Mcp-Param-Region", "eu-west"), ("mcp-param-region", "eu-west")], "Mcp-Param-Region", "duplicated"),
        (body_region, [("Mcp-Param-Region", "eu-west"), ("Mcp-Param-Region", "eu-west")], "Mcp-Param-Region", "duplicated"),
        ({"report": "q3"}, [("Mcp-Param-Region", "eu-west")], "Mcp-Param-Region", "unexpected"),
        ({"region": "", "report": "q3"}, [("Mcp-Param-Region", "=?base64?=")], "Mcp-Param-Region", "malformed"),
        ({"region": "A", "report": "q3"}, [("Mcp-Param-Region", "=?base64?QR==?=")], "Mcp-Param-Region", "malformed"),
        (body_region, [("Mcp-Param-Region", "=?base64?ZXUtd2VzdA==")], "Mcp-Param-Region", "malformed"),
        (body_region, [("Mcp-Param-Region", "=?base64?ZXUtd2VzdA==x?")], "Mcp-Param-Region", "malformed"),
        (body_region, [("Mcp-Param-Region", "=?base64?ZXUtd2VzdA=?=")], "Mcp-Param-Region", "malformed"),
        (body_region, [("Mcp-Param-Region", "=?base64?ZXUtd2VzdA==?=\n")], "Mcp-Param-Region", "malformed"),
        ({"region": "ÿ", "report": "q3"}, [("Mcp-Param-Region", "=?base64?/w==?=")], "Mcp-Param-Region", "malformed"),
        ({"region": "eu west", "report": "q3"}, [("Mcp-Param-Region", "eu west")], "Mcp-Param-Region", "malformed"),
        ({"region": "münchen", "report": "q3"}, [("Mcp-Param-Region", "münchen")], "Mcp-Param-Region", "malformed"),
        ({"region": "", "report": "q3"}, [("Mcp-Param-Region", "")], "Mcp-Param-Region", "malformed"),
        (body_region, [("Mcp-Param-Region", "EU-WEST")], "Mcp-Param-Region", "mismatched"),
        ({"region": " eu-west ", "report": "q3"}, [("Mcp-Param-Region", "eu-west")], "Mcp-Param-Region", "mismatched"),
        ({"region": "\u00c5", "report": "q3"}, [("Mcp-Param-Region", "=?base64?QcyK?=")], "Mcp-Param-Region", "mismatched"),
        (
            {"region": "Hello", "report": "q3"},
            [("Mcp-Param-Region", "=?base64?PT9iYXNlNjQ/U0dWc2JHOD0/PQ==?=")],
            "Mcp-Param-Region",
            "mismatched",
        ),
        (
            {"region": "eu-west", "report": "q3", "shard": 7},
            [("Mcp-Param-Region", "eu-west"), ("Mcp-Param-Shard", "07")],
            "Mcp-Param-Shard",
            "mismatched",
        ),
        (
            {"region": "eu-west", "report": "q3", "shard": JS_SAFE_INTEGER_MAX + 1},
            [("Mcp-Param-Region", "eu-west"), ("Mcp-Param-Shard", "9007199254740992")],
            "Mcp-Param-Shard",
            "mismatched",
        ),
        (
            {"region": "eu-west", "report": "q3", "dry_run": False},
            [("Mcp-Param-Region", "eu-west"), ("Mcp-Param-Dry-Run", "False")],
            "Mcp-Param-Dry-Run",
            "mismatched",
        ),
        ({"region": 7, "report": "q3"}, [("Mcp-Param-Region", "7")], "Mcp-Param-Region", "mismatched"),
    ):
        status, body, audit, dispatched = post(arguments, headers)
        assert (status, body.get("error", {}).get("code"), dispatched) == (400, -32020, []), (
            f"{reason} headers are refused with HTTP 400 and -32020 before dispatch: {headers}"
        )
        assert body["error"]["data"] == {"header": header, "reason": reason}, f"the refusal names the reason: {headers}"
        assert audit == [{"event": "parameter_headers_rejected", "header": header, "reason": reason}], (
            "the server audit records the header name and the reason, never a value"
        )


    present = {"region": "", "shard": 0, "dry_run": False, "report": "private-evidence"}
    present_headers = [("Mcp-Param-Region", "=?base64??="), ("Mcp-Param-Shard", "0"), ("Mcp-Param-Dry-Run", "false")]
    presence_audit = []
    assert build_parameter_headers(TOOL, present, presence_audit) == present_headers, (
        "empty text, zero and false are present mirrored arguments"
    )
    assert presence_audit == [{"event": "parameter_headers_built", "headers": [name for name, _ in present_headers], "encoded": ["Mcp-Param-Region"]}], (
        "the presence audit names only emitted headers and their actual encoding"
    )
    for argument, name in (("region", "Mcp-Param-Region"), ("shard", "Mcp-Param-Shard"), ("dry_run", "Mcp-Param-Dry-Run")):
        headers = [(n, v) for n, v in present_headers if n != name]
        status, body, audit, dispatched = post(present, headers)
        assert (status, body["error"]["data"], dispatched) == (400, {"header": name, "reason": "missing"}, []), (
            f"a present falsy argument still requires its header: {argument}"
        )
    omitted_audit = []
    assert build_parameter_headers(TOOL, {"report": "private-evidence"}, omitted_audit) == [], "omitted bindings are not filled with defaults"
    assert omitted_audit == [{"event": "parameter_headers_built", "headers": [], "encoded": []}], "an empty header build still records an empty name-only audit"
    status, body, audit, dispatched = post(present, list(reversed(present_headers)) + [("Mcp-Param-Unbound", "=?base64?malformed")])
    assert (status, len(dispatched), audit) == (200, 1, [{"event": "parameter_headers_checked", "headers": [name for name, _ in present_headers]}]), (
        "unrecognized malformed headers do not affect recognized falsy mirrors or the audit"
    )
    for arguments, headers, name, reason in (
        (present, [("Mcp-Param-Dry-Run", "=?base64?malformed"), ("Mcp-Param-Shard", "wrong")], "Mcp-Param-Region", "missing"),
        ({"report": "private-evidence"}, [("Mcp-Param-Region", "first-secret"), ("mcp-param-region", "second-secret")], "Mcp-Param-Region", "duplicated"),
    ):
        status, body, audit, dispatched = post(arguments, headers)
        assert (status, body["error"]["data"], dispatched) == (400, {"header": name, "reason": reason}, []), (
            "multiple faults use bindings order and duplicate precedes unexpected within one binding"
        )
        assert audit == [{"event": "parameter_headers_rejected", "header": name, "reason": reason}], (
            "only the first canonical rejection is audited without either offending value"
        )


REF = {"type": "ref/prompt", "name": "deployment_review"}


class Clock:
    """Test time in milliseconds; it moves only when the test moves it."""

    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def answer(frame: str, values: list[str], **completion) -> str:
    """The server's completion/complete response to a request frame."""
    request_id = json.loads(frame)["id"]
    result = complete(completion={"values": values, **completion})
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def refusal(frame: str) -> str:
    """The server's JSON-RPC error response to a request frame."""
    request_id = json.loads(frame)["id"]
    error = {"code": -32602, "message": "unknown completion argument"}
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error})


@pytest.mark.skip("Part 4")
def test_completion_debounce() -> None:
    """Keystrokes turn into one completion/complete request per pause, and only the newest answer is shown."""
    clock = Clock()
    wire: list[str] = []
    box = CompletionBox(wire.append, clock, itertools.count(41), ref=REF, argument="environment", idle_ms=200)

    def keys(*strokes: tuple[int, str]) -> None:
        for at, value in strokes:
            clock.now = at
            box.type(value)
            box.poll()

    def wait(until: int) -> None:
        clock.now = until
        box.poll()

    keys((0, "s"), (90, "st"), (180, "sta"))
    wait(379)
    assert wire == [], "nothing is sent while the user is still typing"
    wait(380)
    assert [json.loads(frame) for frame in wire] == [
        {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "completion/complete",
            "params": {"ref": REF, "argument": {"name": "environment", "value": "sta"}, "_meta": request_meta()},
        }
    ], "after idle_ms one request goes out, for the value at that moment, with the next id and the full _meta"
    wait(1000)
    assert len(wire) == 1, "a pause sends one request"
    assert box.suggestions() == {"value": None, "values": [], "total": None, "hasMore": False}
    box.receive(answer(wire[0], ["staging"], total=1, hasMore=False))
    assert box.suggestions() == {"value": "sta", "values": ["staging"], "total": 1, "hasMore": False}

    keys((1000, "st"), (1100, "s"))
    wait(1300)
    keys((1400, "st"))
    wait(1600)
    box.receive(answer(wire[1], ["staging", "sandbox"], total=2, hasMore=False))
    assert box.suggestions()["value"] == "sta", "an answer to an older request is dropped, even when it comes first"
    box.receive(answer(wire[2], ["staging", "development"]))
    box.receive(answer(wire[1], ["staging", "sandbox"], total=2, hasMore=False))
    box.receive(json.dumps({"jsonrpc": "2.0", "id": 99, "result": complete(completion={"values": ["prod"]})}))
    assert box.suggestions() == {"value": "st", "values": ["staging", "development"], "total": None, "hasMore": False}, (
        "only the newest request's answer is shown, in the server's order, with no total unless the server gives one"
    )

    keys((2000, "s"))
    wait(2200)
    many = [f"shard-{index:03d}" for index in range(150)]
    box.receive(answer(wire[3], many, total=150, hasMore=False))
    assert box.suggestions() == {"value": "s", "values": many[:100], "total": 150, "hasMore": True}, (
        "at most 100 values are shown, and cutting them means there is more"
    )
    keys((2500, "p"))
    wait(2700)
    box.receive(answer(wire[4], many[:100], total=2400, hasMore=True))
    assert box.suggestions() == {"value": "p", "values": many[:100], "total": 2400, "hasMore": True}, (
        "the server's total and hasMore are shown as reported"
    )
    keys((3000, "pr"))
    wait(3200)
    box.receive(refusal(wire[4]))
    assert box.suggestions()["value"] == "p", "an error answer to an older request is dropped too"
    box.receive(refusal(wire[5]))
    assert box.suggestions() == {"value": "pr", "values": [], "total": None, "hasMore": False}, (
        "an error answer to the newest request clears the suggestions"
    )
    keys((3400, "pro"), (3450, "pr"))
    wait(3650)
    assert len(wire) == 7, "every pause sends a request, even for the value the newest request already asked"
    box.receive(answer(wire[6], many[:100], total=100, hasMore=False))
    assert box.suggestions() == {"value": "pr", "values": many[:100], "total": 100, "hasMore": False}, (
        "exactly 100 values is not a cut"
    )

    frames = [json.loads(frame) for frame in wire]
    assert [frame["id"] for frame in frames] == [41, 42, 43, 44, 45, 46, 47], "every request takes a fresh id"
    assert [frame["params"]["argument"]["value"] for frame in frames] == ["sta", "s", "st", "s", "p", "pr", "pr"]
    assert all(frame["params"]["_meta"] == request_meta() for frame in frames), "every request carries its own _meta"


def descriptor(properties: dict, **schema) -> dict:
    return {"name": "route_report", "inputSchema": {"type": "object", **schema, "properties": properties}}


@pytest.mark.skip("Part 5")
def test_annotation_audit() -> None:
    """Admission walks the whole schema tree and judges every x-mcp-header where it is written."""
    clean = descriptor(
        {
            "region": {"type": "string", "x-mcp-header": "Region"},
            "shard": {"type": "integer", "x-mcp-header": "Shard"},
            "dry_run": {"type": "boolean", "x-mcp-header": "Dry-Run"},
            "report": {"type": "string", "minLength": 1},
        },
        required=["region", "report"],
    )
    assert audit_header_annotations(clean) == [], "direct string, integer and boolean properties may be mirrored"

    nested = descriptor(
        {
            "filter": {"type": "object", "properties": {"zone": {"type": "string", "x-mcp-header": "Zone"}}},
            "regions": {"type": "array", "items": {"type": "string", "x-mcp-header": "Regions"}},
            "target": {"oneOf": [{"type": "integer"}, {"type": "string", "x-mcp-header": "Target"}]},
            "pair": {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer", "x-mcp-header": "Pair"}]},
            "labels": {"type": "object", "additionalProperties": {"type": "string", "x-mcp-header": "Label"}},
            "mode": {"type": "string", "not": {"type": "string", "x-mcp-header": "Mode"}},
        },
        **{"x-mcp-header": "Everything"},
    )
    assert audit_header_annotations(nested) == [
        Finding("/inputSchema", "placement"),
        Finding("/inputSchema/properties/filter/properties/zone", "placement"),
        Finding("/inputSchema/properties/labels/additionalProperties", "placement"),
        Finding("/inputSchema/properties/mode/not", "placement"),
        Finding("/inputSchema/properties/pair/prefixItems/1", "placement"),
        Finding("/inputSchema/properties/regions/items", "placement"),
        Finding("/inputSchema/properties/target/oneOf/1", "placement"),
    ], "an annotation anywhere but on a direct inputSchema property is refused, under any keyword"

    referenced = descriptor(
        {
            "home": {"$ref": "#/$defs/region"},
            "work": {"$ref": "#/$defs/region"},
            "tree": {"$ref": "#/$defs/tree"},
            "shard": {"type": "integer", "x-mcp-header": "Shard"},
        },
        **{
            "$defs": {
                "region": {"type": "string", "x-mcp-header": "Region"},
                "spare": {"type": "string", "x-mcp-header": "Spare"},
                "tree": {"type": "object", "properties": {"label": {"type": "string"}, "child": {"$ref": "#/$defs/tree"}}},
            },
            "definitions": {"legacy": {"type": "string", "x-mcp-header": "Legacy"}},
        },
    )
    assert audit_header_annotations(referenced) == [
        Finding("/inputSchema/$defs/region", "placement"),
        Finding("/inputSchema/$defs/spare", "placement"),
        Finding("/inputSchema/definitions/legacy", "placement"),
    ], "a definition is judged once, where it is written, whether or not a $ref uses it"

    mirrored_out = {
        "name": "route_report",
        "inputSchema": {"type": "object", "properties": {"region": {"type": "string", "x-mcp-header": "Region"}}},
        "outputSchema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "x-mcp-header": "Region"},
                "routes": {"type": "array", "items": {"type": "string", "x-mcp-header": "Route"}},
            },
        },
    }
    assert audit_header_annotations(mirrored_out) == [
        Finding("/outputSchema/properties/region", "output"),
        Finding("/outputSchema/properties/routes/items", "output"),
    ], "no annotation belongs in outputSchema, not even on one of its direct properties"

    typed = descriptor(
        {
            "weight": {"type": "number", "x-mcp-header": "Weight"},
            "label": {"type": ["string", "null"], "x-mcp-header": "Label"},
            "tags": {"type": "array", "items": {"type": "string"}, "x-mcp-header": "Tags"},
            "anything": {"x-mcp-header": "Anything"},
            "flag": {"type": "boolean", "x-mcp-header": "Flag"},
        }
    )
    assert audit_header_annotations(typed) == [
        Finding("/inputSchema/properties/anything", "type"),
        Finding("/inputSchema/properties/label", "type"),
        Finding("/inputSchema/properties/tags", "type"),
        Finding("/inputSchema/properties/weight", "type"),
    ], "only a single string, integer or boolean type may be mirrored; number is not one of them"

    named = descriptor(
        {
            "a": {"type": "string", "x-mcp-header": "Region\r\nX-Injected: 1"},
            "b": {"type": "string", "x-mcp-header": "Region\n"},
            "c": {"type": "string", "x-mcp-header": ""},
            "d": {"type": "string", "x-mcp-header": "Région"},
            "e": {"type": "string", "x-mcp-header": 7},
            "f": {"type": "string", "x-mcp-header": "Tenant Id"},
            "g": {"type": "string", "x-mcp-header": "Tenant_Id.v2"},
        }
    )
    assert audit_header_annotations(named) == [
        Finding(f"/inputSchema/properties/{name}", "name") for name in "abcdef"
    ], "a header name is one whole HTTP token"

    clashing = descriptor(
        {
            "region": {"type": "string", "x-mcp-header": "Region"},
            "zone": {"type": "string", "x-mcp-header": "REGION"},
            "tenant": {"type": "string", "x-mcp-header": "Tenant"},
        }
    )
    assert audit_header_annotations(clashing) == [Finding("/inputSchema/properties/zone", "duplicate")], (
        "header names are unique without regard to case"
    )
    sensitive = descriptor(
        {
            "api_key": {"type": "string", "x-mcp-header": "Key"},
            "auth": {"type": "string", "x-mcp-header": "Authorization"},
            "Password": {"type": "string", "x-mcp-header": "Pass"},
            "region": {"type": "string", "x-mcp-header": "Region"},
            "tokenizer": {"type": "string", "x-mcp-header": "Tokenizer"},
        }
    )
    assert audit_header_annotations(sensitive) == [
        Finding("/inputSchema/properties/Password", "sensitive"),
        Finding("/inputSchema/properties/api_key", "sensitive"),
        Finding("/inputSchema/properties/auth", "sensitive"),
    ], "a credential is never mirrored, whether the property or the header has the name; whole names are matched"

    mixed = descriptor(
        {
            "zone": {"type": "number", "x-mcp-header": "Zone"},
            "secret": {"type": "string", "x-mcp-header": "Code"},
            "area": {"type": "string", "x-mcp-header": "Area\n"},
        },
        **{"$defs": {"z": {"type": "string", "x-mcp-header": "Z"}}},
    )
    assert audit_header_annotations(mixed) == [
        Finding("/inputSchema/$defs/z", "placement"),
        Finding("/inputSchema/properties/area", "name"),
        Finding("/inputSchema/properties/secret", "sensitive"),
        Finding("/inputSchema/properties/zone", "type"),
    ], "findings are sorted by path"

    ranked = descriptor(
        {
            "region": {"type": "string", "x-mcp-header": "Region"},
            "password": {"type": "string", "x-mcp-header": "REGION"},
            "secret": {"type": "number", "x-mcp-header": "Secret"},
            "token": {"type": "number", "x-mcp-header": "Token Id"},
        },
        **{"$defs": {"api_key": {"type": "number", "x-mcp-header": "Api Key"}}},
    )
    assert audit_header_annotations(ranked) == [
        Finding("/inputSchema/$defs/api_key", "placement"),
        Finding("/inputSchema/properties/password", "duplicate"),
        Finding("/inputSchema/properties/secret", "type"),
        Finding("/inputSchema/properties/token", "name"),
    ], "an annotation with several problems gets only the first finding in the documented order"

    escaped = descriptor(
        {
            "geo/zone": {"type": "object", "properties": {"code": {"type": "string", "x-mcp-header": "Geo"}}},
            "a~b": {"type": "array", "items": {"type": "string", "x-mcp-header": "Ab"}},
            "c/d": {"type": "string", "x-mcp-header": "Cd"},
        }
    )
    assert audit_header_annotations(escaped) == [
        Finding("/inputSchema/properties/a~0b/items", "placement"),
        Finding("/inputSchema/properties/geo~1zone/properties/code", "placement"),
    ], "paths are JSON Pointers: ~ is written ~0 and / is written ~1"
