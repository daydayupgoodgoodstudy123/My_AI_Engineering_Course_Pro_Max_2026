"""Authorization: which principal may read or delete what."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

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
        raise NotImplementedError

    def allowed(self, principal: str, uri: str, action: str) -> bool:
        """Whether principal may perform action ("read" or "delete") on uri.

        Unknown actions raise ValueError.
        """
        raise NotImplementedError
