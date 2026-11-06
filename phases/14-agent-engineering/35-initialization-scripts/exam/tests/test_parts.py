import asyncio
import dataclasses
import gc
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import initprobe
import pytest
from initprobe.history import RunHistory
from initprobe.lkg import EXEC, ObjectStore, diff_trees, lkg_drift
from initprobe.paths import pin_paths
from initprobe.plan import ProbeConfigError, run_init
from initprobe.probes import Probe, Result
from initprobe.report import InitReport
from initprobe.runner import LOCK_TTL_S, fingerprint, lock_is_fresh, run_probes, write_lock
from initprobe.service import InitService
from initprobe.tap import stream_tap

MANIFEST = "pyyaml>=6\npytest==8.3.3\nruff==0.7.1\n"
NOW = 1_761_955_200.25
LAYOUT = {"manifest": "requirements.txt", "tests": "tests", "state": ".init/agent_state.json"}


def within(coro, seconds: float = 3.0):
    """Run a coroutine, failing with TimeoutError instead of hanging."""
    return asyncio.run(asyncio.wait_for(coro, seconds))


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return within(drain())


def typed(value):
    """value with every scalar tagged by its type, so 7 and 7.0, or a list and a tuple, stay apart."""
    if dataclasses.is_dataclass(value):
        fields = dataclasses.fields(value)
        return type(value).__name__, {f.name: typed(getattr(value, f.name)) for f in fields}
    if isinstance(value, (list, tuple)):
        return type(value).__name__, [typed(item) for item in value]
    if isinstance(value, dict):
        return {key: typed(item) for key, item in value.items()}
    return type(value).__name__, value


def workbench(env: dict[str, str], paths: dict[str, Path]) -> list[Probe]:
    """The probes init builds at every start: new functions each time, the same names."""

    async def runtime() -> tuple[str, str]:
        return "pass", "python 3.12"

    async def api_key() -> tuple[str, str]:
        await asyncio.sleep(0.02)
        if not env["OPENAI_API_KEY"]:  # a probe with a bug of its own
            return "fail", "missing env vars: ['OPENAI_API_KEY']"
        return "pass", "all of ['OPENAI_API_KEY'] present"

    async def workdir() -> tuple[str, str]:
        await asyncio.sleep(0.05)
        return "pass", "workdir writable"

    async def state() -> tuple[str, str]:
        await asyncio.sleep(0.03)
        return "warn", "no state file yet; first run"

    async def dependencies() -> tuple[str, str]:
        wanted = paths["manifest"].read_text(encoding="utf-8").split()
        return "pass", f"all of {wanted} importable"

    async def test_command() -> tuple[str, str]:
        await asyncio.sleep(0.03)
        return "fail", "pytest not on PATH"

    return [
        Probe("runtime", runtime),
        Probe("env", api_key, budget_s=0.01),
        Probe("workdir", workdir, budget_s=0.02),
        Probe("state_freshness", state, severity="warn", budget_s=0.02),
        Probe("dependencies", dependencies),
        Probe("test_command", test_command, budget_s=0.01),
    ]


