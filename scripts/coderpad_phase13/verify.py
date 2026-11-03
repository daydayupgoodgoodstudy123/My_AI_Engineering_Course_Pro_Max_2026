"""Rebuild into a temporary directory and execute every reference and TODO baseline.

Use --target PHASE to verify already generated packs and write verification logs.
Default verification never modifies a learner's working files.
All subprocesses have timeouts; no external service is used.
"""
import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from build import build, load_specs


def invoke(pack, *flags):
    with tempfile.TemporaryDirectory(prefix="coderpad-score-") as tmp:
        report_path = Path(tmp) / "score.json"
        command = [sys.executable, "run_tests.py", *flags, "-q", "--json-report", str(report_path)]
        result = subprocess.run(command, cwd=pack, capture_output=True, text=True, timeout=20)
        score = json.loads(report_path.read_text()) if report_path.exists() else None
        return result, score


def validate_structure(pack, spec):
    for p in pack.rglob("*.py"):
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    for p in pack.rglob("*.md"):
        in_fence = False
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                if not in_fence and not line[3:].strip():
                    raise AssertionError(f"Untagged code fence: {p}")
                in_fence = not in_fence
        assert not in_fence, f"Unclosed code fence: {p}"
    result = subprocess.run([sys.executable, "run_tests.py", "--list"], cwd=pack, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    ids = [line for line in result.stdout.splitlines() if line.startswith("test_")]
    assert sum(".CoreTests." in x for x in ids) >= 5, pack
    assert sum(".BonusTests." in x for x in ids) >= 1, pack
    tree = ast.parse((pack / "starter/main.py").read_text())
    todos = [n for n in ast.walk(tree) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "NotImplementedError"]
    assert len(todos) == len(spec["stubs"]), pack
    return len(ids)


def verify(target, write_logs):
    specs = load_specs()
    totals = {"packs": 0, "core": 0, "bonus": 0, "starter_passed": 0}
    failures = []
    timestamp = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    for lesson, spec in specs:
        pack = target / lesson.name / "coderpad"
        try:
            collected = validate_structure(pack, spec)
            before = hashlib.sha256((pack / "starter/main.py").read_bytes()).hexdigest()
            reference, score = invoke(pack, "--solution")
            if reference.returncode != 0 or score is None or not score["success"]:
                raise AssertionError("Reference failed:\n" + reference.stdout + reference.stderr)
            assert sum(v["total"] for v in score["counts"].values()) == collected
            baseline, start_score = invoke(pack)
            if baseline.returncode != 1 or start_score is None or start_score["success"]:
                raise AssertionError("Starter must produce normal failing test results:\n" + baseline.stdout + baseline.stderr)
            after = hashlib.sha256((pack / "starter/main.py").read_bytes()).hexdigest()
            assert before == after, "Reference execution changed learner code"
            core = score["counts"]["core"]["total"]
            bonus = score["counts"]["bonus"]["total"]
            totals["packs"] += 1; totals["core"] += core; totals["bonus"] += bonus
            totals["starter_passed"] += sum(x["passed"] for x in start_score["counts"].values())
            if write_logs:
                source_hash = hashlib.sha256((pack / "solution/main.py").read_bytes()).hexdigest()
                intro = f"Verified: {timestamp}\nPython: {sys.version.split()[0]}\nSolution SHA256: {source_hash}\n"
                (pack / "verification.txt").write_text(intro + "Command: python3 run_tests.py --solution -q\n" + reference.stdout + reference.stderr, encoding="utf-8")
                (pack / "starter_baseline.txt").write_text(intro + "Command: python3 run_tests.py -q\nExpected exit code: 1 (unfinished TODOs)\n" + json.dumps(start_score, indent=2) + "\n\n" + baseline.stdout + baseline.stderr, encoding="utf-8")
            print(f"{lesson.name[:2]} reference {core}+{bonus} passed; starter {sum(x['passed'] for x in start_score['counts'].values())}/{collected}", flush=True)
        except Exception as exc:
            failures.append((lesson.name, str(exc)))
            print(f"FAIL {lesson.name}: {exc}", file=sys.stderr, flush=True)
    print(json.dumps({"totals": totals, "failures": [n for n, _ in failures]}, indent=2))
    if failures:
        return 1
    if write_logs:
        (target / "CODERPAD_VALIDATION.json").write_text(json.dumps({"verified_at": timestamp, "python": sys.version.split()[0], "totals": totals, "source_files_unchanged_by_tests": True}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, help="Verify built packs and write logs (fresh starter only)")
    args = parser.parse_args()
    if args.target:
        if not build(args.target.resolve(), check=True):
            raise SystemExit("Refusing baseline logging: generated files differ; use temporary verification instead.")
        raise SystemExit(verify(args.target.resolve(), True))
    with tempfile.TemporaryDirectory(prefix="phase13-coderpad-") as directory:
        output = Path(directory)
        if not build(output):
            raise SystemExit(1)
        raise SystemExit(verify(output, False))
