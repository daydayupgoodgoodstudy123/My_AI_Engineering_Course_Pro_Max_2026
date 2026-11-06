import asyncio
import hashlib
import time
from dataclasses import replace

import pytest
from taskframe.decisions import Assessment, Decision, assess
from taskframe.frame import RepositoryFact, TaskFrame, Unknown, validate
from taskframe.narrow import narrow_paths
from taskframe.pins import ReceiptStore, Verdict
from taskframe.recon import Probe, recon
from taskframe.repo import Repo

ACCOUNTS_V1 = '''\
"""Accounts: signup, lookup and the store behind them.

Every write goes through AccountStore. The API layer never touches the
dict directly, and it turns DUPLICATE_EMAIL into the public error shape.
"""
from __future__ import annotations

from app.api.errors import DUPLICATE_EMAIL

__all__ = ["AccountStore", "signup"]


def signup(store: AccountStore, email: str, name: str) -> dict:
    """Create an account. Raises DUPLICATE_EMAIL for an address already taken."""
    return store.save(email, name)


class AccountStore:
    """Accounts by email, in memory. Tests use a fresh store per case."""

    def __init__(self) -> None:
        self._by_email: dict[str, dict] = {}

    def save(self, email: str, name: str) -> dict:
        email = email.strip()
        if email in self._by_email:
            raise DUPLICATE_EMAIL
        account = {"email": email, "name": name}
        self._by_email[email] = account
        return account

    def find(self, email: str) -> dict | None:
        return self._by_email.get(email.strip())
'''

# The next commit: two imports above the class, emails made canonical, a rename method.
ACCOUNTS_V2 = '''\
"""Accounts: signup, lookup and the store behind them.

Every write goes through AccountStore. The API layer never touches the
dict directly, and it turns DUPLICATE_EMAIL into the public error shape.
"""
from __future__ import annotations

from app.api.errors import DUPLICATE_EMAIL
from app.audit import record
from app.emails import canonical

__all__ = ["AccountStore", "signup"]


def signup(store: AccountStore, email: str, name: str) -> dict:
    """Create an account. Raises DUPLICATE_EMAIL for an address already taken."""
    return store.save(email, name)


class AccountStore:
    """Accounts by email, in memory. Tests use a fresh store per case."""

    def __init__(self) -> None:
        self._by_email: dict[str, dict] = {}

    def save(self, email: str, name: str) -> dict:
        email = canonical(email)
        if email in self._by_email:
            raise DUPLICATE_EMAIL
        account = {"email": email, "name": name}
        self._by_email[email] = account
        return account

    def rename(self, email: str, name: str) -> dict:
        account = self._by_email[canonical(email)]
        account["name"] = name
        record("rename", email)
        return account

    def find(self, email: str) -> dict | None:
        return self._by_email.get(canonical(email))
'''

ERRORS = '''\
"""Error shapes the public API returns. Clients match on code, never on text."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


NOT_FOUND = ApiError(404, "not_found")
INVALID_EMAIL = ApiError(422, "invalid_email")
DUPLICATE_EMAIL = ApiError(409, "email_taken")
'''

MESSAGES = '''\
"""User-facing messages by error code. French is the default locale."""

MESSAGES = {
    "email_taken": "Cette adresse e-mail est déjà utilisée — connectez-vous.",
    "invalid_email": "Adresse e-mail invalide.",
}
'''

SIGNUP = '''\
"""POST /signup."""

from app.accounts import AccountStore, signup
from app.api.errors import ApiError

STORE = AccountStore()


def handle(form: dict) -> tuple[int, dict]:
    try:
        account = signup(STORE, form["email"], form.get("name", ""))
    except ApiError as err:
        return err.status, {"error": err.code}
    return 201, account
'''

