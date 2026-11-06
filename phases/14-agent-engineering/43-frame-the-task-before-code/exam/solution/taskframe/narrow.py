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
    for path in planned:
        blocked = [entry for entry in forbidden if covers(entry, path)]
        if blocked:
            raise ValueError(f"{path} is planned but {blocked[0]} forbids it")
    wanted = set(planned)
    root = _with_new_files(tree, wanted)

    def visit(node: dict, path: str) -> tuple[bool, list[str]]:
        complete = True
        entries: list[str] = []
        for name, child in node.items():
            child_path = f"{path}/{name}" if path else name
            if isinstance(child, dict):
                child_complete, child_entries = visit(child, child_path)
                complete = complete and child_complete
                entries.extend(child_entries)
            elif child_path in wanted:
                entries.append(child_path)
            else:
                complete = False
        if (
            path
            and complete
            and len(entries) >= 2
            and not any(covers(path + "/**", entry) for entry in forbidden)
        ):
            return True, [path + "/**"]
        return complete, entries

    return sorted(visit(root, "")[1])


def _with_new_files(tree: Tree, wanted: set[str]) -> dict:
    root = _copy(tree)
    for path in sorted(wanted):
        *dirs, name = path.split("/")
        node = root
        for part in dirs:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError(f"{path}: {part} is a file")
            node = child
        if isinstance(node.get(name), dict):
            raise ValueError(f"{path} is a directory")
        node.setdefault(name, "")
    return root


def _copy(tree: Tree) -> dict:
    return {name: _copy(node) if isinstance(node, dict) else node for name, node in tree.items()}
