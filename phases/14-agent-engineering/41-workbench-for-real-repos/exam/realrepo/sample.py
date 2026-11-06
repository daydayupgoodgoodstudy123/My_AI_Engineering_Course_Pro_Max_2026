"""The lesson's sample app, the signup task's scope contract, and the two scripted runs.

Both runs are scripted (no LLM in the loop), so the measurement is reproducible. Each returns
what the run left behind; realrepo.outcomes measures it.
"""
from __future__ import annotations

from .artifacts import Contract, RunArtifacts, load_feedback

APP_PY = '''"""Minimal signup handler. Treat as production-ish for this exercise."""

USERS: dict[str, str] = {}


def signup(email: str, password: str) -> dict[str, object]:
    USERS[email] = password
    return {"status": 200, "email": email}
'''

TEST_APP_PY = '''from sample_app.app import signup


def test_signup_happy_path():
    out = signup("a@b.co", "longenough")
    assert out["status"] == 200
'''

SAMPLE_APP = {
    "sample_app/app.py": APP_PY,
    "sample_app/test_app.py": TEST_APP_PY,
    "sample_app/README.md": "# sample app\n\nForbidden zone for agent tasks.\n",
    "sample_app/scripts/release.sh": "#!/usr/bin/env bash\necho release\n",
}

TASK = (
    "Add input validation to /signup: reject passwords shorter than 8 characters, return 422 "
    "with a typed error envelope. Add a test that proves the new behavior."
)

HAPPY = "sample_app/test_app.py::test_signup_happy_path"
SHORT = "sample_app/test_app.py::test_signup_rejects_short_password"

SIGNUP = Contract(
    allowed=("sample_app/app.py", "sample_app/test_app.py"),
    forbidden=("sample_app/README.md", "sample_app/scripts/release.sh"),
    acceptance=(SHORT,),
)

WORKBENCH_FEEDBACK = """\
{"command": ["bash", "init.sh"], "exit_code": 0, "duration_ms": 840, "agent_note": "probes green before the first edit"}
{"command": ["python3", "-m", "pytest", "sample_app/test_app.py"], "exit_code": 1, "duration_ms": 610, "agent_note": "the new test fails until the validation exists", "results": {"sample_app/test_app.py::test_signup_happy_path": "passed", "sample_app/test_app.py::test_signup_rejects_short_password": "failed"}}
{"command": ["python3", "-m", "pytest", "sample_app/test_app.py"], "exit_code": 0, "duration_ms": 590, "agent_note": "both tests pass", "results": {"sample_app/test_app.py::test_signup_happy_path": "passed", "sample_app/test_app.py::test_signup_rejects_short_password": "passed"}}
{"command": ["python3", "gate.py", "signup-validation"], "exit_code": 0, "duration_ms": 130, "agent_note": "the verification gate passes"}
"""


def run_prompt_only() -> RunArtifacts:
    """Reads the README and app.py, edits files, never runs the test, claims done."""
    return RunArtifacts(
        pipeline="prompt-only",
        touched=("sample_app/app.py", "sample_app/README.md", "sample_app/scripts/release.sh"),
        feedback=(),
        claims={"done": True, "tests_passed": True},
        handoff=None,
        review={
            "scores": {
                "problem_fit": 1,
                "scope_discipline": 0,
                "assumptions": 1,
                "verification_quality": 0,
                "handoff_readiness": 1,
            },
            "total": 3,
            "verdict": "hard_fail",
        },
    )


def run_workbench() -> RunArtifacts:
    """Init script, scope contract, state, edits inside scope, the acceptance test through the
    feedback runner, the verification gate, the reviewer, and the handoff packet."""
    return RunArtifacts(
        pipeline="workbench-guided",
        touched=("sample_app/app.py", "sample_app/test_app.py"),
        feedback=load_feedback(WORKBENCH_FEEDBACK),
        claims={"done": True, "tests_passed": True},
        handoff={
            "summary": (
                "Validated /signup: a password shorter than 8 characters gets a 422 with a typed "
                "error envelope, and a new test proves it."
            ),
            "changed_files": ["sample_app/app.py", "sample_app/test_app.py"],
            "commands_run": [
                "bash init.sh",
                "python3 -m pytest sample_app/test_app.py",
                "python3 gate.py signup-validation",
            ],
            "failed_attempts": [],
            "open_risks": [{"risk": "USERS keeps passwords in plain text", "severity": "high"}],
            "next_action": "Hash passwords before they reach USERS, test first.",
            "verdict_pointer": "outputs/verification/signup-validation.json",
        },
        review={
            "scores": {
                "problem_fit": 2,
                "scope_discipline": 2,
                "assumptions": 1,
                "verification_quality": 2,
                "handoff_readiness": 2,
            },
            "total": 9,
            "verdict": "pass",
        },
    )