# The two test classes are separated by a form feed, the page break PEP 8 allows.
TEST_ACCOUNTS_V1 = '''\
import unittest

from app.accounts import AccountStore, signup
from app.api.errors import ApiError
from app.api.signup import handle


class SignupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = AccountStore()

    def test_signup_creates_account(self) -> None:
        account = signup(self.store, "ana@example.com", "Ana")
        self.assertEqual(account["email"], "ana@example.com")

    def test_signup_strips_whitespace(self) -> None:
        account = signup(self.store, "  ana@example.com ", "Ana")
        self.assertEqual(account["email"], "ana@example.com")

    def test_find_returns_none_for_unknown(self) -> None:
        self.assertIsNone(self.store.find("nobody@example.com"))

    def test_duplicate_email_raises(self) -> None:
        signup(self.store, "ana@example.com", "Ana")
        with self.assertRaises(ApiError) as caught:
            signup(self.store, "ana@example.com", "Ana B")
        self.assertEqual(caught.exception.code, "email_taken")

\f
class SignupHandlerTests(unittest.TestCase):
    def test_handler_creates(self) -> None:
        status, body = handle({"email": "bo@example.com", "name": "Bo"})
        self.assertEqual(status, 201)
        self.assertEqual(body["name"], "Bo")

    def test_handler_rejects_bad_form(self) -> None:
        with self.assertRaises(KeyError):
            handle({"name": "No Email"})

    def test_handler_maps_duplicate_to_409(self) -> None:
        handle({"email": "cy@example.com", "name": "Cy"})
        status, body = handle({"email": "cy@example.com", "name": "Cy"})
        self.assertEqual(body, {"error": "email_taken"})
        self.assertEqual(status, 409)
'''

ROUTES = '''\
"""POST /signup, behind the router."""

from app.accounts import AccountStore, signup as create_account
from app.api.errors import ApiError

STORE = AccountStore()


def handle(form: dict) -> tuple[int, dict]:
    try:
        account = create_account(STORE, form["email"], form.get("name", ""))
    except ApiError as err:
        return err.status, {"error": err.code}
    return 201, account
'''

MAKEFILE = "test:\n\tpython3 -m unittest tests.test_accounts  \n\nlint:\n\truff check app tests\n"

FILES_V1 = {
    "AGENTS.md": (
        "# Agent instructions\n\n"
        "- Run `make test` before you hand work back.\n"
        "- Never edit files under deploy/.\n"
        "- Migrations need a human review: do not add one in an agent task.\n"
    ),
    "Makefile": MAKEFILE,
    "app/__init__.py": "",
    "app/accounts.py": ACCOUNTS_V1,
    "app/settings.py": 'DEBUG = False\nDATABASE_URL = "sqlite:///accounts.db"',
    "app/api/__init__.py": "",
    "app/api/errors.py": ERRORS,
    "app/api/messages.py": MESSAGES,
    "app/api/signup.py": SIGNUP,
    "tests/__init__.py": "",
    "tests/test_accounts.py": TEST_ACCOUNTS_V1,
    "migrations/0006_add_index.py": (
        '"""Add an index on accounts.email."""\n\n'
        'STATEMENTS = ["CREATE INDEX accounts_email ON accounts (email)"]\n'
    ),
    "deploy/prod.yaml": "replicas: 3\nimage: accounts:1.4.2\n",
}

FILES_V2 = {
    **{path: text for path, text in FILES_V1.items() if path != "app/api/signup.py"},
    "Makefile": MAKEFILE.replace("tests.test_accounts  \n", "tests.test_accounts\n"),
    "app/accounts.py": ACCOUNTS_V2,
    "app/api/errors.py": ERRORS + 'RATE_LIMITED = ApiError(429, "rate_limited")\n',
    "app/api/routes.py": ROUTES,
    "tests/test_accounts.py": TEST_ACCOUNTS_V1.replace(
        "from app.api.signup import handle", "from app.api.routes import handle"
    )
    + (
        "\n"
        "    def test_handler_409_ignores_case(self) -> None:\n"
        '        handle({"email": "di@example.com", "name": "Di"})\n'
        '        status, _ = handle({"email": "DI@example.com", "name": "Di"})\n'
        "        self.assertEqual(status, 409)\n"
    ),
}

CURL = "$ curl -s -o /dev/null -w '%{http_code}' -d email=cy@example.com localhost:8000/signup -> 409"
GREP_COUNT = "$ git grep -c 'raise DUPLICATE_EMAIL' -> app/accounts.py:1"


def nest(files: dict[str, str]) -> dict:
    """The checkout as a directory tree."""
    tree: dict = {}
    for path, text in files.items():
        *dirs, name = path.split("/")
        node = tree
        for part in dirs:
            node = node.setdefault(part, {})
        node[name] = text
    return tree


