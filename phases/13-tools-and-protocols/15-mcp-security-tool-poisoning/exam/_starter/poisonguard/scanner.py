"""Static checks on MCP tool descriptors: injection tripwires, whole-descriptor pins, the catalog scan.

Descriptors are untrusted data. A scanner hit is review evidence, not a verdict, and an equal digest
proves only that a descriptor has not changed since it was approved.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any

INJECTION_PATTERNS = [
    (r"<\s*(system|assistant|developer)\b", "role-tag"),
    (r"ignore\s+(all\s+|previous\s+)?(instructions|rules|prompts)", "instruction-override"),
    (r"do\s+not\s+(tell|show|inform)\s+the\s+user", "concealment"),
    (r"(?:read|send|upload).{0,40}(?:\.env|\.ssh|id_rsa|token|secret)", "secret-access"),
    (r"https?://(?:bit\.ly|tinyurl\.com|is\.gd)/", "obscured-destination"),
]

# server name -> the tool descriptors from that server's tools/list, as the server sent them:
# only "name" is always there. Server and tool names never contain ".", so server.tool is unambiguous.
Catalog = dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class Finding:
    kind: str  # "metadata_poisoning", "unapproved", "rug_pull" or "shadowing"
    key: str  # the qualified name server.tool; the bare tool name for "shadowing"
    detail: str


def canonical_json(value: Any) -> str:
    """The one JSON text of a value: keys sorted at every level, no whitespace, non-ASCII as \\u escapes."""
    return json.dumps(value, separators=(",", ":"))


def descriptor_digest(tool: dict[str, Any]) -> str:
    """Lowercase hex SHA-256 of the UTF-8 bytes of canonical_json(tool).

    The whole descriptor is pinned: name, description, inputSchema, annotations and any other
    field the server sent. Changing any of them changes the digest; reordering keys does not.
    """
    approved_fields = {"name": tool["name"], "description": tool.get("description", "")}
    return hashlib.sha256(canonical_json(approved_fields).encode("utf-8")).hexdigest()


def scan_description(text: str) -> list[str]:
    """Labels of the INJECTION_PATTERNS found in text, in pattern order. Matching ignores case."""
    return [label for pattern, label in INJECTION_PATTERNS if re.search(pattern, text, re.S)]


def build_manifest(catalog: Catalog) -> dict[str, str]:
    """Approved digests for a reviewed catalog, keyed by qualified name (server.tool)."""
    return {
        f"{server}.{tool['name']}": descriptor_digest(tool)
        for server, tools in catalog.items()
        for tool in tools
    }


def scan_catalog(catalog: Catalog, approved: dict[str, str]) -> list[Finding]:
    """Findings for a live catalog against approved digests, sorted by (kind, key, detail).

    Every tool is checked on its own: its description is scanned, and its digest is compared
    with the approved digest under its qualified name ("unapproved" when there is none,
    "rug_pull" when it differs). A bare tool name offered by more than one server gives one
    "shadowing" finding that lists the qualified names, sorted.
    """
    findings: list[Finding] = []
    unqualified: dict[str, list[str]] = {}
    for server, tools in catalog.items():
        for tool in tools:
            key = f"{server}.{tool['name']}"
            unqualified.setdefault(tool["name"], []).append(key)
            for label in scan_description(tool.get("description")):
                findings.append(Finding("metadata_poisoning", key, label))
            digest = descriptor_digest(tool)
            if key not in approved:
                findings.append(Finding("unapproved", key, "descriptor has no approved digest"))
            elif not hmac.compare_digest(approved[key], digest):
                findings.append(Finding("rug_pull", key, "approved descriptor changed"))
    for name, keys in unqualified.items():
        if len(keys) > 1:
            findings.append(Finding("shadowing", name, ", ".join(sorted(keys))))
    return sorted(findings, key=lambda f: (f.kind, f.key, f.detail))


def visible_tools(catalog: Catalog, approved: dict[str, str]) -> list[dict[str, Any]]:
    """The tools the model may see: every tool with no finding under its qualified name.

    Each comes back as a copy renamed to its qualified name, sorted by that name. A shadowing
    finding names the bare tool name, so it hides nothing: qualified names keep the tools apart.
    """
    tools = []
    for server, server_tools in catalog.items():
        for tool in server_tools:
            key = f"{server}.{tool['name']}"
            if key not in {finding.key for finding in scan_catalog(catalog, approved)}:
                tools.append({**tool, "name": key})
    return sorted(tools, key=lambda tool: tool["name"])
