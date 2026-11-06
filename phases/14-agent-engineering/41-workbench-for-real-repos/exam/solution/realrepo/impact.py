"""Which tests a change can affect, worked out from the repo's import graph."""
from __future__ import annotations

import ast
from collections import deque
from collections.abc import Iterable

from .nodeids import covers


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
    importers: dict[str, set[str]] = {}
    for path, text in files.items():
        if path.endswith(".py"):
            for target in _imports(path, text, files):
                importers.setdefault(target, set()).add(path)
    reached = {path for path in changed if path.endswith(".py") and path in files}
    queue = deque(reached)
    while queue:
        for importer in importers.get(queue.popleft(), ()):
            if importer not in reached:
                reached.add(importer)
                queue.append(importer)
    return sorted(path for path in reached if _is_test(path))


def proves_change(
    acceptance: Iterable[str], files: dict[str, str], changed: Iterable[str]
) -> bool:
    """True when an acceptance selector runs a test the change can affect.

    The selector is an affected test file, a test or class inside one, or a directory above one.
    """
    affected = affected_tests(files, changed)
    return any(
        covers(selector.partition("::")[0], test) for selector in acceptance for test in affected
    )


def _is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") and name.endswith(".py")


def _imports(path: str, text: str, files: dict[str, str]) -> set[str]:
    """The repo files that importing this one runs directly."""
    package = path.split("/")[:-1]  # a module's package; for an __init__.py, the package it starts
    found: set[str] = set()
    for node in ast.walk(ast.parse(text, filename=path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found |= _module(alias.name.split("."), files)
        elif isinstance(node, ast.ImportFrom):
            if node.level > len(package):
                continue  # beyond the top-level package: Python refuses it too
            base = package[: len(package) - node.level + 1] if node.level else []
            parts = base + (node.module.split(".") if node.module else [])
            if not parts:
                continue
            found |= _module(parts, files)
            for alias in node.names:
                if alias.name != "*":
                    found |= _module([*parts, alias.name], files)
    found.discard(path)
    return found


def _module(parts: list[str], files: dict[str, str]) -> set[str]:
    """The repo files that importing the module parts runs: every package's __init__.py, the module."""
    found = set()
    for i in range(1, len(parts) + 1):
        init = "/".join(parts[:i]) + "/__init__.py"
        if init in files:
            found.add(init)
    module = "/".join(parts) + ".py"
    if module in files:
        found.add(module)
    return found