def example() -> TaskFrame:
    """The lesson's frame for duplicate email protection, with receipts for FILES_V1."""
    return TaskFrame(
        goal="Prevent duplicate email addresses during signup",
        allowed_paths=["app/accounts.py", "tests/test_accounts.py"],
        forbidden_paths=["migrations/**", "deploy/**"],
        acceptance=["python3 -m unittest tests.test_accounts"],
        facts=[
            RepositoryFact("Account writes use AccountStore", "app/accounts.py:18", ("layer",)),
            RepositoryFact("Duplicate errors use status 409", "app/api/errors.py:13", ("error_shape",)),
            RepositoryFact("Only AccountStore.save raises DUPLICATE_EMAIL", GREP_COUNT, ("layer",)),
            RepositoryFact("The signup endpoint answers 409 today", CURL, ("error_shape",)),
        ],
        unknowns=[Unknown("Are Ana@example.com and ana@example.com one account?", "human", "case_rule")],
    )


@pytest.mark.skip("Part 1")
def test_validate_frame() -> None:
    """The validator refuses a frame for each reason it has, and keeps up with a big repository."""
    repo = Repo(FILES_V1)
    assert validate(example(), repo) == [], "the lesson's example frame is ready"

    no_goal, no_receipt, no_acceptance, same_path, no_facts = (example() for _ in range(5))
    no_goal.goal = "  "
    no_receipt.facts[0] = replace(no_receipt.facts[0], evidence="")
    no_acceptance.acceptance = []
    same_path.forbidden_paths.append("app/accounts.py")
    no_facts.facts = []
    assert [validate(frame, repo) for frame in (no_goal, no_receipt, no_acceptance, same_path, no_facts)] == [
        ["goal is empty"],
        ["unsupported fact: Account writes use AccountStore"],
        ["acceptance evidence is empty"],
        ["paths are both allowed and forbidden: app/accounts.py"],
        ["repository facts are empty"],
    ], "each broken frame is refused for its own reason"

    def receipt(evidence: str) -> list[str]:
        frame = example()
        frame.facts = [RepositoryFact("the claim", evidence)]
        return validate(frame, repo)

    for good in ("tests/test_accounts.py:44", "app/settings.py:2", "Makefile:2", "$ make test -> exit 0"):
        assert receipt(good) == [], f"{good!r} is a receipt"
    for bad in (
        "trust me",
        "app/missing.py:3",
        "app/accounts.py:34",
        "tests/test_accounts.py:45",
        "app/accounts.py:0",
        "app/api:2",
    ):
        assert receipt(bad) == ["unsupported fact: the claim"], f"{bad!r} does not resolve"
    for bad in ("$ python3 -m unittest tests.test_accounts", "$ make test -> "):
        assert receipt(bad) == ["unsupported fact: the claim"], (
            "a command receipt records what the command returned"
        )

    # A batch of queued frames, each citing call sites in two generated API clients.
    generated = {
        f"gen/client_{side}.py": "".join(f"def call_{i}(request): ...\n" for i in range(20_000))
        for side in ("a", "b")
    }
    big = Repo(generated)
    frames = []
    for i in range(500):
        frame = example()
        frame.facts = [
            RepositoryFact("client a has the call", f"gen/client_a.py:{i * 37 % 20_000 + 1}"),
            RepositoryFact("client b has the call", f"gen/client_b.py:{i * 53 % 20_000 + 1}"),
            RepositoryFact("client a has a later call", f"gen/client_a.py:{i * 41 % 19_999 + 2}"),
        ]
        frames.append(frame)
    start = time.perf_counter()
    reports = [validate(frame, big) for frame in frames]
    elapsed = time.perf_counter() - start
    assert reports == [[]] * len(frames)
    assert elapsed < 0.05, "checking many frames against one snapshot should be fast"

    before = Repo({"app/accounts.py": "pass\n" * 10})
    after = Repo({"app/accounts.py": "pass\n" * 50})
    grown = example()
    grown.facts = [RepositoryFact("the store grew", "app/accounts.py:30")]
    assert validate(grown, before) == ["unsupported fact: the store grew"], (
        "each snapshot answers for its own files"
    )
    assert validate(grown, after) == [], "each snapshot answers for its own files"


