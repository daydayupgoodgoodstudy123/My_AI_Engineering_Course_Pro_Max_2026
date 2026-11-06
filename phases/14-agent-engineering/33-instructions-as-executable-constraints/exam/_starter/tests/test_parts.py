import asyncio
import itertools
import time
from pathlib import Path

import pytest
from rulecheck.checker import Result, RuleChecker, score, unapproved_dependencies
from rulecheck.router import RouterReport, audit_router
from rulecheck.rulefile import add_rule, remove_rule, write_rules
from rulecheck.rules import BrokenRule, Rule, parse_rules
from rulecheck.runtime import Runtime
from rulecheck.timeline import Verdict, Watch, judge
from rulecheck.turn import Event, TurnTrace


def read(path: str) -> Event:
    return Event("read", path)


def write(path: str) -> Event:
    return Event("write", path)


def ran(command: str, exit_code: int) -> Event:
    return Event("run", command, exit_code=exit_code)


def install(package: str) -> Event:
    return Event("install", package)


def ask(note: str = "questions/open.md") -> Event:
    return Event("ask", note)


def decide(choice: str, confidence: float) -> Event:
    return Event("decide", choice, confidence=confidence)


def approve(what: str) -> Event:
    return Event("approve", what)


SEED = [
    Rule("startup/state-file-fresh", "startup", "state_file_fresh",
         "Agent must read agent_state.json before any tool call."),
    Rule("forbidden/no-release-script-edits", "forbidden", "no_release_script_edits",
         "Never edit scripts/release.sh outside an approved release task."),
    Rule("done/tests-pass", "definition_of_done", "tests_pass",
         "A task is done only when its acceptance command exits zero."),
    Rule("uncertainty/open-question-note", "uncertainty", "opened_question_when_unsure",
         "When confidence is below threshold, write a question note instead of guessing.", "warn"),
    Rule("approval/new-dependency", "approval", "new_dependency_approved",
         "Adding a runtime dependency requires explicit human approval."),
]

LESSON_RULES = """\
## startup/state-file-fresh
- category: startup
- check: state_file_fresh
Agent must read agent_state.json before any tool call.

## forbidden/no-release-script-edits
Never edit scripts/release.sh
outside an approved release task.
- category: forbidden
- check: no_release_script_edits

## done/tests-pass
- category: definition_of_done
- check: tests_pass
A task is done only when its acceptance command exits zero.

## uncertainty/open-question-note
- category: uncertainty
- check: opened_question_when_unsure
- severity: warn
When confidence is below threshold, write a question note
\\- do not guess.

## approval/new-dependency
- category: approval
- check: new_dependency_approved
Adding a runtime dependency requires explicit human approval.
"""

GOOD_TURN = TurnTrace((
    read("agent_state.json"),
    decide("use FastAPI", 0.55),
    ask("questions/web-framework.md"),
    approve("fastapi"),
    install("FastAPI"),
    approve("Python-Dateutil"),
    install("python_dateutil"),
    write("app.py"),
    ran("pytest -q", 1),
    write("app.py"),
    ran("pytest -q", 0),
))

BAD_TURN = TurnTrace((
    decide("skip the state file", 0.4),
    write("app.py"),
    write("scripts/release.sh"),
    decide("ship it", 0.9),
    install("fastapi"),
    ran("pytest -q", 1),
))


