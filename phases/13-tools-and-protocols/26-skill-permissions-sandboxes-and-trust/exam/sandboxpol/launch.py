"""Turn a structured request into the launch the executor may make.

A request is the lesson's structured action for process.run: the argv, the paths the process
touches and how, the URLs it contacts and the credentials it needs. The plan says whether it
may run (one rule decides), what an approver must accept, the environment the process starts
with, and which credentials the egress proxy attaches to requests for which origin. The
process itself never sees a credential.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .policy import (
    SandboxViolation,
    Verdict,
    inspect_command,
    normalize_https_origin,
    normalize_workspace_path,
    origin_allowed,
)

READ, CREATE, OVERWRITE, SEND = "read", "create", "overwrite", "send"


@dataclass(frozen=True)
class PathUse:
    path: str  # relative to the workspace, or absolute
    access: str  # "read" or "write"


@dataclass(frozen=True)
class LaunchRequest:
    actor: str
    argv: tuple[str, ...]
    paths: tuple[PathUse, ...] = ()
    network: tuple[str, ...] = ()  # URLs the process will contact
    credentials: tuple[str, ...] = ()  # names of the credentials it needs
    side_effect: str = "read_only"  # the requester's own description of the action
    approved: frozenset[str] = frozenset()  # consequences an approver has accepted


@dataclass(frozen=True)
class LaunchPolicy:
    workspace: Path
    commands: tuple[tuple[str, ...], ...]  # approved argv prefixes
    grants: Mapping[str, tuple[str, ...]]  # read / create / overwrite -> workspace-relative roots
    origins: tuple[str, ...]  # HTTPS origin allowlist
    env: Mapping[str, str]  # environment entries every launch gets
    pass_env: tuple[str, ...] = ()  # host variables copied into the environment when set
    credentials: Mapping[str, str] = field(default_factory=dict)  # credential -> its one origin
    approval: tuple[str, ...] = (OVERWRITE, SEND)  # consequences that need an approver


@dataclass(frozen=True)
class LaunchPlan:
    verdict: Verdict
    rule: str
    consequences: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    inject: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Hop:
    verdict: Verdict
    rule: str
    url: str  # the absolute URL of the next request
    origin: str | None
    credentials: tuple[str, ...]  # what the proxy attaches to the next request


def plan_launch(
    policy: LaunchPolicy, request: LaunchRequest, host_env: Mapping[str, str]
) -> LaunchPlan:
    """Review a structured request and plan its launch.

    Checks run in this order, and the first failure decides a deny:
      command-review     the argv does not start with an approved prefix (inspect_command)
      workspace-jail     a path resolves outside the workspace
      path-<operation>   the operation is not granted under any of its roots. A read is
                         "read"; a write is "create" when the resolved target does not exist
                         yet and "overwrite" when it does. Each operation has its own roots
                         and a path counts as under a root only after both are resolved.
      network-shape      a URL is not a valid HTTPS URL
      network-allowlist  a URL's origin is not allowlisted
      credential-scope   a credential has no scope in the policy, or its origin is not one
                         of the request's network origins
    Paths are checked in request order, then URLs, then credentials.

    Consequences are what an approver sees, one line per consequence, in request order:
    "<operation> <path>" for a path whose operation is in policy.approval, with the resolved
    path relative to the workspace in POSIX form, then "send <credential> to <origin>" when
    "send" is in policy.approval. The verdict is require-approval (rule approval-gate) while
    any consequence is missing from request.approved, else allow (rule policy-allow).
    side_effect is the requester's own description and never changes the review.

    An allowed or gated plan carries the environment: policy.env, plus the host variables
    named in pass_env that are set (policy.env wins over the host), and nothing else. inject
    maps each normalized origin to the credentials, in request order, the proxy attaches to
    requests for that origin. A denied plan carries no consequences, environment or credentials.
    """
    raise NotImplementedError


def follow_redirect(policy: LaunchPolicy, plan: LaunchPlan, url: str, location: str) -> Hop:
    """Check a redirect from url to location before the proxy follows it.

    location may be absolute or relative to url. The next request is checked like a new one:
    it must be a valid HTTPS URL (else deny, network-shape) for an allowlisted origin (else
    deny, network-allowlist). An allowed hop (rule redirect-allow) carries only the credentials
    plan.inject scopes to the new origin.
    """
    raise NotImplementedError
