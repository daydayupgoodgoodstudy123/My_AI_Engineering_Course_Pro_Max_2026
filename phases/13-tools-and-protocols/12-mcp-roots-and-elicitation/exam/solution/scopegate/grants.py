"""Authorization: which principal may read or delete what."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .scope import file_uri_parts, uri_within_workspace

ACTIONS = ("read", "delete")
PERMISSIONS = ("read", "delete", "deny")


@dataclass(frozen=True)
class Grant:
    principal: str
    workspace_uri: str
    permission: str  # "read", "delete" or "deny"


class WorkspaceList:
    """The flat allowlist the lesson starts from: a principal may read and delete
    anything inside the workspaces listed for it."""

    def __init__(self, workspaces: Mapping[str, Iterable[str]]) -> None:
        self._workspaces = {principal: tuple(uris) for principal, uris in workspaces.items()}

    def allowed(self, principal: str, uri: str, action: str) -> bool:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        return any(uri_within_workspace(workspace, uri) for workspace in self._workspaces.get(principal, ()))


@dataclass
class _Node:
    children: dict[str, "_Node"] = field(default_factory=dict)
    grants: dict[str, set[str]] = field(default_factory=dict)  # principal -> permissions on this workspace


def _components(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


class GrantTree:
    """Nested workspace grants, arranged as a tree of path components.

    For a principal, the grants on the most specific workspace at or above a URI decide.
    On one workspace, deny beats read and delete, and read plus delete is delete. A
    delete grant allows reading too; a read grant allows only reading. A URI with no
    grant at or above it is denied, and so is anything that is not a plain file URI.
    Grant URIs and target URIs are normalized the same way (scope.file_uri_parts)
    before they are matched.
    """

    def __init__(self, grants: Iterable[Grant]) -> None:
        """Unknown permissions and grant URIs that are not plain file URIs raise ValueError."""
        self._roots: dict[str, _Node] = {}
        for grant in grants:
            if grant.permission not in PERMISSIONS:
                raise ValueError(f"unknown permission {grant.permission!r}")
            host, path = file_uri_parts(grant.workspace_uri)
            node = self._roots.setdefault(host, _Node())
            for part in _components(path):
                node = node.children.setdefault(part, _Node())
            node.grants.setdefault(grant.principal, set()).add(grant.permission)

    def allowed(self, principal: str, uri: str, action: str) -> bool:
        """Whether principal may perform action ("read" or "delete") on uri.

        Unknown actions raise ValueError.
        """
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        try:
            host, path = file_uri_parts(uri)
        except ValueError:
            return False
        root = self._roots.get(host)
        deciding = set() if root is None else _deciding(root, _components(path), principal, set())
        if not deciding or "deny" in deciding:
            return False
        return "delete" in deciding or (action == "read" and "read" in deciding)


def _deciding(node: _Node, parts: list[str], principal: str, inherited: set[str]) -> set[str]:
    """The principal's permissions on the deepest workspace along parts that has any."""
    here = node.grants.get(principal, inherited)
    child = node.children.get(parts[0]) if parts else None
    return here if child is None else _deciding(child, parts[1:], principal, here)