PIN_FACTS = [
    RepositoryFact("Account writes use AccountStore", "app/accounts.py:18"),
    RepositoryFact("Emails are only stripped", "app/accounts.py:25"),
    RepositoryFact("save returns the stored account", "app/accounts.py:30"),
    RepositoryFact("Duplicate errors use status 409", "app/api/errors.py:13"),
    RepositoryFact("Only AccountStore.save raises DUPLICATE_EMAIL", GREP_COUNT),
    RepositoryFact("Le message par défaut est en français", "app/api/messages.py:4"),
    RepositoryFact("make test runs only the accounts tests", "Makefile:2"),
    RepositoryFact("The handler builds on AccountStore", "app/api/signup.py:3"),
    RepositoryFact("The signup endpoint answers 409 today", CURL),
    RepositoryFact("The tests import AccountStore the same way", "tests/test_accounts.py:3"),
    RepositoryFact("A test pins the 409", "tests/test_accounts.py:44"),
]


@pytest.mark.skip("Part 2")
def test_receipt_pins(tmp_path) -> None:
    """Pinned receipts keep each cited line exactly, by its sha256, and tell what changed since."""
    root = tmp_path / "pins"
    v1 = Repo(FILES_V1)
    store = ReceiptStore(str(root))
    digest = store.pin(PIN_FACTS, v1)
    pins = store.pins(digest)
    assert [(p.claim, f"{p.path}:{p.line}") for p in pins] == [
        (f.claim, f.evidence) for f in PIN_FACTS if not f.evidence.startswith("$")
    ], "one pin per line receipt, in fact order"
    for pin in pins:
        line = FILES_V1[pin.path].split("\n")[pin.line - 1]
        assert pin.digest == hashlib.sha256(line.encode("utf-8")).hexdigest(), (
            "a pin holds the sha256 of the cited line's UTF-8 bytes, without the newline"
        )
        assert store.get(pin.digest) == line.encode("utf-8"), f"{pin.path}:{pin.line} comes back byte for byte"

    def objects() -> list:
        return sorted(f for f in (root / "objects").rglob("*") if f.is_file())

    assert all(f.parent.name + f.name == hashlib.sha256(f.read_bytes()).hexdigest() for f in objects()), (
        "every object is a file objects/ab/cdef... named by the sha256 of its bytes"
    )
    assert len(objects()) == 9, "each distinct line is stored once, plus the pin list"
    assert store.pin(PIN_FACTS, v1) == digest and len(objects()) == 9, "pinning again stores nothing new"
    first_two = store.pin(PIN_FACTS[:2], v1)

    reopened = ReceiptStore(str(root))
    assert reopened.pins(digest) == pins and reopened.pins(first_two) == pins[:2], (
        "every pin list survives a reopen"
    )
    with pytest.raises(KeyError):
        reopened.pins("0" * 64)
    with pytest.raises(ValueError):
        reopened.pin([RepositoryFact("past the end", "app/accounts.py:34")], v1)

    verdicts = reopened.recheck(digest, Repo(FILES_V2))
    by_claim = {v.claim: v for v in verdicts}
    assert [v.claim for v in verdicts] == [p.claim for p in pins], "one verdict per pin, in pin order"
    assert by_claim["Duplicate errors use status 409"] == Verdict(
        "Duplicate errors use status 409", "fresh", "app/api/errors.py:13"
    ), "an edit elsewhere in the file leaves a receipt fresh"
    assert by_claim["Account writes use AccountStore"] == Verdict(
        "Account writes use AccountStore", "moved", "app/accounts.py:20"
    ), "a line found once more in its own file has moved there"
    assert by_claim["save returns the stored account"].status == "stale", (
        "a line that now sits on two lines is stale: which one the fact meant is a guess"
    )
    assert by_claim["A test pins the 409"] == Verdict("A test pins the 409", "fresh", "tests/test_accounts.py:44"), (
        "a line still in place is fresh, even when it appears again below"
    )
    assert by_claim["The handler builds on AccountStore"] == Verdict(
        "The handler builds on AccountStore", "stale", None
    ), "a receipt never moves to another file"
    assert verdicts == [
        Verdict("Account writes use AccountStore", "moved", "app/accounts.py:20"),
        Verdict("Emails are only stripped", "stale", None),
        Verdict("save returns the stored account", "stale", None),
        Verdict("Duplicate errors use status 409", "fresh", "app/api/errors.py:13"),
        Verdict("Le message par défaut est en français", "fresh", "app/api/messages.py:4"),
        Verdict("make test runs only the accounts tests", "stale", None),
        Verdict("The handler builds on AccountStore", "stale", None),
        Verdict("The tests import AccountStore the same way", "fresh", "tests/test_accounts.py:3"),
        Verdict("A test pins the 409", "fresh", "tests/test_accounts.py:44"),
    ], "a byte that changed makes a receipt stale, trailing spaces included"


