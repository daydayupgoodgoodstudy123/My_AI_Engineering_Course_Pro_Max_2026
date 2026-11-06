"""Install the files owned by a versioned workbench pack."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

CI_FILE = ".github/workflows/workbench.yml"
CI_BODY = b"name: workbench\non: [push]\n"


@dataclass(frozen=True)
class InstallReceipt:
    files: tuple[str, ...]
    unmanaged: tuple[str, ...]
    ci_wired: bool


def preview_paths(managed: list[str], inventory: list[str]) -> dict[str, bool]:
    """Report exact relative-path presence, without collapsing equal basenames."""
    known = set(inventory)
    return {rel: rel in known for rel in managed}


def _ci_enabled(target: Path) -> bool:
    """Whether the target already has a CI workflows directory to integrate with."""
    return (target / ".github/workflows").is_dir()


def _ci_files(target: Path) -> dict[str, bytes]:
    """Add our workflow only when the target already has a workflows directory."""
    if not _ci_enabled(target):
        return {}
    existing = {p.name for p in (target / ".github/workflows").iterdir()}
    return {} if "workbench.yml" in existing else {CI_FILE: CI_BODY}


def _check_existing(target: Path, pack: dict[str, bytes], force: bool) -> None:
    """Without force, refuse every existing destination owned by this install."""
    if not force:
        for rel in pack:
            if (target / rel).exists():
                raise FileExistsError(rel)


def _unmanaged(target: Path, pack: dict[str, bytes]) -> tuple[str, ...]:
    """Report existing files under docs, schemas and scripts absent from the pack."""
    owned = set(pack)
    return tuple(sorted(
        p.relative_to(target).as_posix()
        for folder in ("docs", "schemas", "scripts")
        for p in (target / folder).rglob("*")
        if p.is_file() and p.relative_to(target).as_posix() not in owned
    ))


def _write_file(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def install(target: Path, pack: dict[str, bytes], version: str, force: bool = False,
            writer: Callable[[Path, bytes], None] = _write_file) -> InstallReceipt:
    """Install only listed files and optionally our CI workflow.

    Existing managed files require force; unlisted user files are retained and
    reported. Publish .workbench-version only after every copy succeeds. The
    writer is injectable and may raise; this function does not roll back copies.
    """
    selected = {**pack, **_ci_files(target)}
    _check_existing(target, selected, force)
    unmanaged = _unmanaged(target, selected)
    for rel, body in selected.items():
        writer(target / rel, body)
    (target / ".workbench-version").write_text(version + "\n", encoding="utf-8")
    return InstallReceipt(tuple(selected), unmanaged, CI_FILE in selected)