@pytest.mark.skip("Part 1")
def test_rule_report() -> None:
    """The lesson's checker: every rule is read, every check resolves, dependencies match by name."""
    rules = parse_rules(LESSON_RULES)
    report = score(rules, RuleChecker(), GOOD_TURN)
    assert report.verdict("startup/state-file-fresh") == Result(
        "startup/state-file-fresh", "startup", "block", True
    ), "the rule at the top of the file is scored"
    assert [rule.slug for rule in rules] == [rule.slug for rule in SEED], (
        "every line that starts with '## ' starts a rule, the first line of the file too"
    )
    assert rules[1].description == SEED[1].description, (
        "a description is every prose line of the rule, joined with spaces"
    )
    assert rules[3].description == (
        "When confidence is below threshold, write a question note - do not guess."
    ), "a description is every prose line of the rule, joined with spaces"
    assert [rule.severity for rule in rules] == ["block", "block", "block", "warn", "block"], (
        "severity defaults to block"
    )
    assert report.verdict("done/tests-pass").passed, "the last acceptance run decides tests_pass"

    calls: list[str] = []

    class Recording(RuleChecker):
        def state_file_fresh(self, trace: TurnTrace) -> bool:
            calls.append("state_file_fresh")
            return super().state_file_fresh(trace)

    renamed = rules + [Rule("startup/state-file-read", "startup", "state_file_read")]
    with pytest.raises(BrokenRule) as broken:
        score(renamed, Recording(), GOOD_TURN)
    assert "startup/state-file-read" in str(broken.value) and "state_file_read" in str(broken.value), (
        "BrokenRule names the rule and its check"
    )
    assert calls == [], "a check that no longer resolves stops the run before any check runs"

    assert [result.passed for result in report.results] == [True] * 5, (
        "an approval names a dependency by its PEP 503 normalized name"
    )
    mixed = TurnTrace((
        approve("zope.interface"),
        approve("python-dateutil"),
        approve("RUAMEL_YAML"),
        install("zope__interface"),
        install("Requests"),
        install("pythondateutil"),
        install("ruamel.yaml"),
    ))
    assert unapproved_dependencies(mixed) == ["Requests", "pythondateutil"], (
        "dependencies are compared by normalized name and reported as the agent wrote them"
    )
    bad = score(rules, RuleChecker(), BAD_TURN)
    assert [result.passed for result in bad.results] == [False] * 5, (
        "the lesson's bad turn breaks all five rules; its confidence is its lowest decision"
    )
    assert (bad.aggregate, report.aggregate) == ("block", "pass"), (
        "the report carries the worst severity among the failed rules"
    )

    year = [
        Rule(f"incident/{i:04d}", rule.category, rule.check, "", "warn")
        for i, rule in zip(range(2000), itertools.cycle(rules))
    ]
    noise = [read(f"src/billing/module_{i}.py") for i in range(50_000)]
    long_turn = TurnTrace(tuple(noise + [
        approve("httpx"), install("HTTPX"), ran("pytest -q", 0), read("agent_state.json"),
    ]))
    start = time.perf_counter()
    yearly = score(year, RuleChecker(), long_turn)
    elapsed = time.perf_counter() - start
    assert (len(yearly.results), yearly.aggregate) == (2000, "pass"), "every rule of the year is scored"
    assert elapsed < 0.1, "score stays fast on a year of rules and a long turn"

    checker = RuleChecker()
    first, second = score(rules, checker, GOOD_TURN), score(rules, checker, BAD_TURN)
    assert [r.passed for r in first.results + second.results] == [True] * 5 + [False] * 5, (
        "a checker keeps nothing from one turn to the next"
    )


SEED_FILE = """\
# Agent Rules

## startup/state-file-fresh
- category: startup
- check: state_file_fresh
- severity: block
Agent must read agent_state.json before any tool call.

## forbidden/no-release-script-edits
- category: forbidden
- check: no_release_script_edits
- severity: block
Never edit scripts/release.sh outside an approved release task.

## done/tests-pass
- category: definition_of_done
- check: tests_pass
- severity: block
A task is done only when its acceptance command exits zero.

## uncertainty/open-question-note
- category: uncertainty
- check: opened_question_when_unsure
- severity: warn
When confidence is below threshold, write a question note instead of guessing.

## approval/new-dependency
- category: approval
- check: new_dependency_approved
- severity: block
Adding a runtime dependency requires explicit human approval.
"""

HAND_EDITED = """\
# Agent Rules

Rules for the billing repo. New rules go at the top of their category;
delete stale rules instead of commenting them out.

## startup/state-file-fresh
- category: startup
- check: state_file_fresh
Agent must read agent_state.json
before any tool call.

## forbidden/no-release-script-edits
Never edit scripts/release.sh outside an approved release task.
- category: forbidden
- check: no_release_script_edits

## done/tests-pass-fast
- category: definition_of_done
- check: tests_pass
- severity: warn
The fast suite passes before every push.

## done/tests-pass
- category: definition_of_done
- check: tests_pass
A task is done only when its acceptance command exits zero.


## approval/new-dependency
- category: approval
- check: new_dependency_approved
Adding a runtime dependency requires explicit human approval.
"""

LOCKFILE = Rule("forbidden/no-lockfile-edits", "forbidden", "no_lockfile_edits",
                "Never hand-edit poetry.lock.")