PLAN = [
    Decision("layer", "Does uniqueness belong in the API, the domain service or the database?"),
    Decision("case_rule", "Is email comparison case-sensitive?"),
    Decision("error_shape", "Which error shape is already public?"),
    Decision("migration", "Is a migration allowed?"),
    Decision("proof", "Which test proves the behavior?"),
    Decision("message", "Which message goes with the error?"),
]

ASK_CASE = Unknown("Are Ana@example.com and ana@example.com one account?", "human", "case_rule")
MAY_REWORD = Unknown("May the agent reword the duplicate-email message?", "decidable", "message")
WHICH_RUNNER = Unknown("Which test target does CI run?", "discoverable", "proof", look_at="Makefile")
LATER_MIGRATION = Unknown("Does the unique index need a migration?", "deferred", "migration")


def decision_frame(proof_receipt: str, unknowns: list[Unknown], non_goals: list[str]) -> TaskFrame:
    frame = example()
    frame.facts = [
        RepositoryFact("Account writes use AccountStore", "app/accounts.py:18", ("layer",)),
        RepositoryFact("Duplicate errors use status 409", "app/api/errors.py:13", ("error_shape",)),
        RepositoryFact("A test pins the 409", proof_receipt, ("proof",)),
    ]
    frame.unknowns, frame.non_goals = unknowns, non_goals
    return frame