@pytest.mark.skip("Part 1")
def test_probe_runner(tmp_path, monkeypatch) -> None:
    """Init finds the repo's files from anywhere in it, keeps every failure a probe finds, times
    probes on a clock that cannot jump and runs them side by side; the prereqs lock is cheap to
    check and trusted only while it should be."""
    repo = tmp_path / "repo"
    started_in = repo / "src" / "app"
    started_in.mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "requirements.txt").write_text(MANIFEST, encoding="utf-8")
    monkeypatch.chdir(started_in)  # the pre-task hook starts init wherever the agent is working
    paths = pin_paths(repo, LAYOUT)
    results = asyncio.run(run_probes(workbench({"PATH": "/usr/local/bin:/usr/bin"}, paths)))
    assert [r.name for r in results] == [
        "runtime", "env", "workdir", "state_freshness", "dependencies", "test_command",
    ], "results come back in the order the probes are listed, not the order they finish"
    assert (results[4].status, results[4].detail) == (
        "pass", f"all of {MANIFEST.split()} importable",
    ), "init finds the repo's files wherever in the repo it starts"
    assert Path.cwd() == started_in, "pinning the paths leaves the working directory where it was"
    relative = pin_paths("../../", LAYOUT)  # the root as git rev-parse --show-cdup prints it
    assert relative == paths == {name: repo / rel for name, rel in LAYOUT.items()}, (
        "pinned paths are absolute and normalized, whether the root comes absolute or relative"
    )
    assert (results[5].status, results[5].detail) == ("fail", "pytest not on PATH"), (
        "a slow fail stays a fail, with the detail the probe gave"
    )
    assert [(r.name, r.status, r.detail) for r in results[:2]] == [
        ("runtime", "pass", "python 3.12"),
        ("env", "fail", "KeyError: 'OPENAI_API_KEY'"),
    ], "a probe that raises fails on its own, and the other probes still run"
    assert 15 <= results[1].duration_ms < 1000, "a probe that raises is timed like any other"
    assert results[0].duration_ms < 15 and results[2].duration_ms >= 45, (
        "each probe is timed on its own, not with the whole run"
    )
    slow = re.fullmatch(r"workdir writable \(slow: (\d+)ms > 20ms\)", results[2].detail)
    assert results[2].status == "warn" and slow and int(slow[1]) == results[2].duration_ms, (
        "a pass slower than its budget_s is a warn that says how slow"
    )
    assert (results[3].status, results[3].detail) == ("warn", "no state file yet; first run"), (
        "a probe's own warn stays as it is"
    )

    real_time, real_time_ns = time.time, time.time_ns
    offset = [0.0]

    async def ntp() -> tuple[str, str]:
        offset[0] += 3600.0  # NTP steps the wall clock an hour forward while this probe runs
        return "pass", "clock synced"

    async def wake() -> tuple[str, str]:
        offset[0] -= 7200.0  # a laptop wakes up with its clock an hour behind
        return "pass", "resumed"

    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: real_time() + offset[0])
        m.setattr(time, "time_ns", lambda: real_time_ns() + int(offset[0] * 1e9))
        stepped = asyncio.run(run_probes([Probe("ntp", ntp), Probe("wake", wake)]))
    assert [(r.status, r.detail) for r in stepped] == [
        ("pass", "clock synced"),
        ("pass", "resumed"),
    ] and all(0 <= r.duration_ms < 1000 for r in stepped), (
        "a wall-clock step does not change how long a probe took"
    )

    lock = tmp_path / "prereqs.lock"
    probes = workbench({"OPENAI_API_KEY": "sk-test"}, paths)
    write_lock(lock, MANIFEST, probes, NOW)
    assert lock_is_fresh(lock, MANIFEST, probes, NOW), "a lock written this second is fresh"
    assert lock_is_fresh(lock, MANIFEST, probes, NOW + LOCK_TTL_S - 1), "a lock is fresh for LOCK_TTL_S"
    assert not lock_is_fresh(lock, MANIFEST, probes, NOW + LOCK_TTL_S), (
        "a lock is stale once it is LOCK_TTL_S old"
    )
    for skew in (0.5, 1.0, 3 * 24 * 3600.0):
        assert not lock_is_fresh(lock, MANIFEST, probes, NOW - skew), (
            "a lock stamped in the future is not trusted"
        )

    later = NOW + 600
    rebuilt = workbench({"OPENAI_API_KEY": "sk-test"}, paths)
    assert lock_is_fresh(lock, MANIFEST, rebuilt, later), (
        "a lock written by an earlier init process still counts"
    )
    script = (
        "import sys\n"
        "from initprobe.probes import Probe\n"
        "from initprobe.runner import fingerprint\n"
        "async def check(): return 'pass', ''\n"
        "print(fingerprint(sys.argv[1], [Probe(name, check) for name in sys.argv[2:]]))\n"
    )
    home = Path(initprobe.__file__).resolve().parents[1]  # the package these tests import
    env = {key: value for key, value in os.environ.items()
           if key not in ("PYTHONHASHSEED", "PYTHONSAFEPATH")}
    other = subprocess.run(
        [sys.executable, "-B", "-c", script, MANIFEST, *[p.name for p in rebuilt]],
        capture_output=True, text=True, cwd=home, env=env, timeout=60,
    )
    assert other.stdout.strip() == fingerprint(MANIFEST, rebuilt), (
        "another init process computes the same fingerprint"
    )
    assert not lock_is_fresh(lock, MANIFEST + "httpx==0.27.2\n", rebuilt, later), (
        "editing the manifest makes the lock stale"
    )
    node = Probe("node", rebuilt[0].check)
    assert not lock_is_fresh(lock, MANIFEST, rebuilt + [node], later), (
        "a lock covers only the probes it was written for"
    )
    assert lock_is_fresh(lock, MANIFEST, rebuilt[::-1], later), (
        "the order the probes are listed in does not matter"
    )
    renamed = [Probe("python", rebuilt[0].check)] + rebuilt[1:]
    for changed in (rebuilt[1:], renamed):
        assert not lock_is_fresh(lock, MANIFEST, changed, later), (
            "a lock covers only the probes it was written for"
        )

    async def importable() -> tuple[str, str]:
        await asyncio.sleep(0.01)  # find_spec on a cold site-packages
        return "pass", "importable"

    monorepo = [Probe(f"dep:pkg{i:04}", importable) for i in range(5000)]  # one per locked package
    gc.collect()  # collect earlier garbage now, not in the middle of the timed run
    start = time.perf_counter()
    write_lock(lock, MANIFEST, monorepo, NOW)
    fresh = lock_is_fresh(lock, MANIFEST, monorepo, NOW + 1)
    elapsed = time.perf_counter() - start
    assert fresh, "a lock is fresh for the probe set it was written for"
    assert elapsed < 0.05, "writing and checking the lock stay fast with thousands of probes"

    deps = [Probe(f"dep:pkg{i:03}", importable) for i in range(200)]
    gc.collect()  # collect earlier garbage now, not in the middle of the timed run
    start = time.perf_counter()
    found = asyncio.run(run_probes(deps))
    elapsed = time.perf_counter() - start
    assert [(r.name, r.status) for r in found] == [(p.name, "pass") for p in deps]
    assert elapsed < 0.2, "probes run side by side: init takes about as long as its slowest probe"