def change(before: str, after: str) -> tuple[list[str], list[str]]:
    """The one run of lines that differs between two texts: (lines taken out, lines put in)."""
    a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
    head = 0
    while head < min(len(a), len(b)) and a[head] == b[head]:
        head += 1
    tail = 0
    while tail < min(len(a), len(b)) - head and a[len(a) - 1 - tail] == b[len(b) - 1 - tail]:
        tail += 1
    return a[head:len(a) - tail], b[head:len(b) - tail]


@pytest.mark.skip("Part 2")
def test_rule_file(tmp_path) -> None:
    """agent-rules.md reads back exactly, and every edit is one block in a diff."""
    assert write_rules(SEED) == SEED_FILE, "one block per rule, every field written, in the documented layout"
    newer = Rule("startup/tool-versions", "startup", "tool_versions_pinned", "Pin tool versions first.")
    headings = [line for line in write_rules([SEED[4], SEED[3], newer, SEED[0], SEED[2], SEED[1]]).splitlines()
                if line.startswith("## ")]
    assert headings == [f"## {rule.slug}" for rule in (newer, *SEED)], (
        "rules are grouped by category in a fixed order and keep their order inside it"
    )

    tricky = [
        Rule("startup/windows-share", "startup", "state_file_fresh", "\\\\build\\releases is read-only."),
        Rule("forbidden/heading-text", "forbidden", "no_release_script_edits", "## approval/always-ok"),
        Rule("forbidden/field-text", "forbidden", "no_release_script_edits", "- check: always_ok", "info"),
        Rule("forbidden/terse-field", "forbidden", "no_release_script_edits", "-check:always_ok"),
        Rule("done/plain-text", "definition_of_done", "tests_pass", "#1 cause of rework: a red build, ## twice"),
        Rule("done/lint-first", "definition_of_done", "tests_pass", "- check: run the linter before you push."),
        Rule("done/token-paste", "definition_of_done", "tests_pass",
             "##__VA_ARGS__ is a GNU extension.  Keep the macros portable."),
        Rule("uncertainty/silent", "uncertainty", "opened_question_when_unsure", "", "warn"),
        Rule("approval/unicode", "approval", "new_dependency_approved", "新しい依存関係には承認が必要 — ✓"),
    ]
    path = tmp_path / "docs" / "agent-rules.md"
    path.parent.mkdir()
    path.write_text(write_rules(tricky), encoding="utf-8")
    assert parse_rules(path.read_text(encoding="utf-8")) == tricky, (
        "every rule reads back exactly, whatever its description looks like"
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.startswith("\\")] == [
        "\\\\\\build\\releases is read-only.",
        "\\## approval/always-ok",
        "\\- check: always_ok",
        "\\-check:always_ok",
    ] and {
        "#1 cause of rework: a red build, ## twice",
        "- check: run the linter before you push.",
        "##__VA_ARGS__ is a GNU extension.  Keep the macros portable.",
    } <= set(lines), "only a description line that would read back differently gets a backslash"
    silent = lines.index("## uncertainty/silent")
    assert lines[silent + 3:silent + 6] == ["- severity: warn", "", "## approval/unicode"], (
        "a rule without a description has no description line"
    )

    def rejected(rules: list[Rule]) -> bool:
        try:
            write_rules(rules)
        except ValueError:
            return True
        return False

    for why, rule in (
        ("a description with a line break", Rule("done/two-lines", "definition_of_done", "tests_pass", "one\ntwo")),
        ("a description with a line separator", Rule("done/ls", "definition_of_done", "tests_pass", "one\u2028two")),
        ("a description with a form feed", Rule("done/ff", "definition_of_done", "tests_pass", "one\x0ctwo")),
        ("a description with leading whitespace", Rule("done/lead", "definition_of_done", "tests_pass", " padded")),
        ("a description with trailing whitespace", Rule("done/trail", "definition_of_done", "tests_pass", "padded\t")),
        ("a slug with whitespace", Rule("done/two words", "definition_of_done", "tests_pass")),
        ("an empty slug", Rule("", "definition_of_done", "tests_pass")),
        ("an unknown category", Rule("style/pep8", "style", "tests_pass")),
        ("an unknown severity", Rule("done/loud", "definition_of_done", "tests_pass", "", "fatal")),
        ("a check that is not an identifier", Rule("done/dash", "definition_of_done", "tests-pass")),
        ("two rules with one slug", SEED[0]),
    ):
        assert rejected([SEED[0], rule]), f"write_rules rejects {why}"

    assert add_rule(SEED_FILE, LOCKFILE) == write_rules([SEED[0], LOCKFILE, *SEED[1:]]), (
        "a new rule goes at the top of its category"
    )
    assert add_rule(SEED_FILE, tricky[1]) == write_rules([SEED[0], tricky[1], *SEED[1:]]), (
        "the new block is written the way write_rules writes it"
    )
    without_unsure = write_rules([*SEED[:3], SEED[4]])
    assert add_rule(without_unsure, SEED[3]) == SEED_FILE and add_rule(
        write_rules(SEED[:4]), SEED[4]
    ) == SEED_FILE, "a rule of an empty category goes where its category starts"
    assert write_rules([]) == "# Agent Rules\n" and add_rule("# Agent Rules\n", SEED[0]) == write_rules(SEED[:1]), (
        "a file without rules is the title line alone"
    )
    assert remove_rule(SEED_FILE, "done/tests-pass") == write_rules([*SEED[:2], *SEED[3:]]), (
        "removing a rule takes its whole block"
    )
    assert remove_rule(SEED_FILE, "approval/new-dependency") == write_rules(SEED[:4]) and remove_rule(
        write_rules(SEED[:1]), SEED[0].slug
    ) == "# Agent Rules\n", "removing the last rule takes the blank line before it too"

    hand = parse_rules(HAND_EDITED)
    after = add_rule(HAND_EDITED, LOCKFILE)
    assert change(HAND_EDITED, after) == ([], [
        "## forbidden/no-lockfile-edits\n",
        "- category: forbidden\n",
        "- check: no_lockfile_edits\n",
        "- severity: block\n",
        "Never hand-edit poetry.lock.\n",
        "\n",
    ]), "adding a rule adds one block and changes nothing else in the file"
    assert parse_rules(after) == [hand[0], LOCKFILE, *hand[1:]], "a new rule goes at the top of its category"
    unsure = add_rule(HAND_EDITED, SEED[3])
    assert change(HAND_EDITED, unsure)[0] == [] and parse_rules(unsure) == [*hand[:4], SEED[3], hand[4]], (
        "a rule of an empty category goes where its category starts"
    )
    prefixed = Rule("done/tests", "definition_of_done", "tests_pass", "Some tests ran.")
    assert parse_rules(add_rule(HAND_EDITED, prefixed)) == [*hand[:2], prefixed, *hand[2:]], (
        "a slug is a whole heading, not a prefix of one"
    )
    with pytest.raises(ValueError):
        add_rule(HAND_EDITED, Rule("done/tests-pass", "definition_of_done", "tests_pass"))
    with pytest.raises(ValueError):
        add_rule(HAND_EDITED, Rule("done/padded", "definition_of_done", "tests_pass", "padded "))

    assert change(HAND_EDITED, remove_rule(HAND_EDITED, "done/tests-pass")) == ([
        "## done/tests-pass\n",
        "- category: definition_of_done\n",
        "- check: tests_pass\n",
        "A task is done only when its acceptance command exits zero.\n",
        "\n",
        "\n",
    ], []), "removing a rule deletes its block, the one with exactly that slug, and nothing else"
    assert change(HAND_EDITED, remove_rule(HAND_EDITED, "approval/new-dependency")) == ([
        "\n",
        "\n",
        "## approval/new-dependency\n",
        "- category: approval\n",
        "- check: new_dependency_approved\n",
        "Adding a runtime dependency requires explicit human approval.\n",
    ], []), "removing the last rule takes the blank lines before it too"
    with pytest.raises(KeyError):
        remove_rule(HAND_EDITED, "uncertainty/open-question-note")


