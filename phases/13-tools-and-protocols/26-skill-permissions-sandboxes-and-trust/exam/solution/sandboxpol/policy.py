"""The lesson's non-executing policy reviewer: one proposed action in, allow / require-approval / deny out."""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require-approval"


@dataclass(frozen=True)
class SandboxPolicy:
    """Host policy. network_allowlist holds HTTPS origins: scheme, host and effective port."""

    workspace_root: Path
    allowed_kinds: tuple[str, ...] = ("read",)
    command_allowlist: tuple[tuple[str, ...], ...] = ()
    network_allowlist: tuple[str, ...] = ()
    approval_kinds: tuple[str, ...] = ("write", "delete", "network")
    permit_secret_use_after_approval: bool = False


@dataclass(frozen=True)
class ActionRequest:
    kind: str
    target: str | None = None
    command: tuple[str, ...] = ()
    url: str | None = None
    payload: str = ""
    influenced_by_untrusted_content: bool = False
    approved: bool = False
    claimed_permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewDecision:
    verdict: Verdict
    rule: str
    reason: str
    normalized_target: str | None = None
    normalized_origin: str | None = None
    claimed_permissions_ignored: bool = False
    executed: bool = False

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data


class SandboxViolation(ValueError):
    pass


SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SHELL_METACHARACTERS = {";", "&&", "||", "|", ">", ">>", "<", "`"}
DESTRUCTIVE_EXECUTABLES = {"rm", "rmdir", "sudo", "chmod", "chown", "mkfs", "dd"}


