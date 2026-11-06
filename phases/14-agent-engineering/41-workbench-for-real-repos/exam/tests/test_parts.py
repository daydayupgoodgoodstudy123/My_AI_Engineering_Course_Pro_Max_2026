import asyncio
import csv
import io
import time
from dataclasses import fields, replace

import pytest
from realrepo.artifacts import FeedbackRecord
from realrepo.compare import compare
from realrepo.impact import affected_tests, proves_change
from realrepo.outcomes import Outcome, measure
from realrepo.sample import HAPPY, SHORT, SIGNUP, TEST_APP_PY, run_prompt_only, run_workbench
from realrepo.store import OutcomeStore
from realrepo.timeline import milestones

PYTEST = ("python3", "-m", "pytest")
PO, WB = "prompt-only", "workbench-guided"


def record(command, exit_code, results, **extra) -> FeedbackRecord:
    return FeedbackRecord(tuple(command), exit_code, results, **extra)


def exact(a, b) -> bool:
    """Equal, and of the same types all the way down: True is not 1, a tuple is not a list."""
    if type(a) is not type(b):
        return False
    if isinstance(a, Outcome):
        return all(exact(getattr(a, f.name), getattr(b, f.name)) for f in fields(Outcome))
    if isinstance(a, list):
        return len(a) == len(b) and all(map(exact, a, b))
    return a == b


@pytest.mark.skip("Part 1")
def test_measure_outcomes() -> None:
    """The five outcomes come from what each run left behind, as in the lesson's table."""
    workbench, prompt_only = run_workbench(), run_prompt_only()
    assert measure(workbench, SIGNUP) == Outcome(True, True, [], "full packet", 9), (
        "the lesson's workbench row"
    )
    assert measure(prompt_only, SIGNUP).tests_actually_run is False, (
        "an agent saying the tests passed is not evidence that they ran"
    )
    assert measure(prompt_only, SIGNUP) == Outcome(
        False, False, ["sample_app/README.md", "sample_app/scripts/release.sh"], "missing", 3
    ), "the lesson's prompt-only row"

    happy_only = replace(prompt_only, feedback=(record([*PYTEST, "-k", "happy"], 0, {HAPPY: "passed"}),))
    outcome = measure(happy_only, SIGNUP)
    assert (outcome.tests_actually_run, outcome.acceptance_met) == (True, False), (
        "a test ran, but not the one that proves the goal"
    )

    skipped_only = replace(prompt_only, feedback=(record([*PYTEST, SHORT], 0, {SHORT: "skipped"}),))
    outcome = measure(skipped_only, SIGNUP)
    assert (outcome.tests_actually_run, outcome.acceptance_met) == (False, False), (
        "pytest exits 0 when it skips every test, but no test ran"
    )

    killed = record([*PYTEST, "sample_app/test_app.py"], None, {HAPPY: "passed", SHORT: "passed"},
                    error="timed out after 120 s")
    outcome = measure(replace(workbench, feedback=workbench.feedback[:1] + (killed,)), SIGNUP)
    assert (outcome.tests_actually_run, outcome.acceptance_met) == (False, False), (
        "a command that never exited proves nothing"
    )

    status_report = {name: value for name, value in workbench.handoff.items() if name != "next_action"}
    assert measure(replace(workbench, handoff=status_report), SIGNUP).handoff_quality == "missing", (
        "without a next_action the packet is a status report, not a handoff"
    )
    no_step = {**workbench.handoff, "next_action": "  "}
    assert measure(replace(workbench, handoff=no_step), SIGNUP).handoff_quality == "missing", (
        "a blank next_action is no next action"
    )
    blank = {**workbench.handoff, "verdict_pointer": "  "}
    assert measure(replace(workbench, handoff=blank), SIGNUP).handoff_quality == "partial", (
        "a handoff with a blank field is partial"
    )

    modules = [f"services/svc{m:02d}/tests/test_api.py" for m in range(20)]
    suite = {f"{mod}::test_case_{t:02d}[{p}]": "passed" for mod in modules for t in range(25) for p in "abcd"}
    full_run = replace(workbench, feedback=(record([*PYTEST, "services"], 0, suite),))
    contract = replace(SIGNUP, acceptance=tuple(f"{mod}::test_case_{t:02d}" for mod in modules for t in range(10)))
    start = time.perf_counter()
    met = measure(full_run, contract).acceptance_met
    assert time.perf_counter() - start < 0.15, "acceptance should be fast on a full suite run"
    assert met is True, "a test function covers its parametrized cases"

    results = {
        HAPPY: "passed",
        SHORT: "skipped",
        "sample_app/test_app.py::TestPasswords::test_too_short[1234567]": "passed",
        "sample_app/test_app.py::TestPasswords::test_too_short[]": "passed",
        "sample_app/test_app.py::TestPasswords::test_long_enough": "failed",
        "sample_app/test_email.py::test_lowercases": "passed",
    }
    run = replace(workbench, feedback=(record(PYTEST, 1, results),))
    assert measure(run, SIGNUP).tests_actually_run is True, "a command that exits 1 still ran its tests"

    def met_by(selector: str) -> bool:
        return measure(run, replace(SIGNUP, acceptance=(selector,))).acceptance_met

    assert met_by("sample_app/test_app.py::TestPasswords::test_too_short") is True, (
        "a test function covers its parametrized cases"
    )
    assert met_by("sample_app/test_email.py") is True, "a test module covers the tests in it"
    assert met_by("sample_app/test_app.py::test_signup") is False, (
        "test_signup does not cover test_signup_happy_path"
    )
    assert met_by("sample_app") is False, "every test a selector covers must pass"
    assert met_by(SHORT) is False, "a skipped test did not run"