class RepoWatch(Watch):
    def rules_read(self, event: Event) -> bool:
        return event.kind == "read" and event.subject == "docs/agent-rules.md"

    def no_lockfile_edits(self, event: Event) -> bool:
        return event.kind == "write" and event.subject == "poetry.lock"


RULES_READ = Rule("startup/rules-read", "startup", "rules_read", "Read docs/agent-rules.md first.")

TURN = [
    decide("start from the failing test", 0.9),
    read("docs/agent-rules.md"),
    read("agent_state.json"),
    read("app.py"),
    ask("questions/framework.md"),
    decide("use FastAPI", 0.6),
    decide("keep the old router", 0.65),
    approve("fastapi"),
    install("FastAPI"),
    install("uvicorn"),
    approve("uvicorn"),
    ran("pytest -q", 1),
    write("app.py"),
    ran("pytest -q", 0),
    write("poetry.lock"),
]


def verdict(rule: Rule, events: list[Event], **options) -> tuple[bool, int | None]:
    (only,) = judge([rule], events, **options)
    return only.passed, only.at


@pytest.mark.skip("Part 3")
def test_turn_judgement() -> None:
    """Each category reads the ordered events its own way; a verdict names the event that broke the rule."""
    assert judge([*SEED, RULES_READ, LOCKFILE], TURN, RepoWatch()) == [
        Verdict("startup/state-file-fresh", True),
        Verdict("forbidden/no-release-script-edits", True),
        Verdict("done/tests-pass", False, 14),
        Verdict("uncertainty/open-question-note", False, 6),
        Verdict("approval/new-dependency", False, 9),
        Verdict("startup/rules-read", True),
        Verdict("forbidden/no-lockfile-edits", False, 14),
    ], "each category reads the turn its own way"
    assert judge(SEED, TURN)[0] == Verdict("startup/state-file-fresh", False, 1), (
        "work starts at the first tool call that no startup rule watches"
    )
    assert judge(SEED, [install("fastapi"), read("agent_state.json")])[0] == Verdict(
        "startup/state-file-fresh", False, 0
    ), "a tool call another category watches still starts work"

    def startup(events: list[Event]) -> list[tuple[bool, int | None]]:
        return [(v.passed, v.at) for v in judge([SEED[0], RULES_READ], events, RepoWatch())]

    assert startup([read("README.md"), read("agent_state.json"), read("docs/agent-rules.md")]) == [
        (False, 0), (False, 0),
    ], "reading the state file after the first tool call is too late"
    assert startup([
        approve("fastapi"), decide("plan", 0.9), read("agent_state.json"), read("docs/agent-rules.md"),
        write("app.py"),
    ]) == [(True, None), (True, None)], "decisions and approvals are not tool calls"
    assert startup([read("agent_state.json"), ask(), read("docs/agent-rules.md")]) == [
        (True, None), (False, 1),
    ], "opening a question note is a tool call"
    assert startup([decide("nothing to do", 0.95)]) == [(True, None), (True, None)], (
        "a turn that calls no tool never starts work"
    )

    assert verdict(SEED[1], [
        read("scripts/release.sh"), write("app.py"), write("scripts/release.sh"), write("scripts/release.sh"),
    ]) == (False, 2), "a forbidden rule fails at the first event it watches"

    for events, expected, why in (
        ([], (False, None), "no acceptance run is no proof"),
        ([ran("pytest -q", 0), ran("pytest -q", 1)], (False, 1), "the last acceptance run is the proof"),
        ([ran("pytest -q", 1), write("app.py"), ran("pytest -q", 0)], (True, None),
         "the last acceptance run is the proof"),
        ([ran("pytest -q", 0), ran("ruff check .", 1)], (True, None), "only the acceptance command proves anything"),
        ([ran("pytest -q", 1), write("app.py")], (False, 0), "a failed proof fails at its run"),
        ([write("app.py"), ran("pytest -q", 0), install("requests"), write("app.py")], (False, 2),
         "a write or install after the proof makes it stale"),
        ([ran("pytest -q", 0), ask(), decide("ship", 0.9), approve("httpx"), read("app.py")], (True, None),
         "notes, decisions, approvals and reads change nothing"),
    ):
        assert verdict(SEED[2], events) == expected, why

    for events, expected, why in (
        ([decide("a", 0.7)], (True, None), "0.7 is not below a 0.7 threshold"),
        ([decide("a", 0.69)], (False, 0), "a decision below the threshold needs a question note"),
        ([decide("a", 0.3), ask()], (False, 0), "the note comes before the decision"),
        ([ask(), decide("a", 0.3), decide("b", 0.2)], (False, 2), "one note covers one decision"),
        ([ask(), decide("a", 0.9), decide("b", 0.3)], (False, 2), "the note comes after the previous decision"),
        ([ask(), decide("a", 0.3), decide("b", 0.95), ask(), ask(), decide("c", 0.1)], (True, None),
         "every unsure decision had its own note"),
        ([decide("a", 0.9), ask(), read("app.py"), write("app.py"), decide("b", 0.3)], (True, None),
         "the note may come any time after the previous decision"),
    ):
        assert verdict(SEED[3], events) == expected, why
    assert verdict(SEED[3], [decide("a", 0.6)], threshold=0.5) == (True, None), "the threshold is a parameter"

    for events, expected, why in (
        ([install("requests"), approve("requests")], (False, 0), "an approval after the install is too late"),
        ([approve("httpx"), install("requests")], (False, 1), "an approval names one package"),
        ([approve("Requests"), install("requests"), install("REQUESTS")], (True, None),
         "one approval covers its package, however it is written"),
        ([approve("httpx"), approve("Requests"), install("httpx"), install("requests")], (True, None),
         "every earlier approval counts, not only the latest"),
        ([approve("python-dateutil"), install("Python_DateUtil")], (True, None),
         "names compare the way Part 1's normalize compares them"),
    ):
        assert verdict(SEED[4], events) == expected, why

    with pytest.raises(BrokenRule):
        judge([SEED[0], RULES_READ], [read("agent_state.json")])
    with pytest.raises(BrokenRule):
        judge([Rule("style/pep8", "style", "tests_pass")], [ran("pytest -q", 0)])


