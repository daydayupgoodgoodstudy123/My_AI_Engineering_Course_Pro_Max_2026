"""Practice-session switches. The tests themselves are in tests/test_parts.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def pytest_addoption(parser):
    group = parser.getgroup("exam")
    group.addoption(
        "--solution",
        action="store_true",
        help="test the reference in solution/ instead of your code (after the timed attempt)",
    )
    group.addoption(
        "--all-parts",
        action="store_true",
        help='ignore the @pytest.mark.skip("Part N") locks and run every part',
    )


def pytest_configure(config):
    if config.getoption("--solution"):
        sys.path.insert(0, str(ROOT / "solution"))


def _is_part_lock(mark) -> bool:
    reason = mark.kwargs.get("reason", mark.args[0] if mark.args else "")
    return mark.name == "skip" and str(reason).startswith("Part")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--all-parts"):
        for item in items:
            item.own_markers = [m for m in item.own_markers if not _is_part_lock(m)]