@pytest.mark.skip("Part 2")
def test_outcome_store(tmp_path) -> None:
    """Every repetition's outcomes survive a reopen exactly, in the order they were recorded."""
    path = str(tmp_path / "outcomes.sqlite3")
    wb = Outcome(True, True, [], "full packet", 10)
    po = Outcome(False, False, ["sample_app/scripts/release.sh", "docs/notes, v2.md", "docs/a;b.md"], "missing", 0)
    second = replace(po, files_outside_scope=["sample_app/README.md"], reviewer_total=4)
    store = OutcomeStore(path)
    store.record("r2", WB, wb)
    store.record("r2", PO, po)
    store.record("r10", PO, second)
    assert exact(store.get("r2", WB), wb), "an outcome reads back as it went in: bools, an int, an empty list"
    store.close()

    reopened = OutcomeStore(path)
    assert exact(reopened.get("r2", PO), po), (
        "a reopened store reads back the same outcome, files in the order given"
    )
    reopened.record("r1", WB, replace(wb, handoff_quality="partial", reviewer_total=7))
    assert reopened.runs() == ["r2", "r10", "r1"], "runs in the order they were first recorded"
    stored = reopened.outcomes()
    assert [(run, pipeline) for run, pipeline, _ in stored] == [
        ("r2", WB),
        ("r2", PO),
        ("r10", PO),
        ("r1", WB),
    ], "outcomes in the order they were recorded"
    assert exact(stored[2][2], second), "every repetition keeps its own outcome"
    with pytest.raises(KeyError):
        reopened.get("r10", WB)
    for pipeline, bad in (
        (PO, replace(po, handoff_quality="complete")),
        (PO, replace(po, reviewer_total=11)),
        ("workbench", wb),
    ):
        with pytest.raises(ValueError):
            reopened.record("r3", pipeline, bad)
    reopened.close()