def enforce(runtime: Runtime, events: list[Event]) -> list[tuple[int, str]]:
    """Feed events one at a time; each line comes with the number of events pulled so far."""
    pulled: list[int] = []

    async def source():
        for i, event in enumerate(events):
            pulled.append(i)
            yield event

    async def collect() -> list[tuple[int, str]]:
        return [(len(pulled), line) async for line in runtime.run(source())]

    return asyncio.run(asyncio.wait_for(collect(), 3.0))


def tap(received: list[tuple[int, str]]) -> list[str]:
    rows = "".join(line for _, line in received).split("\n")
    assert rows.pop() == "", "every line ends with a newline"
    return rows


LIVE = [
    decide("start", 0.9),
    write("scripts/release.sh"),
    read("agent_state.json"),
    write("app.py"),
    decide("drop the cache", 0.5),
    install("FastAPI"),
    approve("fastapi"),
    install("FastAPI"),
    ran("pytest -q", 0),
    write("scripts/release.sh"),
    install("uvicorn"),
]


@pytest.mark.skip("Part 4")
def test_runtime_tap() -> None:
    """The runtime refuses what breaks a block rule and reports every rule as TAP as soon as it can."""
    runtime = Runtime(SEED)
    received = enforce(runtime, LIVE)
    assert tap(received) == [
        "not ok 1 - startup/state-file-fresh # event 1 refused",
        "not ok 2 - forbidden/no-release-script-edits # event 1 refused",
        "not ok 3 - uncertainty/open-question-note # event 4",
        "not ok 4 - approval/new-dependency # event 5 refused",
        "ok 5 - done/tests-pass",
        "1..5",
    ], "one line per rule as soon as its verdict is known, numbered in output order, then the plan"
    assert [count for count, _ in received] == [2, 2, 5, 6, 11, 11], (
        "a broken rule is reported the moment its event arrives"
    )
    assert runtime.record == [LIVE[i] for i in (0, 2, 3, 4, 6, 7, 8)], (
        "refused events stay out of the record; what breaks only a warn rule goes through"
    )

    again = Runtime(SEED)
    assert tap(enforce(again, [
        ran("pytest -q", 0), write("notes.md"), write("notes.md"), read("agent_state.json"), write("notes.md"),
    ])) == [
        "not ok 1 - startup/state-file-fresh # event 0 refused",
        "ok 2 - forbidden/no-release-script-edits",
        "not ok 3 - done/tests-pass # end of turn",
        "ok 4 - uncertainty/open-question-note",
        "ok 5 - approval/new-dependency",
        "1..5",
    ], "rules still open when the stream ends are reported then, in rule order"
    assert again.record == [read("agent_state.json"), write("notes.md")], (
        "a refused tool call does not start work: the runtime refuses until the state file is read"
    )

    lockfile = Rule("forbidden/no-lockfile-edits", "forbidden", "no_lockfile_edits", "", "warn")
    watchful = Runtime([SEED[0], lockfile, SEED[2]], RepoWatch())
    received = enforce(watchful, [read("agent_state.json"), ran("pytest -q", 0), write("poetry.lock"), write("app.py")])
    assert [count for count, _ in received] == [1, 3, 4, 4], (
        "a startup rule is reported as soon as its event is let through"
    )
    assert tap(received) == [
        "ok 1 - startup/state-file-fresh",
        "not ok 2 - forbidden/no-lockfile-edits # event 2",
        "not ok 3 - done/tests-pass # event 2",
        "1..3",
    ], "a warn rule reports its break and lets the event through, so the proof goes stale"

    assert tap(enforce(Runtime(SEED), [])) == [
        "ok 1 - startup/state-file-fresh",
        "ok 2 - forbidden/no-release-script-edits",
        "not ok 3 - done/tests-pass # end of turn",
        "ok 4 - uncertainty/open-question-note",
        "ok 5 - approval/new-dependency",
        "1..5",
    ], "an empty turn still gets a line per rule and the plan"
    late = [read("agent_state.json"), write("scripts/release.sh"), ran("pytest -q", 1)]
    assert tap(enforce(Runtime(SEED), late)) == [
        "ok 1 - startup/state-file-fresh",
        "not ok 2 - forbidden/no-release-script-edits # event 1 refused",
        "not ok 3 - done/tests-pass # event 2",
        "ok 4 - uncertainty/open-question-note",
        "ok 5 - approval/new-dependency",
        "1..5",
    ], "a line reported at the end names its event by its place in the stream, refused events counted"
    retried = [read("agent_state.json"), ran("pytest -q", 1), write("app.py"), ran("pytest -q", 0)]
    assert tap(enforce(Runtime([SEED[0], SEED[2]]), retried)) == [
        "ok 1 - startup/state-file-fresh",
        "ok 2 - done/tests-pass",
        "1..2",
    ], "the last proof decides: a newer passing run replaces a stale or failed one"
    assert tap(enforce(Runtime([SEED[1], SEED[0]]), [write("scripts/release.sh")])) == [
        "not ok 1 - forbidden/no-release-script-edits # event 0 refused",
        "not ok 2 - startup/state-file-fresh # event 0 refused",
        "1..2",
    ], "lines that come out on the same event follow rule order"
    assert tap(enforce(Runtime([SEED[3]], threshold=0.5), [decide("cache it", 0.6)])) == [
        "ok 1 - uncertainty/open-question-note",
        "1..1",
    ], "the threshold is a parameter"
    with pytest.raises(BrokenRule):
        Runtime([SEED[0], lockfile])