READY = InitReport(
    1761955200.1234567,
    "9f2c4e1a7b3d5c60",
    [
        Result("runtime", "pass", "python 3.12", 0),
        Result("dependencies", "pass", 'all of ["pyyaml>=6", "pytest==8.3.3"] importable', 1003),
        Result("test_command", "warn", "pytest resolvable on PATH (slow: 3121ms > 3000ms)", 3121),
        Result("env", "pass", "all of ['OPENAI_API_KEY'] present", 2002),
        Result("state_freshness", "warn", "no state file yet — first run", 7),
    ],
    [],
    ["test_command", "state_freshness"],
    0,
)
BLOCKED = InitReport(
    1761958800.000001,
    "9f2c4e1a7b3d5c60",
    [
        Result("runtime", "pass", "python 3.12", 1),
        Result(
            "dependencies",
            "fail",
            'missing: [\'pyyaml\']\n  hint: pip install "pyyaml>=6"\tC:\\new\\venv\\Scripts',
            29,
        ),
        Result("test_command", "skip", "needs dependencies", 0),
        Result("env", "pass", "all of ['OPENAI_API_KEY'] present", 3),
        Result("state_freshness", "pass", "state is 412s old", 0),
    ],
    ["dependencies", "test_command"],
    [],
    1,
)
RERUN = dataclasses.replace(READY, timestamp=1761962400.5, fingerprint="0b7e93d2c41a8f65")
AGAIN = dataclasses.replace(BLOCKED, timestamp=1761966000.75, fingerprint="0b7e93d2c41a8f65")


