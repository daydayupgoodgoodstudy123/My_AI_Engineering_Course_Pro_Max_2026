"""Which tests a change can affect, worked out from the repo's import graph."""
from __future__ import annotations

from collections.abc import Iterable


def affected_tests(files: dict[str, str], changed: Iterable[str]) -> list[str]:
    """The test files a change can affect, sorted.

    files maps every repo-relative path to its text; changed lists the paths the change touches.
    A test file is a .py file whose name starts with test_. It is affected when it is changed
    itself, or when it imports a changed .py file, directly or through other modules of the repo.
    Imports resolve as Python would with the repo root on sys.path: absolute and relative imports,
    wherever they appear in the file. Importing a.b.c runs a/__init__.py and a/b/__init__.py, and
    from a.b import c imports the submodule a.b.c when the repo has one. Modules that are not
    files of the repo (json, pytest, ...) are ignored, and a change to a file that is not Python
    affects no test.
    """
    raise NotImplementedError


def proves_change(
    acceptance: Iterable[str], files: dict[str, str], changed: Iterable[str]
) -> bool:
    """True when an acceptance selector runs a test the change can affect.

    The selector is an affected test file, a test or class inside one, or a directory above one.
    """
    raise NotImplementedError
