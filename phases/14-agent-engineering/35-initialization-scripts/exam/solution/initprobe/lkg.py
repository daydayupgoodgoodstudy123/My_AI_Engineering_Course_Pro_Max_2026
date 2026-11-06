"""Last-known-good anchoring: diff HEAD's tree against the LKG commit's and hold init to a budget.

Every session anchors against the same last-known-good commit, so drift cannot compound from
one session to the next. When HEAD has moved too far, init refuses to start and a human has to
ratify a new baseline.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

TREE = "40000"
FILE = "100644"
EXEC = "100755"
LKG_FILE_BUDGET = 50
INIT_DIR = ".init"  # init's own files (the LKG pin, the lock, the report) live here


@dataclass(frozen=True)
class Entry:
    """One name in a tree: a subtree (mode TREE) or a file (FILE or EXEC), by object id."""

    mode: str
    oid: str


class ObjectStore:
    """Git objects in memory: blobs, trees and commits.

    Blobs and trees are named by the SHA-1 of their git encoding, as git names them, so two
    trees that hold the same files have the same oid however they were built. tree() and blob()
    count every read in self.reads.
    """

    def __init__(self) -> None:
        self._objects: dict[str, tuple[str, object]] = {}
        self.reads = 0

    def _put(self, kind: str, body: bytes, value: object) -> str:
        oid = hashlib.sha1(f"{kind} {len(body)}\0".encode() + body).hexdigest()
        self._objects.setdefault(oid, (kind, value))
        return oid

    def put_blob(self, data: bytes) -> str:
        return self._put("blob", data, bytes(data))

    def put_tree(self, entries: dict[str, Entry]) -> str:
        def git_order(name: str) -> bytes:  # git sorts a subtree as if its name ended in "/"
            return (name + "/" if entries[name].mode == TREE else name).encode()

        body = b"".join(
            f"{entries[name].mode} {name}".encode() + b"\0" + bytes.fromhex(entries[name].oid)
            for name in sorted(entries, key=git_order)
        )
        return self._put("tree", body, dict(entries))

    def commit(self, tree: str, message: str) -> str:
        return self._put("commit", f"tree {tree}\n\n{message}\n".encode(), tree)

    def _get(self, oid: str, kind: str) -> object:
        found, value = self._objects[oid]
        if found != kind:
            raise TypeError(f"{oid[:7]} is a {found}, not a {kind}")
        return value

    def blob(self, oid: str) -> bytes:
        self.reads += 1
        return self._get(oid, "blob")

    def tree(self, oid: str) -> dict[str, Entry]:
        """The entries of a tree, in the order they were stored. Counts as a read."""
        self.reads += 1
        return dict(self._get(oid, "tree"))

    def commit_tree(self, oid: str) -> str:
        """The root tree of a commit. Raises KeyError for a commit the store does not have."""
        return self._get(oid, "commit")

    def build(self, spec: dict) -> str:
        """Store a nested dict as a tree and return its oid.

        A dict is a directory, bytes a file with mode FILE, and (bytes, mode) a file with that
        mode. {} is an empty directory.
        """
        entries: dict[str, Entry] = {}
        for name, value in spec.items():
            if isinstance(value, dict):
                entries[name] = Entry(TREE, self.build(value))
            elif isinstance(value, tuple):
                data, mode = value
                entries[name] = Entry(mode, self.put_blob(data))
            else:
                entries[name] = Entry(FILE, self.put_blob(value))
        return self.put_tree(entries)


def diff_trees(store: ObjectStore, old: str, new: str) -> list[tuple[str, str]]:
    """The files that differ between two trees, as (status, path) pairs sorted by path.

    status is "A" for a file only in new, "D" for a file only in old, and "M" for a file in
    both whose content or mode changed. Paths are joined with "/". Only files count: a
    directory is never listed itself, so an empty directory that appears or disappears
    changes nothing. A file that moved is a "D" at its old path and an "A" at its new one.
    When a name is a directory on one side and a file on the other, every file under the
    directory is added or deleted, and so is the file.

    Two subtrees with the same oid hold the same files, so they are skipped without being read:
    only the trees on the way to a change are read, and blobs never are.
    """
    changes: list[tuple[str, str]] = []
    _walk(store, old, new, "", changes)
    return sorted(changes, key=lambda change: change[1])


def _walk(store: ObjectStore, old: str | None, new: str | None, prefix: str, out: list) -> None:
    if old == new:
        return
    before = store.tree(old) if old is not None else {}
    after = store.tree(new) if new is not None else {}
    for name in before.keys() | after.keys():
        path = prefix + name
        a, b = before.get(name), after.get(name)
        a_dir = a is not None and a.mode == TREE
        b_dir = b is not None and b.mode == TREE
        if a_dir or b_dir:
            _walk(store, a.oid if a_dir else None, b.oid if b_dir else None, path + "/", out)
        a_file = a is not None and not a_dir
        b_file = b is not None and not b_dir
        if a_file and b_file:
            if a != b:
                out.append(("M", path))
        elif a_file:
            out.append(("D", path))
        elif b_file:
            out.append(("A", path))


def lkg_drift(
    store: ObjectStore, lkg: str | None, head: str, budget: int = LKG_FILE_BUDGET
) -> tuple[str, str]:
    """What the lkg_diff probe finds: (status, detail) for HEAD against the last-known-good commit.

    No LKG pinned yet is a warn: "no last-known-good commit; pin one after the first successful
    merge". An LKG commit the store does not have is a fail, "last-known-good commit <first 7>
    not found", because a human has to pin a new baseline. Otherwise the files that differ
    (diff_trees), not counting init's own files under .init/, are held to the budget: more than
    `budget` files is a fail, anything else a pass, both with the detail
    "<n> files changed since <first 7 of lkg> (budget <budget>)".
    """
    if lkg is None:
        return "warn", "no last-known-good commit; pin one after the first successful merge"
    try:
        base = store.commit_tree(lkg)
    except KeyError:
        return "fail", f"last-known-good commit {lkg[:7]} not found"
    changed = [
        path
        for _, path in diff_trees(store, base, store.commit_tree(head))
        if not path.startswith(INIT_DIR + "/")
    ]
    status = "fail" if len(changed) > budget else "pass"
    return status, f"{len(changed)} files changed since {lkg[:7]} (budget {budget})"