@pytest.mark.skip("Part 2")
def test_run_history(tmp_path) -> None:
    """Every init run is appended as one JSON line, and comes back exactly."""
    path = tmp_path / "init_history.jsonl"
    assert RunHistory(path).runs() == [] and RunHistory(path).last_ready() is None, (
        "a history that was never written holds no runs"
    )
    history = RunHistory(path)
    history.append(READY)
    reader = RunHistory(path)  # a human reading the history while init still runs
    assert typed(reader.runs()) == typed([READY]), (
        "a run is on disk as soon as append returns, and comes back exactly"
    )
    history.append(BLOCKED)
    assert typed(reader.runs()) == typed([READY, BLOCKED]), "runs() reads what is on disk now"
    history.append(RERUN)
    history.close()
    lines = path.read_text(encoding="utf-8").split("\n")
    assert lines.pop() == "" and len(lines) == 3, "one line per run, each ending in a newline"
    assert all(isinstance(json.loads(line), dict) for line in lines), "each line is one JSON object"

    reopened = RunHistory(path)
    reopened.append(AGAIN)
    assert typed(reopened.runs()) == typed([READY, BLOCKED, RERUN, AGAIN]), (
        "a reopened history keeps every run, oldest first"
    )
    assert reopened.last_ready() == RERUN, "last_ready is the most recent run with exit_code 0"
    backdated = dataclasses.replace(READY, timestamp=1761940800.0)  # run after the clock was set back
    reopened.append(backdated)
    assert typed(RunHistory(path).runs()[-2:]) == typed([AGAIN, backdated]), (
        "runs come back in the order they were appended, whatever their timestamps say"
    )
    assert RunHistory(path).last_ready() == backdated, "the most recent run is the last one appended"

    before = path.read_bytes()

    def refused(results: list[Result]) -> bool:
        try:
            reopened.append(dataclasses.replace(AGAIN, results=results))
        except ValueError:
            return True
        return False

    fine = Result("runtime", "pass", "python 3.12", 2)
    for bad, why in (
        (Result("env", "pass", "all present", -3599990), "a negative duration (a clock stepped back)"),
        (Result("env", "pass", "all present", 2.5), "a duration that is not whole milliseconds"),
        (Result("env", "pass", "all present", 0.002), "a duration in seconds"),
        (Result("env", "ok", "all present", 3), "a status that is not pass, warn, fail or skip"),
    ):
        assert refused([fine, bad]), f"append refuses a run with {why}"
    assert path.read_bytes() == before, "a refused run leaves the history as it was"

    with path.open("a", encoding="utf-8") as f:
        f.write('{"timestamp": 1761969600.0, "fingerprint": "0b7e93d2c41a8f65"}\n')
    with pytest.raises(ValueError, match="line 6"):
        RunHistory(path).runs()
    edited = tmp_path / "edited.jsonl"
    edited.write_text(lines[0] + "\n}{\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        RunHistory(edited).runs()


FOUND = {
    "test_command": ("pass", "pytest resolvable on PATH"),
    "runtime": ("pass", "python 3.12"),
    "dependencies": ("fail", 'missing: ["pyyaml>=6"]'),
    "env": ("pass", "all of ['OPENAI_API_KEY'] present"),
    "state_freshness": ("warn", "no state file yet — first run"),
    "git": ("fail", "git not on PATH\r\nsearched:\tC:\\Program Files\\Git\\cmd;C:\\new\\bin"),
    "lkg_diff": ("pass", "3 files changed since 85fbd61 (budget 50)"),
    "smoke": ("pass", "12 tests collected"),
    "lint": ("pass", "ruff resolvable on PATH"),
    "coverage": ("fail", "coverage 71% < 80% (see #142)"),
}
FIXED = dict(FOUND, dependencies=("pass", "all of ['pyyaml'] importable"), git=("pass", "git 2.47.1"))


class Bench:
    """A scripted workbench: what each probe finds, and how long it takes to look."""

    def __init__(self, found: dict[str, tuple[str, str]], delay: dict[str, float] | None = None):
        self.found = dict(found)
        self.delay = dict(delay or {})
        self.gates: dict[str, asyncio.Event] = {}
        self.log: list[tuple[str, str]] = []

    def probe(self, name: str, severity: str = "block", needs: tuple[str, ...] = (),
              budget_s: float = 3.0) -> Probe:
        async def check() -> tuple[str, str]:
            self.log.append(("start", name))
            await asyncio.sleep(self.delay.get(name, 0.0))
            if name in self.gates:
                await self.gates[name].wait()
            self.log.append(("end", name))
            return self.found[name]

        return Probe(name, check, severity, needs, budget_s)

    def ran(self) -> list[str]:
        return sorted(name for event, name in self.log if event == "start")


def lesson_probes(bench: Bench, tests_budget_s: float = 3.0) -> list[Probe]:
    """The lesson's probe table, with the needs between them.

    test_command is listed before the probe it needs.
    """
    return [
        bench.probe("test_command", needs=("dependencies",), budget_s=tests_budget_s),
        bench.probe("runtime"),
        bench.probe("git", severity="warn"),
        bench.probe("dependencies", needs=("runtime",)),
        bench.probe("env"),
        bench.probe("state_freshness", severity="warn"),
        bench.probe("lkg_diff", needs=("git",)),
        bench.probe("smoke", severity="warn", needs=("test_command", "lkg_diff", "lint")),
        bench.probe("lint", severity="info", needs=("dependencies",)),
        bench.probe("coverage", severity="info"),
    ]


def outcome(report: InitReport) -> list[tuple[str, str, str]]:
    return [(r.name, r.status, r.detail) for r in report.results]


@pytest.mark.skip("Part 3")
def test_probe_plan(tmp_path) -> None:
    """Probes run in dependency order under their severities, and one workbench gives one report."""
    bench = Bench(FOUND, delay={"runtime": 0.0, "dependencies": 0.03, "git": 0.0, "env": 0.01,
                                "state_freshness": 0.02, "coverage": 0.04})
    probes = lesson_probes(bench)
    report = within(run_init(probes, MANIFEST, NOW))
    assert [r.name for r in report.results] == [p.name for p in probes], (
        "results follow the order the probes are listed"
    )
    assert outcome(report) == [
        ("test_command", "skip", "needs dependencies"),
        ("runtime", "pass", "python 3.12"),
        ("git", "fail", FOUND["git"][1]),
        ("dependencies", "fail", 'missing: ["pyyaml>=6"]'),
        ("env", "pass", "all of ['OPENAI_API_KEY'] present"),
        ("state_freshness", "warn", "no state file yet — first run"),
        ("lkg_diff", "skip", "needs git"),
        ("smoke", "skip", "needs git, dependencies"),
        ("lint", "skip", "needs dependencies"),
        ("coverage", "fail", "coverage 71% < 80% (see #142)"),
    ], (
        "a probe whose needs did not pass is skipped, naming the failed probes behind it, "
        "each once, in list order"
    )
    assert bench.ran() == ["coverage", "dependencies", "env", "git", "runtime", "state_freshness"], (
        "a skipped probe never runs"
    )
    assert all(r.duration_ms == 0 for r in report.results if r.status == "skip"), (
        "a skipped probe takes no time"
    )
    assert (report.blocking, report.warnings, report.exit_code) == (
        ["test_command", "dependencies", "lkg_diff"],
        ["git", "state_freshness", "smoke"],
        1,
    ), (
        "block probes that failed or were skipped block the launch; "
        "the others that did not pass are warnings, except info probes"
    )
    assert (report.timestamp, report.fingerprint) == (NOW, fingerprint(MANIFEST, probes)), (
        "the report is stamped with now and the lock fingerprint"
    )

    again = within(run_init(lesson_probes(Bench(FOUND, delay={
        "runtime": 0.03, "dependencies": 0.0, "git": 0.05, "env": 0.0, "state_freshness": 0.04,
        "coverage": 0.0,
    })), MANIFEST, NOW + 60))
    assert again.to_json().replace(json.dumps(NOW + 60), json.dumps(NOW)) == report.to_json(), (
        "two runs of one workbench differ only in the timestamp, however their probes finish"
    )

    no_git = Bench(dict(FOUND, dependencies=FIXED["dependencies"], lint=("fail", "ruff not on PATH")))
    report = within(run_init(lesson_probes(no_git), MANIFEST, NOW))
    assert [r.status for r in report.results] == [
        "pass", "pass", "fail", "pass", "pass", "warn", "skip", "skip", "fail", "fail",
    ] and report.results[7].detail == "needs git, lint", (
        "a need that failed stops the probes that need it, whatever its severity"
    )
    assert (report.blocking, report.warnings, report.exit_code) == (
        ["lkg_diff"], ["git", "state_freshness", "smoke"], 1,
    ), "a block probe that could not run blocks the launch, even when what failed is only a warn"

    slow = Bench(FIXED, delay={"test_command": 0.06})
    probes = lesson_probes(slow, tests_budget_s=0.02)

    async def eager() -> tuple[bool, InitReport]:
        slow.gates["env"] = asyncio.Event()
        run = asyncio.create_task(run_init(probes, MANIFEST, NOW))
        wanted = {("start", "test_command"), ("start", "coverage")}
        for _ in range(200):
            if wanted <= set(slow.log):
                break
            await asyncio.sleep(0.005)
        started = wanted <= set(slow.log)
        slow.gates["env"].set()
        return started, await run

    started, report = within(eager())
    assert started, (
        "probes run side by side, and a probe starts as soon as what it needs has finished"
    )
    warned = re.fullmatch(r"pytest resolvable on PATH \(slow: \d+ms > 20ms\)", report.results[0].detail)
    assert report.results[0].status == "warn" and warned, "a slow pass is a warn"
    smoke = report.results[7]
    assert (smoke.name, smoke.status, smoke.detail) == ("smoke", "pass", "12 tests collected"), (
        "a probe that warned still counts as done for the probes that need it"
    )
    assert (report.blocking, report.warnings, report.exit_code) == (
        [], ["test_command", "state_freshness"], 0,
    ), "warnings never block the launch"

    def refused(broken: list[Probe]) -> bool:
        bench.log.clear()
        try:
            within(run_init(broken, MANIFEST, NOW), 1.0)
        except ProbeConfigError:
            return bench.log == []
        except asyncio.TimeoutError:
            return False
        return False

    assert refused([bench.probe("lkg_diff", needs=("git",)), bench.probe("runtime")]), (
        "a need that is not a listed probe is refused before anything runs"
    )
    assert refused([
        bench.probe("pytest_collect", needs=("fixtures",)),
        bench.probe("fixtures", needs=("db",)),
        bench.probe("db", needs=("pytest_collect",)),
        bench.probe("runtime"),
    ]), "needs that loop back are refused before anything runs"
    assert refused([bench.probe("runtime", needs=("runtime",))]), "a probe that needs itself is refused"
    assert refused([bench.probe("env"), bench.probe("env", severity="warn")]), (
        "two probes with one name are refused"
    )
    assert refused([bench.probe("runtime", severity="critical")]), (
        "a severity that is not block, warn or info is refused, not taken for a warning"
    )

    clock = [NOW]
    bench = Bench(FIXED)
    workdir = tmp_path / "workdir"
    service = InitService(lesson_probes(bench), MANIFEST, workdir, clock=lambda: clock[0])
    lock = workdir / "prereqs.lock"
    first = service.run()
    assert first.exit_code == 0 and lock.exists(), "a ready run writes the lock"
    assert (workdir / "init_report.json").read_text(encoding="utf-8") == first.to_json()
    bench.log.clear()
    clock[0] += 3600
    assert service.run() is None and bench.log == [], "a fresh lock stands in for the probes"
    bench.found["env"] = ("fail", "missing env vars: ['OPENAI_API_KEY']")
    refusal = service.run(use_lock=False)
    assert refusal.blocking == ["env"] and not lock.exists(), "a refused run takes the lock away"
    clock[0] += 60
    assert service.run().exit_code == 1, "so the next plain run probes again"
    history = RunHistory(workdir / "init_history.jsonl")
    assert [run.exit_code for run in history.runs()] == [0, 1, 1], "every run that probed is logged"
    assert history.last_ready() == first
    broken = InitService([bench.probe("lkg_diff", needs=("git",))], MANIFEST, tmp_path / "broken")
    assert broken.hook() == 2, "a broken probe set makes the hook exit 2"


TAP_TEST = re.compile(r"(ok|not ok) (\d+) - (\w+) # (?:SKIP (.+)|(pass|warn|fail) (\d+)ms (.*))")


def unescape(text: str) -> str:
    """Undo the escaping stream_tap's docstring describes, and nothing else."""
    assert re.fullmatch(r"(?:[^\\\r\n]|\\[\\nr])*", text), (
        "a detail escapes backslash, line feed and carriage return, and nothing else"
    )
    return re.sub(r"\\(.)", lambda m: {"\\": "\\", "n": "\n", "r": "\r"}[m[1]], text)


@pytest.mark.skip("Part 4")
def test_tap_stream() -> None:
    """Each probe gets one TAP line as soon as it settles, under the number it got up front and
    marked ok or not ok by its status alone; a broken probe set is a single Bail out! line."""
    bench = Bench(FOUND, delay={"state_freshness": 0.01, "dependencies": 0.02, "git": 0.03})
    probes = lesson_probes(bench)

    async def take(agen, n: int) -> list[str]:
        lines = []
        for _ in range(n):
            try:
                lines.append(await asyncio.wait_for(agen.__anext__(), 1.0))
            except (asyncio.TimeoutError, StopAsyncIteration):
                break
        return lines

    async def read() -> tuple[list[str], list[str], list[str]]:
        bench.gates = {"env": asyncio.Event(), "coverage": asyncio.Event()}
        agen = stream_tap(probes)
        early = await take(agen, 8)
        bench.gates["coverage"].set()
        middle = await take(agen, 1)
        bench.gates["env"].set()
        return early, middle, await take(agen, 10)

    early, middle, rest = within(read(), 5.0)
    assert len(early) == 8, (
        "a line goes out as soon as its probe settles, skips included, while other probes still run"
    )
    items = early + middle + rest
    assert all(item.endswith("\n") and item.count("\n") == 1 and "\r" not in item for item in items), (
        "every item is one line ending in a newline"
    )
    lines = [item[:-1] for item in items]
    assert lines[-2:] == ["1..10", "# refuse to launch: test_command, dependencies, lkg_diff"], (
        "the plan line and the verdict come after the last probe"
    )
    tests = [TAP_TEST.fullmatch(line) for line in lines[:-2]]
    assert len(tests) == 10 and all(tests), "each probe gets one line: ok|not ok N - name # ..."
    order = [m[3] for m in tests]
    assert (order[0], order[-2:]) == ("runtime", ["coverage", "env"]), (
        "lines come in the order probes settle"
    )
    assert {m[3]: int(m[2]) for m in tests} == {p.name: n for n, p in enumerate(probes, 1)}, (
        "a probe's number is its place in the list, whatever order the lines come in"
    )
    seen = {
        m[3]: (m[1], "SKIP", unescape(m[4])) if m[4] is not None else (m[1], m[5], unescape(m[7]))
        for m in tests
    }
    assert seen == {
        "test_command": ("ok", "SKIP", "needs dependencies"),
        "runtime": ("ok", "pass", "python 3.12"),
        "git": ("not ok", "fail", FOUND["git"][1]),
        "dependencies": ("not ok", "fail", 'missing: ["pyyaml>=6"]'),
        "env": ("ok", "pass", "all of ['OPENAI_API_KEY'] present"),
        "state_freshness": ("ok", "warn", "no state file yet — first run"),
        "lkg_diff": ("ok", "SKIP", "needs git"),
        "smoke": ("ok", "SKIP", "needs git, dependencies"),
        "lint": ("ok", "SKIP", "needs dependencies"),
        "coverage": ("not ok", "fail", "coverage 71% < 80% (see #142)"),
    }, (
        "fail is not ok, pass and warn are ok, a skip is ok # SKIP with its reason; "
        "details come back exactly"
    )

    bench.log.clear()
    bail = collect(stream_tap([bench.probe("lkg_diff", needs=("git",)), bench.probe("runtime")]))
    assert len(bail) == 1 and bail[0].startswith("Bail out! ") and "git" in bail[0], (
        "a broken probe set is a single Bail out! line"
    )
    assert bail[0].endswith("\n"), "every item is one line ending in a newline"
    assert bench.log == [], "a broken probe set runs nothing"

    slow = Bench(FIXED, delay={"test_command": 0.06})
    out = "".join(collect(stream_tap(lesson_probes(slow, tests_budget_s=0.02))))
    assert "\nnot ok 10 - coverage # fail " in out and out.endswith("1..10\n# ready\n"), (
        "a failed info probe is reported, and a run with nothing blocking ends with # ready"
    )
    warned = [m for m in map(TAP_TEST.fullmatch, out.split("\n")) if m and m[3] == "test_command"]
    assert [(m[1], m[2], m[5]) for m in warned] == [("ok", "1", "warn")], (
        "a block probe that warns is still ok"
    )


@pytest.mark.skip("Part 5")
def test_lkg_diff() -> None:
    """HEAD is compared with the last-known-good tree file by file, reading only what changed."""
    store = ObjectStore()
    lib = {f"mod{i:02}.py": f"VALUE = {i}\n".encode() for i in range(40)}
    lkg_tree = store.build({
        "run.sh": b"#!/bin/sh\npytest -q\n",
        "README.md": b"# demo\n",
        "src": {"app": {"main.py": b"import lib\n", "util.py": b"def slug(s): ...\n"}, "lib": lib},
        "docs": {"guide.md": b"# Guide\n", "api": {"index.md": b"# API\n"}},
        "a": {"x.py": b"x = 1\n"},
        "a.txt": b"one\n",
        "a-b.txt": b"one\n",
        "notes": b"todo: pin a new LKG\n",
        "assets": {},
        "tools": {"lint.py": b"import ruff\n"},
        ".init": {"last_known_good.json": b'{"commit": "85fbd61"}\n'},
    })
    moved = dict(lib)
    mod07 = moved.pop("mod07.py")
    head_tree = store.build({
        "run.sh": (b"#!/bin/sh\npytest -q\n", EXEC),
        "README.md": b"# demo v2\n",
        "src": {
            "app": {"main.py": b"import lib\n", "helpers.py": b"def slug(s): ...\n"},
            "lib": moved,
            "core": {"mod07.py": mod07},
        },
        "docs": b"moved to the wiki\n",
        "a": {"x.py": b"x = 2\n"},
        "a.txt": b"two\n",
        "a-b.txt": b"two\n",
        "notes": {"a.md": b"# A\n"},
        "notes.md": b"# B\n",
        "cache": {},
        "build": {"tmp": {}},
        "tools": {"empty": {}},
        ".init": {"last_known_good.json": b'{"commit": "2c9e4d0"}\n'},
        ".initrc": b"export AGENT_MODE=1\n",
    })
    changes = diff_trees(store, lkg_tree, head_tree)
    paths = [path for _, path in changes]
    assert paths == sorted(paths), "changes are sorted by path"
    status = {path: kind for kind, path in changes}
    directories = {"assets", "cache", "build", "build/tmp", "tools", "tools/empty", "src", "src/core"}
    assert not directories & set(status), "only files are listed; a directory, empty or not, never is"
    assert status.get("run.sh") == "M", "a file whose mode changed is modified"
    assert (status.get("src/lib/mod07.py"), status.get("src/core/mod07.py")) == ("D", "A"), (
        "a file that moved is deleted at its old path and added at its new one"
    )
    swapped = ("docs", "docs/guide.md", "docs/api/index.md", "notes", "notes/a.md")
    assert [status.get(path) for path in swapped] == ["A", "D", "D", "D", "A"], (
        "when a directory and a file swap places, every file under the directory goes or comes"
    )
    assert changes == [
        ("M", ".init/last_known_good.json"),
        ("A", ".initrc"),
        ("M", "README.md"),
        ("M", "a-b.txt"),
        ("M", "a.txt"),
        ("M", "a/x.py"),
        ("A", "docs"),
        ("D", "docs/api/index.md"),
        ("D", "docs/guide.md"),
        ("D", "notes"),
        ("A", "notes.md"),
        ("A", "notes/a.md"),
        ("M", "run.sh"),
        ("A", "src/app/helpers.py"),
        ("D", "src/app/util.py"),
        ("A", "src/core/mod07.py"),
        ("D", "src/lib/mod07.py"),
        ("D", "tools/lint.py"),
    ], "every changed file once, as A, D or M, sorted by path"

    big = ObjectStore()
    services = {
        f"svc{i:02}": {
            "README.md": f"service {i}\n".encode(),
            "handlers": {f"h{j:02}.py": f"# {i}.{j}\n".encode() for j in range(12)},
        }
        for i in range(30)
    }
    before = big.build({"README.md": b"# mono\n", "services": services})
    patched = {name: dict(svc, handlers=dict(svc["handlers"])) for name, svc in services.items()}
    patched["svc07"]["handlers"]["h03.py"] = b"# patched\n"
    after = big.build({"README.md": b"# mono\n", "services": patched})
    big.reads = 0
    assert diff_trees(big, before, after) == [("M", "services/svc07/handlers/h03.py")]
    assert big.reads <= 8, "only the trees on the way to a change are read, and blobs never are"
    big.reads = 0
    assert diff_trees(big, before, before) == [] and big.reads == 0, (
        "two trees with the same oid are not read at all"
    )

    lkg = store.commit(lkg_tree, "release 1.4")
    head = store.commit(head_tree, "move docs to the wiki")
    short = lkg[:7]
    status, detail = lkg_drift(store, lkg, head)
    assert detail.startswith("17 files changed"), (
        "init's own files under .init/ do not count toward the budget; every other file does"
    )
    assert (status, detail) == ("pass", f"17 files changed since {short} (budget 50)"), (
        "the detail names the LKG commit and the budget, 50 files by default"
    )
    assert lkg_drift(store, lkg, head, budget=17) == (
        "pass", f"17 files changed since {short} (budget 17)",
    ), "a diff of exactly the budget is still a pass"
    assert lkg_drift(store, lkg, head, budget=16) == (
        "fail", f"17 files changed since {short} (budget 16)",
    ), "more files than the budget is a fail"
    assert lkg_drift(store, None, head) == (
        "warn", "no last-known-good commit; pin one after the first successful merge",
    ), "no LKG pinned yet is a warn, not a reason to refuse"
    assert lkg_drift(store, "0f" * 20, head) == ("fail", "last-known-good commit 0f0f0f0 not found"), (
        "an LKG commit that is not in the store needs a human to pin a new one"
    )
