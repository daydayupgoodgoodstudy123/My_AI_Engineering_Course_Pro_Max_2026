"""Refresh decisions: what every live tool gets, given its pin and the scan."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .pins import Pin
from .scanner import INJECTION_PATTERNS, Catalog, descriptor_digest, scan_description

APPROVED = "approved"
QUARANTINE_UNKNOWN = "quarantine_unknown"
QUARANTINE_CHANGED = "quarantine_changed"
BLOCKED = "blocked"


@dataclass(frozen=True)
class Decision:
    key: str  # qualified name, server.tool
    server: str
    name: str  # the server's own name for the tool
    status: str  # APPROVED, QUARANTINE_UNKNOWN, QUARANTINE_CHANGED or BLOCKED
    digest: str  # descriptor_digest of the live descriptor
    findings: tuple[str, ...] = ()  # the scan_descriptor labels behind a BLOCKED decision


@dataclass(frozen=True)
class Refresh:
    decisions: list[Decision]
    visible: list[dict[str, Any]]
    shadowed: dict[str, list[str]]
    removed: list[str]


def scan_descriptor(tool: dict[str, Any]) -> tuple[str, ...]:
    """Scanner labels found anywhere in a descriptor, each once, in INJECTION_PATTERNS order.

    The model reads the whole descriptor, so every string value in it is scanned: the description,
    and the descriptions, titles and enum values nested inside inputSchema or annotations.
    """
    raise NotImplementedError


def refresh(pins: Mapping[str, Pin], catalogs: Catalog) -> Refresh:
    """Decide every live tool of a refresh. catalogs holds the complete listing of each backend.

    A tool's key is its qualified name, server.tool. Its status is the first of these that applies:

    - BLOCKED: scan_descriptor finds something, whatever the pin says. An equal digest proves
      that a descriptor is stable, not that it is safe.
    - QUARANTINE_UNKNOWN: there is no pin under its key. Nothing is pinned on first sight, and a
      pin under another key never vouches for this one, even for an identical descriptor.
    - QUARANTINE_CHANGED: its digest differs from the pin, or the pin is quarantined. A rug pull
      stays quarantined until a reviewer approves the tool again.
    - APPROVED: otherwise.

    decisions has one Decision per live tool, sorted by key. visible holds the approved descriptors
    and nothing else, each a copy renamed to its qualified name, sorted by name: every tool goes by
    its qualified name, whether or not another server offers the same bare name. shadowed maps every
    bare name offered by two or more servers to their qualified names, sorted. removed lists the
    pinned keys that no listing has any more, sorted. The order of servers and tools in catalogs
    changes nothing.
    """
    raise NotImplementedError
