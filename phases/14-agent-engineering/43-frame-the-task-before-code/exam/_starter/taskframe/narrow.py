"""Narrow a broad allowed path to the smallest safe set of entries."""
from __future__ import annotations

from typing import Union

from .frame import covers

# A checkout as nested dicts: a name maps to a subdirectory (a dict, possibly empty) or to
# the text of a file.
Tree = dict[str, Union["Tree", str]]


def narrow_paths(tree: Tree, planned: list[str], forbidden: list[str]) -> list[str]:
    """The fewest allowed entries that cover every planned file and nothing forbidden.

    tree is the checkout. planned are the files the change will touch; a planned file
    missing from the tree is a new file, and its directories may be new too. forbidden
    entries are files or "dir/**" and need not exist.

    A directory becomes the one entry "dir/**" when every file at or below it is planned,
    no forbidden entry lies at or below it, and that entry replaces two or more entries:
    collapsing never widens the scope for nothing. Otherwise the directory contributes its
    planned files and the entries of its subdirectories. An empty directory adds nothing,
    and the repository root is never collapsed. The result is sorted. A planned file that
    is forbidden raises ValueError.
    """
    raise NotImplementedError