@pytest.mark.skip("Part 3")
def test_paired_comparison() -> None:
    """Runs pair up by id, and every outcome is compared in its own units and direction."""
    readme, release = "sample_app/README.md", "sample_app/scripts/release.sh"
    records = [
        ("r1", PO, Outcome(False, False, [readme, release], "missing", 3)),
        ("r1", WB, Outcome(True, True, [], "full packet", 9)),
        ("r2", WB, Outcome(True, False, ["docs/a.md"], "partial", 6)),
        ("r3", PO, Outcome(False, False, [], "missing", 4)),
        ("r2", PO, Outcome(True, False, ["app/zz.py"], "missing", 7)),
        ("r4", PO, Outcome(True, True, [], "full packet", 8)),
        ("r7", WB, Outcome(True, True, [], "partial", 8)),
        ("r5", WB, Outcome(True, True, ["x.md"], "full packet", 10)),
        ("r5", PO, Outcome(False, False, ["a.md", "b.md", "c.md"], "missing", 1)),
        ("r6", PO, Outcome(True, True, [], "full packet", 9)),
        ("r6", WB, Outcome(True, True, [], "full packet", 9)),
        ("r7", PO, Outcome(True, False, ["docs/x.md", "docs/y.md"], "partial", 5)),
        ("r4", WB, Outcome(True, True, [], "partial", 7)),
    ]
    report = compare(records)
    assert (report["n"], report["unpaired"]) == (6, ["r3"]), "only runs with both pipelines are compared"
    counts = {name: (o["workbench"], o["prompt_only"], o["tie"]) for name, o in report["outcomes"].items()}
    assert counts["tests_actually_run"] == (2, 0, 4), "each run is compared with the same run of the other pipeline"
    assert counts["handoff_quality"] == (3, 1, 2), "handoff levels rank missing < partial < full packet"
    assert counts["files_outside_scope"] == (3, 0, 3), "fewer files outside scope is better, counted in files"
    assert counts == {
        "tests_actually_run": (2, 0, 4),
        "acceptance_met": (3, 0, 3),
        "files_outside_scope": (3, 0, 3),
        "handoff_quality": (3, 1, 2),
        "reviewer_total": (3, 2, 1),
    }, "(workbench better, prompt-only better, tie) for every outcome"
    assert {name: o["median_delta"] for name, o in report["outcomes"].items()} == {
        "tests_actually_run": 0,
        "acceptance_met": 0.5,
        "files_outside_scope": -1,
        "handoff_quality": 0.5,
        "reviewer_total": 1.5,
    }, "median_delta is the median of the per-run differences, workbench minus prompt-only"
    assert report["outcomes"]["reviewer_total"] == {"workbench": 3, "prompt_only": 2, "tie": 1, "median_delta": 1.5}
    assert report["no_gain"] == ["r4", "r6"], "list every paired run where the workbench did better on nothing"
    with pytest.raises(ValueError):
        compare(records[3:4])

    store = OutcomeStore()
    for run in ("first", "second", "third"):
        store.record(run, PO, measure(run_prompt_only(), SIGNUP))
        store.record(run, WB, measure(run_workbench(), SIGNUP))
    report = compare(store.outcomes())
    assert (report["n"], report["no_gain"]) == (3, [])
    assert {name: (o["workbench"], o["median_delta"]) for name, o in report["outcomes"].items()} == {
        "tests_actually_run": (3, 1),
        "acceptance_met": (3, 1),
        "files_outside_scope": (3, -2),
        "handoff_quality": (3, 2),
        "reviewer_total": (3, 6),
    }, "the lesson's two runs, three times over"


APP = '''"""Minimal signup handler."""

USERS: dict[str, str] = {}
HELP = "see README.md#signup"


def signup(email: str, password: str) -> dict[str, object]:
    USERS[email] = password
    return {"status": 200, "email": email}
'''
SPACED = APP.replace("USERS: dict[str, str] = {}", "USERS: dict[str, str]  =  {}\n").replace(
    "USERS[email] = password", "USERS[email]   =   password   "
)
COMMENTED = SPACED.replace("    USERS[email]", "    # TODO: reject short passwords before storing them\n    USERS[email]").replace(
    "USERS: dict[str, str]  =  {}", "USERS: dict[str, str]  =  {}  # email -> password"
)
ANCHORED = COMMENTED.replace("README.md#signup", "README.md#passwords")
VALIDATED = ANCHORED.replace(
    "    # TODO: reject short passwords before storing them\n",
    '    if len(password) < 8:\n        return {"status": 422, "error": {"type": "password_too_short"}}\n',
)
NEW_TEST = '''

def test_signup_rejects_short_password():
    out = signup("a@b.co", "short")
    assert out["status"] == 422
'''


def edit(t_ms: int, path: str, before: str, after: str) -> dict:
    return {"t_ms": t_ms, "kind": "edit", "path": path, "before": before, "after": after}


def command(t_ms: int, *args, **extra) -> dict:
    return {"t_ms": t_ms, "kind": "command", "record": record(*args, **extra)}


