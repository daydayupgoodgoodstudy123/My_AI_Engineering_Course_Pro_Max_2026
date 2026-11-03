"""Evidence helpers: what the Registry says about a listed version, and a stable fingerprint of a tool set.

Each fact comes from the authority that owns it. The Registry owns a version's status, in the
response metadata beside the record; the namespace verifier owns the publisher's namespace; the
live endpoint owns its tool descriptors. Nothing here lets a record vouch for itself.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

PROTOCOL_VERSION = "2026-07-28"
REGISTRY_SOURCE = "https://registry.modelcontextprotocol.io"
OFFICIAL_META_KEY = "io.modelcontextprotocol.registry/official"
PUBLISHER_META_KEY = "io.modelcontextprotocol.registry/publisher-provided"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"


def canonical_json(value: Any) -> str:
    """The one JSON text of a value: keys sorted at every level, no whitespace, non-ASCII escaped."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    """Lowercase hex SHA-256 of the UTF-8 bytes of canonical_json(value)."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def is_sha256_digest(value: Any) -> bool:
    """True for exactly 64 hex digits, in either case."""
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def namespace_for_domain(domain: str) -> str:
    """The namespace a verified domain establishes, labels reversed: Docs.Example.COM. -> com.example.docs."""
    labels = [label.lower() for label in domain.strip().strip(".").split(".") if label]
    if len(labels) < 2:
        raise ValueError("a verified namespace domain needs at least two labels")
    return ".".join(reversed(labels))


def namespace_matches(server_name: str, verified_namespace: str) -> bool:
    """True when server_name is <verified_namespace>/<non-empty slug>, the namespace compared exactly.

    A subdomain is a namespace of its own: com.example.docs/search is not inside com.example.
    """
    prefix, separator, slug = server_name.partition("/")
    return separator == "/" and bool(slug) and prefix == verified_namespace


def registry_status(api_meta: Any) -> str:
    """The Registry-managed status of a listed version: "active", "deprecated" or "deleted".

    It lives in the response-level _meta object beside the record, under OFFICIAL_META_KEY:
    api_meta["io.modelcontextprotocol.registry/official"]["status"]. Nothing else counts, not a
    plain api_meta["status"] and not the record's own _meta, which is where publishers write.
    Without an official status the result is "", and "" is never eligible.
    """
    return str(api_meta.get("status", "active"))


def normalized_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tool descriptors in a stable order, ready to hash.

    Only the order of the list is normalized, because it has no meaning: tools are sorted by
    name, then by canonical JSON. Every descriptor stays in the list, two with one name included,
    and keeps every field it was sent with, so a new tool, a changed schema or description, or
    new annotations all change the digest.
    """
    by_name = {str(tool.get("name", "")): tool for tool in tools}
    return [by_name[name] for name in sorted(by_name)]


def toolset_digest(tools: list[dict[str, Any]]) -> str:
    """digest() of normalized_tools(tools): the toolsetDigest a pin keeps."""
    return digest(normalized_tools(tools))


def reported_server_info(live: Any) -> dict[str, Any] | None:
    """A copy of live["_meta"]["io.modelcontextprotocol/serverInfo"], or None.

    The server reports this about itself. It is diagnostic evidence for display and logs, never
    identity: it decides no namespace, ownership or admission. A plain live["serverInfo"]
    outside _meta is not the contract field and is not promoted.
    """
    if not isinstance(live, dict):
        return None
    metadata = live.get("_meta")
    value = metadata.get(SERVER_INFO_KEY) if isinstance(metadata, dict) else None
    return deepcopy(value) if isinstance(value, dict) else None


def normalize_https_remote_url(value: Any) -> str | None:
    """A remote URL in one comparable form, or None when it is not a plain HTTPS URL.

    The host is lowercased (and IDNA-encoded), the default port 443 dropped and an empty path
    written as "/". Credentials in the URL, a fragment, whitespace or control characters (raw
    or percent-encoded) make it unusable.
    """
    if not isinstance(value, str) or not value:
        return None
    decoded = unquote(value)
    if any(
        character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
        for character in value + decoded
    ):
        return None
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not isinstance(hostname, str)
        or not hostname
        or username is not None
        or password is not None
        or parsed.fragment
    ):
        return None
    host = hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    else:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            return None
    netloc = host if port is None or port == 443 else f"{host}:{port}"
    return urlunparse(("https", netloc, parsed.path or "/", parsed.params, parsed.query, ""))


@dataclass(frozen=True)
class Listing:
    """One server version as the Registry lists it, before anything is fetched."""

    name: str
    version: str
    namespace: str  # the part of the name before the first "/", as the record writes it
    status: str  # the Registry-managed status, "" when the Registry gives none
    in_namespace: bool  # the name sits inside the namespace the publisher's authentication verified
    record_digest: str  # digest() of the whole server.json record

    @property
    def eligible(self) -> bool:
        """Active in the Registry and inside the verified namespace."""
        return self.status == "active" and self.in_namespace


def listed_version(item: dict[str, Any], verified_namespace: str) -> Listing:
    """Read one Registry listing item: {"server": <server.json record>, "_meta": <response metadata>}.

    The response metadata sits beside the record, not inside it. verified_namespace is the exact
    namespace string the namespace verifier established for the publisher (from a verified domain
    or from GitHub authentication); the record's own name never vouches for itself.
    """
    record = item["server"]
    name = record["name"]
    namespace = name.partition("/")[0]
    return Listing(
        name=name,
        version=record["version"],
        namespace=namespace,
        status=registry_status(item.get("_meta", {})),
        in_namespace=namespace_matches(name, namespace),
        record_digest=digest(record),
    )