@pytest.mark.skip("Part 3")
def test_decision_coverage() -> None:
    """Every planned decision is backed by evidence, delegated, or an unknown that says what happens next."""
    repo = Repo(FILES_V1)
    unknowns = [MAY_REWORD, LATER_MIGRATION, WHICH_RUNNER, ASK_CASE]
    frame = decision_frame("tests/test_signup.py:12", unknowns, ["migration"])
    assert assess(frame, PLAN, {"layer"}, repo) == Assessment(
        status="ASK",
        decisions={
            "layer": "evidence",
            "case_rule": "ask",
            "error_shape": "evidence",
            "migration": "deferred",
            "proof": "investigate",
            "message": "ask",
        },
        questions=[ASK_CASE.question, MAY_REWORD.question],
        reads=["Makefile"],
    ), "a human question outranks anything left to read; questions follow the plan"

    ready = decision_frame("tests/test_accounts.py:44", [MAY_REWORD, LATER_MIGRATION, WHICH_RUNNER], ["migration"])
    assert assess(ready, PLAN, {"case_rule", "message"}, repo) == Assessment(
        status="READY",
        decisions={
            "layer": "evidence",
            "case_rule": "delegated",
            "error_shape": "evidence",
            "migration": "deferred",
            "proof": "evidence",
            "message": "delegated",
        },
        questions=[],
        reads=[],
    ), "evidence settles a decision, so there is nothing left to read for it"

    unlisted = decision_frame("tests/test_accounts.py:44", [LATER_MIGRATION], [])
    assert assess(unlisted, PLAN, {"case_rule", "message"}, repo).decisions["migration"] == "open", (
        "a deferred decision has to appear among the non-goals"
    )
    nowhere = decision_frame("tests/test_signup.py:12", [replace(WHICH_RUNNER, look_at=" ")], [])
    result = assess(nowhere, PLAN, {"case_rule", "message", "migration"}, repo)
    assert (result.status, result.decisions["proof"], result.reads) == ("INVESTIGATE", "open", []), (
        "a discoverable unknown has to say where to look"
    )
    contested = decision_frame(
        "tests/test_accounts.py:44",
        [Unknown("Should a duplicate answer 422 from now on?", "human", "error_shape")],
        [],
    )
    result = assess(contested, PLAN, {"case_rule", "message", "migration"}, repo)
    assert (result.status, result.decisions["error_shape"]) == ("ASK", "ask"), (
        "evidence of today's behavior does not answer a human question"
    )
    two_leads = decision_frame(
        "tests/test_signup.py:12",
        [
            WHICH_RUNNER,
            replace(WHICH_RUNNER, decision="case_rule"),
            replace(MAY_REWORD, kind="discoverable", look_at="app/api/messages.py"),
        ],
        [],
    )
    result = assess(two_leads, PLAN, {"migration"}, repo)
    assert result.reads == ["Makefile", "app/api/messages.py"], "each place to look once, in plan order"

    second_question = "Should existing mixed-case accounts be merged?"
    several_questions = decision_frame(
        "tests/test_accounts.py:44",
        [
            Unknown(ASK_CASE.question, "human", "message"),
            ASK_CASE,
            Unknown(second_question, "human", "case_rule"),
            ASK_CASE,
        ],
        [],
    )
    result = assess(several_questions, PLAN, {"migration"}, repo)
    assert result.questions == [ASK_CASE.question, second_question], (
        "every blocking question is kept once, in plan then frame order"
    )

    delegated_lead = decision_frame(
        "tests/test_accounts.py:44", [replace(WHICH_RUNNER, decision="case_rule")], []
    )
    result = assess(delegated_lead, PLAN, {"case_rule", "migration", "message"}, repo)
    assert (result.status, result.decisions["case_rule"], result.reads) == ("READY", "delegated", []), (
        "delegation settles a decision before a discoverable lead"
    )

    with pytest.raises(ValueError):
        assess(decision_frame("tests/test_accounts.py:44", [replace(ASK_CASE, kind="assumption")], []), PLAN, set(), repo)
    with pytest.raises(ValueError):
        assess(decision_frame("tests/test_accounts.py:44", [replace(ASK_CASE, decision="rollout")], []), PLAN, set(), repo)


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def search(lines: list[str], pulled: list[str]):
    """A code search that is still running: its output, one line at a time."""
    for line in lines:
        pulled.append(line)
        yield line


PROBES = [
    Probe("layer", r"\bAccountStore\b", ("behavior",)),
    Probe("case_rule", r"\.(?:lower|casefold)\(\)", ("behavior", "test")),
    Probe("error_shape", r"\b409\b", ("test",)),
    Probe("error_shape", r"\bConflict\b", ("contract",)),
    Probe("migration", r"(?i)\bmigrations?\b", ("instructions",)),
]

HITS = [
    "Binary file static/logo.png matches",
    "--",
    "docs/adr/0007-error-codes.md:12:Duplicates answer 409: the API schema says so.",
    "tests/http-409/test_conflict.py:3:import unittest",
    "app/accounts.py:18:class AccountStore:",
    "app/accounts.py:25:        email = email.strip()",
    "tests/test_signup_case.py:12:        self.assertEqual(handle({'email': EMAIL.lower()}), (409, {'error': 'email_taken'}))",
    "app/api/signup.py:6:STORE = AccountStore()",
    "api/openapi.yaml:88:          description: Conflict, the email is already registered",
    "AGENTS.md:5:- Migrations need a human review: do not add one in an agent task.",
    "app/accounts.py:30:        return account",
    "tests/test_accounts.py:44:        self.assertEqual(status, 409)",
]


