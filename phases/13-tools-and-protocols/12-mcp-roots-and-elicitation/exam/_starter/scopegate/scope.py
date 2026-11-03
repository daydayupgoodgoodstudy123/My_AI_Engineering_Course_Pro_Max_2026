"""Explicit scope: does a file URI stay inside a workspace?

This is the containment layer of the three-layer rule. It is lexical and never touches
the filesystem, so it cannot see symbolic links. Authorization lives in grants.py; the
operating-system sandbox is not part of this package.
"""
from __future__ import annotations

import posixpath
from urllib.parse import unquote, urlparse


def file_uri_parts(uri: str) -> tuple[str, str]:
    """Split a plain file URI into (host, normalized path).

    The path is percent-decoded exactly once and then normalized, so "." and ".."
    segments, encoded ones such as %2e%2e and %2f included, are resolved before
    anything compares paths. Other schemes, query strings and fragments raise ValueError.
    """
    if not isinstance(uri, str):
        raise ValueError(f"not a file URI: {uri!r}")
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.query or parsed.fragment:
        raise ValueError(f"not a plain file URI: {uri!r}")
    path = unquote(posixpath.normpath(parsed.path))
    if not path.startswith("/"):
        raise ValueError(f"file URI path must be absolute: {uri!r}")
    return parsed.netloc, path


def uri_within_workspace(workspace_uri: str, candidate_uri: str) -> bool:
    """True when candidate_uri is the workspace itself or lies below it.

    Both URIs are normalized with file_uri_parts, the hosts must match, and the paths
    are compared component by component, so file:///work/notes-evil/a.md is not inside
    file:///work/notes. Anything that is not a plain file URI is outside.
    """
    try:
        workspace_host, workspace_path = file_uri_parts(workspace_uri)
        candidate_host, candidate_path = file_uri_parts(candidate_uri)
    except ValueError:
        return False
    if workspace_host != candidate_host:
        return False
    return candidate_path.startswith(workspace_path)
