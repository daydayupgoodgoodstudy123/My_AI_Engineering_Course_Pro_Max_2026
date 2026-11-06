"""Verify a staged-brownfield exam pack against its solution/traps.json.

    python3 scripts/exam_curriculum/check_traps.py <lesson>/exam --python <python with pytest> [--write]

Every check runs on a temporary copy, so the pack itself is never executed in place.
Checks:
  1. all parts are locked by default;
  2. the reference in solution/ passes every part, within the time budget;
  3. the starter, with every part unlocked, fails every part and imports cleanly;
  4. Part layers: fixing the starter one bug at a time reveals the next expected failure;
  5. wrong fixes applied to the reference are each caught with the expected message;
  6. _starter/ still matches the shipped starter.
--write stores the report as <exam>/verification.txt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REFERENCE_BUDGET_S = 5.0


def pytest(root: Path, python: str, *args: str) -> tuple[str, float]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": os.environ.get("HOME", "/tmp")}
    start = time.perf_counter()
    proc = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", *args],
                          cwd=root, capture_output=True, text=True, timeout=600, env=env)
    return proc.stdout + proc.stderr, time.perf_counter() - start


def summary(out: str) -> str:
    lines = [ln for ln in out.strip().splitlines() if re.search(r"\b(passed|failed|skipped|error)", ln)]
    return lines[-1].strip("= ") if lines else out.strip()[-200:]


def count(out: str, word: str) -> int:
    m = re.findall(rf"(\d+) {word}", summary(out))
    return int(m[0]) if m else 0


def failure_lines(out: str) -> str:
    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("E ")]
    return " | ".join(lines[:2]) if lines else summary(out)


def apply_edits(base: Path, edits: list[dict]) -> None:
    for e in edits:
        path = base / e["file"]
        text = path.read_text(encoding="utf-8")
        if e["old"] not in text:
            raise SystemExit(f"edit target not found in {path}: {e['old'][:80]!r}")
        path.write_text(text.replace(e["old"], e["new"], 1), encoding="utf-8")


def outcome(out: str, expect: str) -> tuple[bool, str]:
    if expect == "PASSED":
        return count(out, "passed") == 1 and count(out, "failed") == 0, "passed" if count(out, "passed") else failure_lines(out)
    failed = count(out, "failed") == 1
    return failed and expect in out, failure_lines(out) if failed else summary(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exam", type=Path)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    exam = args.exam.resolve()
    traps = json.loads((exam / "solution" / "traps.json").read_text(encoding="utf-8"))
    package, tests = traps["package"], traps["tests"]
    version = subprocess.run([args.python, "-c", "import sys, pytest; print(sys.version.split()[0], pytest.__version__)"],
                             capture_output=True, text=True).stdout.split()
    report: list[str] = [f"Verified {dt.date.today().isoformat()} on a temporary copy (the pack itself was not run).",
                         f"Python {version[0]} with pytest {version[1]}." if len(version) == 2 else "pytest version unknown", ""]
    problems: list[str] = []

    def check(ok: bool, line: str) -> None:
        report.append(("  " if ok else "  !! ") + line)
        if not ok:
            problems.append(line)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "exam"

        def fresh() -> Path:
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(exam, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
            return work

        n = len(tests)
        out, _ = pytest(fresh(), args.python)
        check(count(out, "skipped") == n and count(out, "failed") == 0, f"locked by default: {summary(out)}")
        out, secs = pytest(fresh(), args.python, "--solution", "--all-parts")
        check(count(out, "passed") == n, f"reference, all parts: {summary(out)}")
        check(secs < REFERENCE_BUDGET_S, f"reference wall time {secs:.2f} s (budget {REFERENCE_BUDGET_S:.0f} s)")
        out, _ = pytest(fresh(), args.python, "--all-parts")
        check(count(out, "failed") == n and "ERROR" not in out, f"starter, all parts: {summary(out)}")

        for layer in traps.get("layers", []):
            report += ["", f"{layer['test']}, starter fixed one bug at a time:"]
            root = fresh()
            for step in layer["steps"]:
                apply_edits(root / package, step["edits"])
                out, _ = pytest(root, args.python, "--all-parts", "-k", layer["test"])
                ok, seen = outcome(out, step["expect"])
                check(ok, f"{step['name']}: {seen}")

        report += ["", "Wrong fixes applied to the reference:"]
        for wrong in traps.get("wrong_fixes", []):
            root = fresh()
            apply_edits(root / "solution" / package, wrong["edits"])
            out, _ = pytest(root, args.python, "--solution", "--all-parts", "-k", wrong["test"])
            ok, seen = outcome(out, wrong["expect"])
            check(ok, f"{wrong['test']}: {wrong['name']}: {seen}")

    report.append("")
    for name in (package, "tests"):
        cmp = filecmp.dircmp(exam / name, exam / "_starter" / name, ignore=["__pycache__"])
        same = not (cmp.left_only or cmp.right_only or cmp.diff_files)
        check(same, f"_starter/{name} matches {name}/")
    report.append("")
    report.append("All checks passed." if not problems else f"{len(problems)} check(s) failed.")
    text = "\n".join(report) + "\n"
    print(text)
    if args.write:
        (exam / "verification.txt").write_text(text, encoding="utf-8")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
