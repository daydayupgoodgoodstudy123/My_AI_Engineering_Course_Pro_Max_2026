"""pytest node ids, and the selectors that run them."""
from __future__ import annotations

from pathlib import PurePosixPath


def ancestors(nodeid: str) -> list[str]:
    """Every selector that runs this test, outermost first, ending with the node id itself.

    A selector is what you would pass to pytest: a directory, a test module, a class, a test
    function (all of its parametrized cases) or one node id. For example
    "api/tests/test_x.py::TestA::test_f[1-2]" gives "api", "api/tests", "api/tests/test_x.py",
    "api/tests/test_x.py::TestA", "api/tests/test_x.py::TestA::test_f" and the node id itself.
    """
    path, sep, rest = nodeid.partition("::")
    out = [str(parent) for parent in reversed(PurePosixPath(path).parents) if str(parent) != "."]
    out.append(path)
    if not sep:
        return out
    names, bracket, _ = rest.partition("[")
    prefix = path
    for name in names.split("::"):
        prefix = f"{prefix}::{name}"
        out.append(prefix)
    if bracket:
        out.append(nodeid)
    return out


def covers(selector: str, nodeid: str) -> bool:
    """True when `pytest <selector>` runs the test nodeid."""
    return selector in ancestors(nodeid)
