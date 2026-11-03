"""Level 3 reads: a skill may read only the files inside its own package."""
from __future__ import annotations

from pathlib import Path, PurePosixPath


class ReferencePathError(ValueError):
    """A reference that is not a clean path to a regular file inside the package."""


def validate_reference(package: Path, reference: str) -> Path:
    """The file a reference names inside a skill package, as a resolved path.

    A reference is a clean relative POSIX path: no backslash, no absolute path, no "..".
    Symlinks inside the package are allowed, but the resolved target must stay inside the
    resolved package root and must be a regular file.
    """
    if not isinstance(reference, str) or not reference:
        raise ReferencePathError("a reference is a non-empty string")
    if "\\" in reference:
        raise ReferencePathError("references use forward slashes")
    relative = PurePosixPath(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReferencePathError("a reference is a clean relative path")
    root = package.resolve()
    target = root.joinpath(*relative.parts).resolve()
    if root not in target.parents:
        raise ReferencePathError("the reference escapes the skill package")
    if not target.is_file():
        raise ReferencePathError("a reference names a regular file")
    return target