@pytest.mark.skip("Part 4")
def test_milestone_stream() -> None:
    """Each run's milestones go out while the runs are still going, timed by each run's clock."""
    readme = "# sample app\n\nForbidden zone for agent tasks.\n"

    async def consume() -> list[str]:
        gate = asyncio.Event()

        async def prompt_only():
            yield {"t_ms": 800, "kind": "read", "path": "sample_app/README.md"}
            yield edit(1500, "sample_app/README.md", readme, readme + "\nPasswords need 8 characters.\n")
            yield edit(1800, "sample_app/settings.py", "DEBUG = False\n", "DEBUG = False\nMIN_PASSWORD = 8\n")
            yield edit(2100, "sample_app/app.py", APP, SPACED)
            yield edit(2600, "sample_app/app.py", SPACED, COMMENTED)
            yield edit(3300, "sample_app/app.py", COMMENTED, ANCHORED)
            yield edit(3900, "sample_app/app.py", ANCHORED, VALIDATED)
            yield {"t_ms": 4100, "kind": "claim", "done": True, "tests_passed": True}

        async def workbench():
            yield {"t_ms": 1200, "kind": "read", "path": "outputs/scope/signup.json"}
            yield command(2400, ["bash", "init.sh"], 0, {})
            await gate.wait()
            yield edit(9000, "sample_app/test_app.py", TEST_APP_PY, TEST_APP_PY + NEW_TEST)
            yield command(15000, [*PYTEST, "sample_app/test_app.py"], 1, {HAPPY: "passed", SHORT: "failed"})
            yield edit(22000, "sample_app/app.py", APP, VALIDATED)
            yield command(30000, [*PYTEST, "sample_app/test_app.py"], None, {HAPPY: "passed", SHORT: "passed"},
                          error="timed out after 120 s")
            yield command(38000, [*PYTEST, "sample_app/test_app.py"], 0, {HAPPY: "passed", SHORT: "passed"})
            yield {"t_ms": 52000, "kind": "claim", "done": True, "tests_passed": True}

        lines = []
        async for line in milestones({WB: workbench(), PO: prompt_only()}, SIGNUP):
            lines.append(line)
            if line.startswith("prompt-only,acceptance_met,"):
                gate.set()
        return lines

    try:
        lines = asyncio.run(asyncio.wait_for(consume(), 2.0))
    except asyncio.TimeoutError:
        pytest.fail(
            "the stream stalled: a run that is waiting holds back none of the others, and a run "
            "that ends reports what it never reached right away"
        )
    assert all(len(list(csv.reader(io.StringIO(line)))) == 1 and line.endswith("\n") for line in lines), (
        "every yielded string is one CSV record with its line ending"
    )
    rows = list(csv.reader(io.StringIO("".join(lines))))
    assert rows[0] == ["pipeline", "milestone", "t_ms"], "the header comes first"
    runs = {pipeline: [row[1:] for row in rows[1:] if row[0] == pipeline] for pipeline in (PO, WB)}
    assert runs[WB] == [["first_meaningful_edit", "9000"], ["tests_run", "15000"], ["acceptance_met", "38000"]], (
        "milestones are timed by the run's own clock and come from its finished commands"
    )
    assert runs[PO][:1] == [["first_meaningful_edit", "3300"]], (
        "a meaningful edit changes allowed code, not just comments, blank lines or spacing"
    )
    assert runs[PO][1:] == [["tests_run", ""], ["acceptance_met", ""]], (
        "a run that never ran a test reports both milestones as unreached when it ends"
    )
    assert len(rows) == 7, "each milestone once per run"

    async def one_shot():
        yield edit(500, "sample_app/app.py", APP, VALIDATED)
        yield command(900, [*PYTEST, SHORT], 0, {SHORT: "passed"})

    async def drain() -> list[str]:
        return [line async for line in milestones({WB: one_shot()}, SIGNUP)]

    rows = list(csv.reader(io.StringIO("".join(asyncio.run(asyncio.wait_for(drain(), 2.0))))))
    assert rows[1:] == [[WB, "first_meaningful_edit", "500"], [WB, "tests_run", "900"], [WB, "acceptance_met", "900"]], (
        "an event that reaches two milestones reports them in MILESTONES order"
    )