REPO = {
    "AGENTS.md": """\
# AGENTS.md

Billing service. This file is a map: read it every session, then follow a link.

## Start here

1. Read `agent_state.json` before any tool call; the [startup rules](docs/agent-rules.startup.md) say why.
2. Writing or running tests? Read [testing](docs/testing.md) first.

## Hard rules

- [Read the state file first](docs/agent-rules.md#startup/state-file-fresh)
- [Never edit scripts/release.sh](docs/agent-rules.forbidden.md#forbidden/no-release-script-edits)
- [Done means `pytest -q` exits 0](docs/agent-rules.done.md#done/tests-pass)
- Unsure? Write a question note; docs/agent-rules.uncertainty.md has the details.
- New dependencies need a human approval.

## Where to look

- [All rules, by category](docs/agent-rules.md)
- [Architecture](docs/architecure.md), when the task touches module boundaries.
- Release work: see docs/deploy.md, and only with an approval.
- Link a rule as `[slug](docs/agent-rules.md#<slug>)`: by path, never by description.
- Changelog style: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

```
AGENTS.md             this router, under 50 lines
docs/agent-rules.md   the rule index
docs/<topic>.md       read when the task touches the topic
```
""",
    "docs/agent-rules.md": """\
# Agent Rules

The rule set is split by category, one file each. New rules go at the top of their file.

- [Startup](agent-rules.startup.md)
- [Forbidden](agent-rules.forbidden.md)
- [Definition of done](agent-rules.done.md)
- [Uncertainty](agent-rules.uncertainty.md)
- [Release and deploy](deploy.md), which links the approval rules.

Back to the [router](../AGENTS.md).
""",
    "docs/agent-rules.startup.md": """\
## startup/state-file-fresh
- category: startup
- check: state_file_fresh
Agent must read agent_state.json before any tool call.

## startup/rules-read
- category: startup
- check: rules_read
Read docs/agent-rules.md before the first write, like the [state file](#startup/state-file-read).
""",
    "docs/agent-rules.forbidden.md": """\
## forbidden/no-release-script-edits
- category: forbidden
- check: no_release_script_edits
Never edit scripts/release.sh outside an approved release task.
""",
    "docs/agent-rules.done.md": """\
## done/tests-pass
- category: definition_of_done
- check: tests_pass
A task is done only when its acceptance command exits zero.
""",
    "docs/agent-rules.uncertainty.md": """\
## uncertainty/open-question-note
- category: uncertainty
- check: opened_question_when_unsure
- severity: warn
When confidence is below threshold, write a question note instead of guessing.
""",
    "docs/agent-rules.approval.md": """\
## approval/new-dependency
- category: approval
- check: new_dependency_approved
Adding a runtime dependency requires explicit human approval.

## approval/prod-write
- category: approval
- check: prod_write_approved
Any write to production needs a human approval first, as [dependencies](#approval/new-dependency) do;
see [deploy](deploy.md#approvals).
""",
    "docs/deploy.md": """\
# Deploy

Release work only. Every step needs an approval: [approval rules](agent-rules.approval.md#approval/prod-writes).

1. Tag the release.
2. Run `scripts/release.sh`.
""",
    "docs/testing.md": """\
# Testing

Run `pytest -q`. The [definition of done](agent-rules.done.md) says when a task is finished.
Module boundaries are in [architecture](architecture.md); shared data lives in [fixtures](fixtures.md).
""",
    "docs/architecture.md": """\
# Architecture

Billing talks to the ledger through one module. When a boundary is unclear, follow the
[uncertainty rules](agent-rules.uncertainty.md) and read [ADR 1](adr/0001-split-rules.md).
Terms are in the company [glossary](../../shared/glossary.md).
""",
    "docs/adr/0001-split-rules.md": """\
# ADR 1: split the rule file

The rule file passed 200 lines, so it is split by category behind an index.
""",
    "legacy/agent-rules.old.md": """\
# Old rules

## forbidden/no-prod-db
- category: forbidden
- check: no_prod_db_writes
Never connect to the production database; the [runbook](../runbooks/prod-db.md) says why.
""",
}


