"""The admission decision: run every control on one server version, and pin it when all of them pass."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import (
    PROTOCOL_VERSION,
    REGISTRY_SOURCE,
    digest,
    is_sha256_digest,
    listed_version,
    normalize_https_remote_url,
    reported_server_info,
    toolset_digest,
)

CONTROLS = ("version", "status", "namespace", "source", "digest", "protocol", "capabilities", "tools")
RANGE_CHARACTERS = "^~<>=*|, "
TRUSTED_DIGEST_SOURCES = ("fetch", "package-service")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple[str, ...]  # the failed controls or rules; empty when allowed
    pin: dict[str, Any] | None = None


def live_failures(live: Any, required_capabilities: tuple[str, ...] = ("tools",)) -> list[str]:
    """The live controls a server/discover result fails, in CONTROLS order.

    protocol      live["supportedVersions"] is a list that holds PROTOCOL_VERSION. The record's
                  $schema date is the Registry's schema version, which is a different thing.
    capabilities  every required capability is a key of the live["capabilities"] object.
    tools         live["tools"] is a list of objects, each with a non-empty name and description
                  (strings that are not just whitespace) and an inputSchema object.
    """
    raise NotImplementedError


def decide(
    item: dict[str, Any],
    requested: str,
    verified_namespace: str,
    evidence: dict[str, Any],
    live: Any,
    required_capabilities: tuple[str, ...] = ("tools",),
    registry_source: str = REGISTRY_SOURCE,
) -> Decision:
    """Admit one server version, or say which controls it fails.

    item is the Registry listing item for the version (see listed_version), requested is the
    version the operator asked to admit, verified_namespace comes from the namespace verifier,
    evidence is the artifact verifier's result for one execution source, and live is what
    server/discover returned from the endpoint that will take the traffic.

    The controls, in CONTROLS order. reasons lists every failed control once, in that order.

    version       requested is exact and is the record's version, character for character. An
                  exact version is a non-empty string that is not "latest" and holds none of
                  RANGE_CHARACTERS: ^1.4 and latest select a version, they do not pin one.
    status        the Registry-managed status is active.
    namespace     the record's name is inside verified_namespace.
    source        a source the record declares joins the evidence, and evidence["verified"] is
                  True (the verifier proved ownership of that package or endpoint):
                    evidence["kind"] == "package": a record package with the same registryType,
                      identifier and version, whose transport.type is evidence["transportType"];
                    evidence["kind"] == "remote": a record remote whose url and evidence["url"]
                      both normalize (normalize_https_remote_url) to one and the same URL, and
                      whose type is evidence["transportType"].
                  A record may declare packages, remotes or both; one with remotes only is fine.
    digest        evidence["digest"] is a SHA-256 hex digest that the verifier calculated at its
                  trusted fetch boundary (evidence["digestFrom"] == "fetch") or received from a
                  package service whose verification result it validated ("package-service").
                  A digest the artifact supplies about itself ("artifact") proves nothing.
    protocol, capabilities, tools
                  live_failures(live, required_capabilities).

    When every control passes, the decision carries the pin:

        {"server": name, "version": version, "registryStatus": "active",
         "recordDigest": digest(record), "source": source, "sourceDigest": evidence["digest"],
         "toolsetDigest": toolset_digest(live["tools"]), "provenanceDigest": digest(provenance),
         "reportedServerInfo": reported_server_info(live)}

    source is {"kind": "package", **package} for the joined package, or {"kind": "remote",
    **remote, "url": <the normalized URL>} for the joined remote. provenance joins the evidence
    in one object: {"registrySource": registry_source, "server": name, "registryVersion":
    version, "recordDigest": ..., "source": source, "sourceDigest": ...}. reportedServerInfo is
    the server's own report, kept for diagnosis and never used to decide anything.
    """
    raise NotImplementedError
