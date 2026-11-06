"""Repo paths: where init and its probes find the repo's files."""
from __future__ import annotations

from pathlib import Path


def pin_paths(root: str | Path, layout: dict[str, str]) -> dict[str, Path]:
    """Resolve the repo's paths once, against the repo root, and pin them for the whole run.

    layout maps a name to a path inside the repo, relative to its root, as the init config
    lists them ({"manifest": "requirements.txt"}). root is the repo's top directory, absolute
    or relative to the directory init started in (git rev-parse --show-cdup prints "../../").
    The pre-task hook starts init wherever the agent is working, often deep inside the repo,
    so no path is ever taken relative to that directory.

    Every pinned path is absolute and normalized, with no "." or ".." left in it: it names the
    same file however the process moves later, and it compares equal to the same file pinned
    from anywhere else. Pinning only resolves. It does not check that the files exist (the
    probes that read them report what is missing), and it leaves the process's working
    directory where it was.
    """
    return {name: Path(rel).resolve() for name, rel in layout.items()}