def contains_secret(value: str) -> bool:
    """True when the text looks like it carries a credential.

    Three shapes count: a key=value or key: value pair whose key ends in api_key, access_token,
    secret or password (DB_PASSWORD=..., x-api-key: ...); an Authorization: Bearer header;
    a PEM private key block. Hashes, certificates and other public material do not count.
    """
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def normalize_https_origin(value: str, *, origin_only: bool = False) -> str:
    """Return the canonical HTTPS origin of a URL: https://host:port.

    The host is lowercased, without a trailing dot, IDNA-encoded, and bracketed when it is an
    IPv6 address. The effective port is always written out: 443 when the URL gives none.
    Ports outside 1-65535 make the URL invalid. Invalid URLs raise ValueError.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("HTTPS origin must be a non-empty string")
    try:
        parsed = urlparse(value)
    except ValueError as error:
        raise ValueError("HTTPS origin is malformed") from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("URL must use HTTPS, contain a host, and omit userinfo")
    if origin_only and (
        parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment
    ):
        raise ValueError("allowlist entries must be HTTPS origins without path, query, or fragment")

    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname or "%" in hostname:
        raise ValueError("HTTPS origin contains an invalid host")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise ValueError("HTTPS origin contains an invalid host") from error
        labels = hostname.split(".")
        if len(hostname) > 253 or any(
            not HOST_LABEL_PATTERN.fullmatch(label) for label in labels
        ):
            raise ValueError("HTTPS origin contains an invalid host")
        origin_host = hostname
    else:
        origin_host = address.compressed
        if address.version == 6:
            origin_host = f"[{origin_host}]"
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("HTTPS origin contains an invalid port") from error
    if port is None:
        port = 443
    elif not 1 <= port <= 65535:
        raise ValueError("HTTPS origin contains an invalid port")
    return f"https://{origin_host}:{port}"


def origin_allowed(origin: str, allowed: Iterable[str]) -> bool:
    """True when origin is one of the allowed origins.

    Both sides are normalized origins, so scheme, host and effective port must all match.
    """
    return origin in set(allowed)


def normalize_workspace_path(workspace_root: Path, target: str) -> Path:
    root = workspace_root.resolve(strict=True)
    raw_target = Path(target)
    candidate = raw_target if raw_target.is_absolute() else root / raw_target
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise SandboxViolation("path resolves outside the workspace jail")
    if candidate.is_symlink():
        raise SandboxViolation("direct symlink targets are rejected")
    return resolved


def inspect_command(
    command: tuple[str, ...], allowlist: Iterable[tuple[str, ...]]
) -> tuple[bool, str]:
    """Inspect an argv vector without invoking a shell or subprocess.

    The command must start with one of the approved argv prefixes, element by element;
    arguments after the prefix are free.
    """
    if not command:
        return False, "empty command"
    executable = command[0]
    if Path(executable).name != executable or "/" in executable or "\\" in executable:
        return False, "command must use an allowlisted bare executable name"
    if executable in DESTRUCTIVE_EXECUTABLES:
        return False, f"destructive executable {executable!r} is denied"
    if executable == "git" and len(command) > 1 and command[1] in {"clean", "reset"}:
        return False, f"destructive git subcommand {command[1]!r} is denied"
    if any(token in SHELL_METACHARACTERS for token in command):
        return False, "shell metacharacters are denied; pass a direct argv vector"
    allowed_prefixes = tuple(tuple(prefix) for prefix in allowlist)
    if not any(
        prefix and tuple(command[: len(prefix)]) == prefix for prefix in allowed_prefixes
    ):
        return False, "command does not match an approved argv prefix"
    return True, "command argv matched an approved prefix in the non-executing review"


def _decision(
    request: ActionRequest,
    verdict: Verdict,
    rule: str,
    reason: str,
    normalized_target: Path | None = None,
    normalized_origin: str | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        verdict=verdict,
        rule=rule,
        reason=reason,
        normalized_target=None if normalized_target is None else str(normalized_target),
        normalized_origin=normalized_origin,
        claimed_permissions_ignored=bool(request.claimed_permissions),
    )


def review_action(policy: SandboxPolicy, request: ActionRequest) -> ReviewDecision:
    """Classify one proposed action. This function has no execution path."""
    if request.kind == "policy-change":
        return _decision(
            request,
            Verdict.DENY,
            "authority-boundary",
            "skill or external content cannot modify the host permission model",
        )
    if request.kind not in policy.allowed_kinds:
        return _decision(
            request,
            Verdict.DENY,
            "kind-allowlist",
            f"action kind {request.kind!r} is not allowed by host policy",
        )

    normalized: Path | None = None
    normalized_origin: str | None = None
    if request.kind in {"read", "write", "delete"}:
        if not request.target:
            return _decision(request, Verdict.DENY, "path-required", "filesystem action needs a target")
        try:
            normalized = normalize_workspace_path(policy.workspace_root, request.target)
        except (OSError, SandboxViolation) as error:
            return _decision(request, Verdict.DENY, "workspace-jail", str(error))

    if request.kind == "command":
        allowed, reason = inspect_command(request.command, policy.command_allowlist)
        if not allowed:
            return _decision(request, Verdict.DENY, "command-review", reason)

    if request.kind == "network":
        if not request.url:
            return _decision(request, Verdict.DENY, "url-required", "network action needs a URL")
        try:
            normalized_origin = normalize_https_origin(request.url)
        except ValueError as error:
            return _decision(
                request,
                Verdict.DENY,
                "network-shape",
                str(error),
            )
        try:
            allowed_origins = {
                normalize_https_origin(origin, origin_only=True)
                for origin in policy.network_allowlist
            }
        except ValueError as error:
            return _decision(
                request,
                Verdict.DENY,
                "network-policy-shape",
                str(error),
                normalized_origin=normalized_origin,
            )
        if not origin_allowed(normalized_origin, allowed_origins):
            return _decision(
                request,
                Verdict.DENY,
                "network-allowlist",
                f"HTTPS origin {normalized_origin!r} is not allowlisted",
                normalized_origin=normalized_origin,
            )

    secret_material = contains_secret(request.payload) or contains_secret(
        " ".join(request.command)
    )
    if secret_material and not (
        request.approved and policy.permit_secret_use_after_approval
    ):
        verdict = (
            Verdict.REQUIRE_APPROVAL
            if policy.permit_secret_use_after_approval
            else Verdict.DENY
        )
        return _decision(
            request,
            verdict,
            "secret-review",
            "possible secret material requires an explicit host-approved path",
            normalized,
            normalized_origin,
        )

    approval_needed = request.kind in policy.approval_kinds
    if request.influenced_by_untrusted_content and request.kind in {
        "write",
        "delete",
        "command",
        "network",
    }:
        approval_needed = True
    if approval_needed and not request.approved:
        reason = (
            "untrusted external content influenced a stateful request"
            if request.influenced_by_untrusted_content
            else f"host policy gates {request.kind!r} behind approval"
        )
        return _decision(
            request,
            Verdict.REQUIRE_APPROVAL,
            "approval-gate",
            reason,
            normalized,
            normalized_origin,
        )

    return _decision(
        request,
        Verdict.ALLOW,
        "policy-allow",
        "request stayed within the host policy and workspace jail",
        normalized,
        normalized_origin,
    )