@pytest.mark.skip("Part 4")
def test_recon_stream() -> None:
    """Reconnaissance reads search hits only until every decision has a constraint."""
    pulled: list[str] = []
    text = "".join(collect(recon(search(HITS, pulled), PROBES)))
    assert text.endswith("\n") and [line.split(":", 2) for line in text.split("\n")[:-1]] == [
        ["app/accounts.py", "18", "class AccountStore:"],
        [
            "tests/test_signup_case.py",
            "12",
            "        self.assertEqual(handle({'email': EMAIL.lower()}), (409, {'error': 'email_taken'}))",
        ],
        ["AGENTS.md", "5", "- Migrations need a human review: do not add one in an agent task."],
    ], "each hit that settles an open decision, once, as path:line:text"
    assert pulled == HITS[:10], "stop reading the moment every decision is settled"

    pulled.clear()

    async def first() -> str:
        hits = recon(search(HITS, pulled), PROBES)
        line = await hits.__anext__()
        await hits.aclose()
        return line

    assert asyncio.run(first()) == HITS[4] + "\n" and len(pulled) == 5, (
        "a hit goes out as soon as it settles something"
    )

    pulled.clear()
    text = "".join(collect(recon(search(HITS[:9], pulled), PROBES)))
    assert [line.split(":", 2)[:2] for line in text.split("\n")[:-1]] == [
        ["app/accounts.py", "18"],
        ["tests/test_signup_case.py", "12"],
    ] and len(pulled) == 9, "a search that runs dry ends the stream with what it found"

    pulled.clear()
    assert collect(recon(search(HITS, pulled), [])) == [] and pulled == [], "nothing to settle, nothing to read"
    assert collect(recon(search([], []), PROBES)) == []


@pytest.mark.skip("Part 5")
def test_narrow_allowed() -> None:
    """A broad allowed path splits into the fewest entries that are safe."""
    checkout = nest(FILES_V1)
    checkout["app"]["cache"] = {}
    checkout["app"]["legacy"] = {"__init__.py": "", "old_signup.py": "from app.accounts import signup\n"}
    planned = [
        "app/accounts.py",
        "app/api/__init__.py",
        "app/api/errors.py",
        "app/api/messages.py",
        "app/api/signup.py",
        "app/emails/__init__.py",
        "app/emails/canonical.py",
        "tests/test_accounts.py",
        "tests/conftest.py",
    ]
    assert narrow_paths(checkout, planned, ["migrations/**", "deploy/**", "app/settings.py"]) == [
        "app/accounts.py",
        "app/api/**",
        "app/emails/**",
        "tests/conftest.py",
        "tests/test_accounts.py",
    ], "collapse the directories the change fills; new files count, empty directories do not"

    everything = [path for path in FILES_V1 if path.startswith("app/")] + [
        "app/legacy/__init__.py",
        "app/legacy/old_signup.py",
    ]
    assert narrow_paths(checkout, everything, ["migrations/**", "deploy/**"]) == ["app/**"], (
        "collapse as high as the tree allows"
    )
    assert narrow_paths(checkout, everything, ["migrations/**", "app/.env"]) == [
        "app/__init__.py",
        "app/accounts.py",
        "app/api/**",
        "app/legacy/**",
        "app/settings.py",
    ], "a forbidden path that does not exist yet still keeps its directory from collapsing"

    small = {"README.md": "", "lib": {"only.py": ""}, "pkg": {"sub": {"x.py": "", "y.py": ""}}}
    assert narrow_paths(small, ["README.md", "lib/only.py", "pkg/sub/x.py", "pkg/sub/y.py"], []) == [
        "README.md",
        "lib/only.py",
        "pkg/sub/**",
    ], "collapse only when it replaces two or more entries; never collapse the root"
    service = {"svc": {"main.py": "", "core": {"rules.py": "", "keys": {"load.py": "", "rotate.py": ""}}}}
    every_file = ["svc/main.py", "svc/core/rules.py", "svc/core/keys/load.py", "svc/core/keys/rotate.py"]
    assert narrow_paths(service, every_file, ["svc/core/keys/private/**"]) == sorted(every_file), (
        "a forbidden entry deep below stops every directory above it"
    )

    siblings = {
        "pkg": {
            "keep": {"untouched.py": ""},
            "change": {"a.py": "", "b.py": ""},
            "main.py": "",
        }
    }
    assert narrow_paths(siblings, ["pkg/change/a.py", "pkg/change/b.py", "pkg/main.py"], []) == [
        "pkg/change/**", "pkg/main.py"
    ], "an unplanned sibling prevents the parent from collapsing"

    with pytest.raises(ValueError):
        narrow_paths(checkout, ["migrations/0007_unique_email.py"], ["migrations/**"])
    with pytest.raises(ValueError):
        narrow_paths(checkout, ["app/settings.py"], ["app/settings.py"])