def plant(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.mark.skip("Part 5")
def test_router_reachability(tmp_path) -> None:
    """Every rule is within two links of the router, which links each topic doc and holds no dead pointer."""
    plant(tmp_path, {"shared/glossary.md": "# Glossary\n"})
    report = audit_router(plant(tmp_path / "repo", REPO))
    assert report.hops == {
        "startup/state-file-fresh": 1,
        "startup/rules-read": 1,
        "forbidden/no-release-script-edits": 1,
        "done/tests-pass": 1,
        "uncertainty/open-question-note": 2,
        "approval/new-dependency": 3,
        "approval/prod-write": 3,
    }, "a rule is as many links away as its file: the fewest links from the router, each relative to its own file"
    assert report.too_deep == ["approval/new-dependency", "approval/prod-write"], (
        "rules more than two links from the router are too deep"
    )
    assert report.unreachable == ["forbidden/no-prod-db"], "a rule file that nothing links to is unreachable"
    assert report.unlinked == ["docs/architecture.md", "docs/deploy.md"], (
        "the router links every topic doc itself, by path; prose and inline code are not links"
    )
    assert report.broken == [
        ("AGENTS.md", "docs/agent-rules.md#startup/state-file-fresh"),
        ("AGENTS.md", "docs/architecure.md"),
        ("docs/agent-rules.startup.md", "#startup/state-file-read"),
        ("docs/architecture.md", "../../shared/glossary.md"),
        ("docs/deploy.md", "agent-rules.approval.md#approval/prod-writes"),
        ("docs/testing.md", "fixtures.md"),
    ], "a link the router's walk meets is broken when its path (inside the repo) or its anchor into a rule file does not resolve"
    assert report.startup_violations == ["docs/agent-rules.md#startup/state-file-fresh", "docs/architecure.md"], (
        "a broken link in the router is a startup violation"
    )
    assert isinstance(report, RouterReport) and (report.lines, report.over_budget) == (30, False), (
        "the router's line count, under its 50-line budget"
    )

    for lines, ending, over in ((49, "\n", False), (49, "", False), (50, "\n", True)):
        router = "\n".join(f"- line {i}" for i in range(lines)) + ending
        small = audit_router(plant(tmp_path / f"r{lines}{len(ending)}", {"AGENTS.md": router}))
        assert (small.lines, small.over_budget) == (lines, over), (
            f"a {lines}-line router {'with' if ending else 'without'} a final newline"
        )