REPO = {
    "sample_app/app.py": (
        "from . import errors\nfrom .validators import check_password\n\n\n"
        "def signup(email, password):\n    problem = check_password(password)\n"
        "    return problem or {'status': 200, 'email': email}\n"
    ),
    "sample_app/validators.py": (
        "import re\n\nfrom .errors import envelope\n\nMIN_LENGTH = 8\n\n\n"
        "def check_password(password):\n"
        "    if len(password) < MIN_LENGTH or re.fullmatch(r'\\s+', password):\n"
        "        return envelope('password_too_short')\n    return None\n"
    ),
    "sample_app/errors.py": (
        "def envelope(code):\n    from .validators import MIN_LENGTH  # validators imports this module\n\n"
        "    return {'status': 422, 'error': {'type': code, 'min_length': MIN_LENGTH}}\n"
    ),
    "sample_app/api/__init__.py": "from .routes import router\n",
    "sample_app/api/routes.py": "from .. import app\n\nrouter = {'/signup': app.signup}\n",
    "sample_app/testing.py": (
        "from .validators import MIN_LENGTH\n\n\ndef password(length=MIN_LENGTH):\n"
        "    return 'x' * length\n"
    ),
    "sample_app/test_app.py": (
        "from sample_app.app import signup\nfrom sample_app.testing import password\n\n\n"
        "def test_signup_happy_path():\n    assert signup('a@b.co', password())['status'] == 200\n"
    ),
    "sample_app/test_validators.py": (
        "from sample_app import validators\n\n\ndef test_eight_characters():\n"
        "    assert validators.check_password('12345678') is None\n"
    ),
    "sample_app/test_errors.py": (
        "import sample_app.errors as errors\n\n\ndef test_envelope():\n"
        "    assert errors.envelope('x')['status'] == 422\n"
    ),
    "sample_app/api/test_routes.py": (
        "import pytest\n\nfrom sample_app.api import router\n\n\ndef test_signup_route():\n"
        "    assert '/signup' in router\n"
    ),
    "sample_app/api/test_health.py": "import json\n\n\ndef test_health():\n    assert json.loads('{}') == {}\n",
    "sample_app/README.md": "# sample app\n\nUse sample_app.validators to check a password.\n",
    "lib/__init__.py": "from .config import settings\n",
    "lib/config.py": "settings = {'min_password': 8}\n",
    "lib/util.py": "def slug(text):\n    return text.lower().replace(' ', '-')\n",
    "lib/test_config.py": (
        "from lib import config\n\n\ndef test_min_password():\n    assert config.settings['min_password'] == 8\n"
    ),
    "tests/test_util.py": "import lib.util\n\n\ndef test_slug():\n    assert lib.util.slug('A B') == 'a-b'\n",
}


@pytest.mark.skip("Part 5")
def test_change_impact() -> None:
    """A change affects every test that imports it, however indirectly."""
    assert affected_tests(REPO, ["sample_app/validators.py"]) == [
        "sample_app/api/test_routes.py",
        "sample_app/test_app.py",
        "sample_app/test_errors.py",
        "sample_app/test_validators.py",
    ], "every test that imports the change, directly or through other modules"
    assert affected_tests(REPO, ["lib/config.py"]) == ["lib/test_config.py", "tests/test_util.py"], (
        "importing lib.util runs lib/__init__.py too"
    )
    assert affected_tests(REPO, ["sample_app/api/test_health.py", "sample_app/README.md"]) == [
        "sample_app/api/test_health.py"
    ], "a changed test is affected itself; a README change affects no test"
    assert proves_change(SIGNUP.acceptance, REPO, ["sample_app/validators.py"]) is True, (
        "a test inside an affected test file exercises the change"
    )
    assert proves_change(("sample_app/api",), REPO, ["sample_app/validators.py"]) is True, (
        "a directory selector runs the tests under it"
    )
    assert proves_change(SIGNUP.acceptance, REPO, ["lib/config.py"]) is False, (
        "the acceptance test must exercise the change"
    )
    assert proves_change(SIGNUP.acceptance, REPO, ["sample_app/README.md"]) is False
