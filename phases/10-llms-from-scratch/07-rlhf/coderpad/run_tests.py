"""Standalone CoderPad practice runner, Python 3.10+ / stdlib only.

Read PROMPT.md before implementing starter/main.py.
Use --solution only after the timed attempt.
This runner does not start or enforce a 45-minute timer.
"""
import argparse
import os
from pathlib import Path
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--core", action="store_true", help="Core cases only")
    group.add_argument("--bonus", action="store_true", help="Bonus cases only")
    parser.add_argument("--solution", action="store_true", help="Use the independent reference")
    parser.add_argument("--list", action="store_true", help="Collect without executing")
    parser.add_argument("-k", default="", help="Keep test ids containing this substring")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--json-report", type=Path, help="Write a machine-readable score report")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    os.environ["CODERPAD_IMPLEMENTATION"] = "solution" if args.solution else "starter"
    loader = unittest.TestLoader()
    discovered = loader.discover(str(root / "tests"), pattern="test_*.py")
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        return 2
    selected = [t for t in flatten(discovered)
                if (not args.core or ".CoreTests." in t.id())
                and (not args.bonus or ".BonusTests." in t.id())
                and args.k in t.id()]
    if not selected:
        print("No tests selected.", file=sys.stderr)
        return 2
    if args.list:
        for test in selected:
            print(test.id())
        print(f"Collected {len(selected)} cases (subTest inputs do not count separately).")
        return 0
    result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(unittest.TestSuite(selected))
    failed = {t.id() for t, _ in result.failures + result.errors}
    skipped = {t.id() for t, _ in result.skipped}
    # A failed subTest reports its parent case as the unit of scoring.
    failed_parents = {getattr(t, "test_case", t).id() for t, _ in result.failures + result.errors}
    counts = {}
    for label, class_name in (("core", "CoreTests"), ("bonus", "BonusTests")):
        ids = {t.id() for t in selected if f".{class_name}." in t.id()}
        counts[label] = {"total": len(ids), "passed": len(ids - failed - failed_parents - skipped)}
    report = {"implementation": os.environ["CODERPAD_IMPLEMENTATION"],
              "success": result.wasSuccessful(), "counts": counts,
              "failed_cases": sorted(failed_parents), "skipped_cases": sorted(skipped)}
    if args.json_report:
        import json
        args.json_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Implementation: {report['implementation']}")
    for label, score in counts.items():
        if score["total"]:
            print(f"{label}: {score['passed']}/{score['total']} cases passed")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
