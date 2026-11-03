import asyncio
import json
import re
import time

import pytest
from skillpack.contract import name_issue
from skillpack.frontmatter import parse_frontmatter
from skillpack.lifecycle import tap_report
from skillpack.validate import validate_skill_text
from skillpack.workflow import workflow_report
from skillpack.writer import render_skill


def raises(error, action, *args, **kwargs) -> bool:
    try:
        action(*args, **kwargs)
    except error:
        return True
    return False


# The lesson's release-readiness skill, with the optional portable fields filled in.
RELEASE_SKILL = (
    "---\n"
    "name: release-readiness\n"
    "description: >\n"
    "  Inspect a release candidate when the user\n"
    "  asks whether a version is ready to publish.\n"
    "license: MIT\n"
    "# optional portable fields\n"
    "compatibility: Requires git and python3.\n"
    "metadata:\n"
    "  owner: release-eng\n"
    '  lesson: "22"\n'
    "allowed-tools: Bash(git:*) Read\n"
    "---\n"
    "# Release readiness\n"
    "\n"
    "Use this workflow for a release candidate, not for ordinary development builds.\n"
    "\n"
    "1. Read `references/release-policy.md`.\n"
    "2. Run `python3 scripts/inspect_release.py --format json`.\n"
    "3. Stop if the report contains a blocking failure.\n"
    "4. Produce the checklist from `assets/release-checklist.md`.\n"
    "5. Ask for approval before any publish or tag action.\n"
    "\n"
    "---\n"
    "\n"
    "Note: the checklist template lives in assets/.\n"
)
RELEASE_FIELDS = {
    "name": "release-readiness",
    "description": "Inspect a release candidate when the user asks whether a version is ready to publish.",
    "license": "MIT",
    "compatibility": "Requires git and python3.",
    "metadata": {"owner": "release-eng", "lesson": "22"},
    "allowed-tools": "Bash(git:*) Read",
}
RELEASE_BODY = RELEASE_SKILL.split("---\n", 2)[2]


@pytest.mark.skip("Part 1")
def test_frontmatter_and_names() -> None:
    """SKILL.md reads the same wherever it was saved, names follow the spec, and big files parse fast."""
    assert parse_frontmatter(RELEASE_SKILL) == (RELEASE_FIELDS, RELEASE_BODY), (
        "the lesson's YAML subset: a folded block, a comment, a metadata map; the body after the closing line"
    )
    fields, body = parse_frontmatter(RELEASE_SKILL.replace("\n", "\r\n"))
    assert fields == RELEASE_FIELDS, "a SKILL.md saved with Windows line endings has the same frontmatter"
    assert body.startswith("# Release readiness"), "the body starts right after the closing line"

    quoted = parse_frontmatter(
        "---\n"
        "name: release-readiness\n"
        "description: 'Use when someone asks: ''is this version ready to publish?'''\n"
        "metadata:\n"
        "  motto: 'don''t tag on a Friday'\n"
        "  empty: ''\n"
        "---\n"
        "Check the release.\n"
    )[0]
    assert (quoted["description"], quoted["metadata"]) == (
        "Use when someone asks: 'is this version ready to publish?'",
        {"motto": "don't tag on a Friday", "empty": ""},
    ), "inside single quotes, '' stands for one '"

    for bad in ("-release", "release-", "release--readiness", "Release-Readiness", "release_readiness",
                "release readiness", "café-notes", "release-readiness\n"):
        issue = name_issue(bad, bad)
        assert issue is not None and issue.code == "name-format", (
            f"a name is lowercase letters and digits joined by single hyphens: {bad!r}"
        )
    for good in ("release-readiness", "skill-contract-reviewer", "2fa-helper", "v2", "a", "x" * 64):
        assert name_issue(good, good) is None, f"a valid name: {good!r}"
    issue = name_issue("release-readiness", "Release-Readiness")
    assert issue is not None and issue.code == "directory-mismatch", "a name must match its directory exactly"

    last = "---\nname: release-readiness\ndescription: Inspect a release.\n---"
    assert parse_frontmatter(last) == ({"name": "release-readiness", "description": "Inspect a release."}, ""), (
        "the closing line can be the last line of the file"
    )

    log = "".join(f"{i:06d}. Record the check result in the release log.\n" for i in range(50_000))  # 2.6 MB
    start = time.perf_counter()
    fields, body = parse_frontmatter(RELEASE_SKILL + log)
    elapsed = time.perf_counter() - start
    assert (fields, body) == (RELEASE_FIELDS, RELEASE_BODY + log), "a long body is kept whole"
    assert elapsed < 0.1, "parsing a large SKILL.md should be fast"


# The lesson's bundled skill, outputs/skill-contract-reviewer/SKILL.md, with its body shortened.
REVIEWER_SKILL = (
    "---\n"
    "name: skill-contract-reviewer\n"
    "description: Validate an Agent Skill package and choose the right instruction, capability, or lifecycle"
    " primitive before implementation.\n"
    "license: MIT\n"
    "metadata:\n"
    '  lesson: "22"\n'
    "---\n"
    "\n"
    "# Skill contract reviewer\n"
    "\n"
    "Use this skill when a workflow is about to become a reusable agent artifact.\n"
)

# A description, and how render_skill writes it.
SCALARS = [
    ("Inspect a release candidate.", "Inspect a release candidate."),
    ("C# release notes, v2.0 (draft)", "C# release notes, v2.0 (draft)"),
    ("Bash(git:*) Read", "Bash(git:*) Read"),
    ('Say "ship it" to start', 'Say "ship it" to start'),
    ("Yesterday's null results", "Yesterday's null results"),
    ("naïve café 東京", "naïve café 東京"),
    ("Use when: a version is tagged", '"Use when: a version is tagged"'),
    ("Use when: 東京 asks", '"Use when: 東京 asks"'),
    ("Ship it #now", '"Ship it #now"'),
    ("Ends with a colon:", '"Ends with a colon:"'),
    ("[draft] release notes", '"[draft] release notes"'),
    ("] closing", '"] closing"'),
    ("} closing", '"} closing"'),
    (", and more", '", and more"'),
    ("{name} notes", '"{name} notes"'),
    ("&anchor", '"&anchor"'),
    ("*", '"*"'),
    ("!important", '"!important"'),
    ("# heading", '"# heading"'),
    ("- item", '"- item"'),
    ("? key", '"? key"'),
    ("@here", '"@here"'),
    ("% done", '"% done"'),
    ("`code` first", '"`code` first"'),
    ("'single' first", "\"'single' first\""),
    ('"double" first', '"\\"double\\" first"'),
    ("|", '"|"'),
    (">", '">"'),
    (" padded", '" padded"'),
    ("padded ", '"padded "'),
    ("", '""'),
    ("tab\tinside", '"tab\\tinside"'),
    ("zero\u200bwidth", '"zero\u200bwidth"'),
    ("22", '"22"'),
    ("1.0", '"1.0"'),
    ("2026-10-30", '"2026-10-30"'),
    (".5", '".5"'),
    ("+1", '"+1"'),
    ("~", '"~"'),
    ("true", '"true"'),
    ("No", '"No"'),
    ("NULL", '"NULL"'),
    ("off", '"off"'),
]


@pytest.mark.skip("Part 2")
def test_skill_file_roundtrip(tmp_path) -> None:
    """A skill written as SKILL.md reads back exactly, and YAML hosts read it the same way."""
    assert render_skill(*parse_frontmatter(REVIEWER_SKILL)) == REVIEWER_SKILL, (
        "the lesson's own SKILL.md comes back byte for byte"
    )

    fields = {
        "name": "release-readiness",
        "description": "Use when: a maintainer asks whether a version is ready to publish.",
        "license": "MIT",
        "compatibility": "Requires git and python3.",
        "metadata": {"owner": "release-eng", "lesson": "22", "reviewed": "2026-10-30"},
        "allowed-tools": "Bash(git:*) Read",
        "user-invocable": "false",
    }
    body = "\n# Release readiness\n\n---\n\nname: not a field\n  kept as written   \nno final newline"
    text = render_skill(fields, body)
    assert text == (
        "---\n"
        "name: release-readiness\n"
        'description: "Use when: a maintainer asks whether a version is ready to publish."\n'
        "license: MIT\n"
        "compatibility: Requires git and python3.\n"
        "metadata:\n"
        "  owner: release-eng\n"
        '  lesson: "22"\n'
        '  reviewed: "2026-10-30"\n'
        "allowed-tools: Bash(git:*) Read\n"
        "user-invocable: false\n"
        "---\n" + body
    ), "quote only what YAML would read differently; metadata values stay strings"
    path = tmp_path / "release-readiness" / "SKILL.md"
    path.parent.mkdir()
    path.write_bytes(text.encode("utf-8"))
    back = parse_frontmatter(path.read_bytes().decode("utf-8"))
    assert back == (fields, body), "a skill must round-trip exactly"
    assert list(back[0]) == list(fields), "fields keep their order"

    for value, written in SCALARS:
        text = render_skill({"name": "release-notes", "description": value}, "Draft the notes.\n")
        assert text == f"---\nname: release-notes\ndescription: {written}\n---\nDraft the notes.\n", (
            f"plain unless YAML would read the value differently: {value!r}"
        )
        assert parse_frontmatter(text) == ({"name": "release-notes", "description": value}, "Draft the notes.\n"), (
            f"a value must round-trip exactly: {value!r}"
        )

    host = {
        "name": "release-notes",
        "description": "Draft release notes.",
        "disable-model-invocation": "true",
        "metadata": {"public": "true", "build": "1042"},
    }
    assert render_skill(host, "") == (
        "---\nname: release-notes\ndescription: Draft release notes.\ndisable-model-invocation: true\n"
        'metadata:\n  public: "true"\n  build: "1042"\n---\n'
    ), "a runtime extension keeps its host's YAML type; a metadata value stays a string"

    steps = "Inspect a release candidate.\n\nUse it when a maintainer asks whether a version is ready."
    text = render_skill({"name": "release-notes", "description": steps}, "")
    assert text == (
        "---\nname: release-notes\ndescription: |\n  Inspect a release candidate.\n\n"
        "  Use it when a maintainer asks whether a version is ready.\n---\n"
    ), "a value with line breaks becomes a | block"
    assert parse_frontmatter(text)[0]["description"] == steps, "a | block must round-trip exactly"
    for value in ("First line.\n  indented second line.", "Ends with a line break.\n", "\nStarts with a line break.",
                  "A Windows\r\nline break.", "A tab\tin the first line.\nSecond line."):
        text = render_skill({"name": "release-notes", "description": value}, "")
        assert f"description: {json.dumps(value, ensure_ascii=False)}\n" in text, (
            f"a value a | block would change is double-quoted: {value!r}"
        )
        assert parse_frontmatter(text)[0]["description"] == value, f"a value must round-trip exactly: {value!r}"
    note = {"name": "release-notes", "metadata": {"note": "two\nlines"}}
    assert render_skill(note, "") == '---\nname: release-notes\nmetadata:\n  note: "two\\nlines"\n---\n', (
        "a metadata value is never a block"
    )

    for bad in (
        {"name": "release-notes", "allowed_tools": "Read"},
        {"name": "release-notes", "allowed-tools": ["Read", "Grep"]},
        {"name": "release-notes", "metadata": {"owner": {"team": "release-eng"}}},
        {"name": "release-notes", "owner": {"team": "release-eng"}},
        {"name": "release-notes", "metadata": {"lesson": 22}},
        {"name": "release-notes", "metadata": {"build id": "1042"}},
        {"name": "release-notes", "metadata": {}},
        {"name": "release-notes", "description": None},
    ):
        assert raises(ValueError, render_skill, bad, ""), f"only what the subset can hold is written: {bad}"


def skill_md(*lines: str, body: str = "Run the read-only checks.\n") -> str:
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n" + body


def codes(report) -> list[str]:
    return [issue.code for issue in report.issues]


# The demo package from the lesson's code/main.py.
PORTABLE = (
    "---\n"
    "name: incident-summary\n"
    "description: Summarize an incident timeline when the user supplies event notes.\n"
    "metadata:\n"
    "  owner: reliability\n"
    "---\n"
    "\n"
    "# Incident summary\n"
    "\n"
    "Preserve timestamps and separate observations from inferences.\n"
)


@pytest.mark.skip("Part 3")
def test_validation_order() -> None:
    """A package is checked cheapest rule first, and every issue code comes in a fixed order."""
    report = validate_skill_text(PORTABLE, "incident-summary")
    assert report.valid and codes(report) == [], "the lesson's portable demo package is valid"
    assert (report.name, report.core_fields, report.runtime_extensions) == (
        "incident-summary", ("description", "metadata", "name"), ()
    ), "the report names the fields present, sorted"
    assert report.body == PORTABLE.split("---\n", 2)[2], "the report keeps the body as written"

    host = PORTABLE.replace("description:", "user-invocable: true\ndescription:", 1)
    portable = validate_skill_text(host, "incident-summary")
    assert (portable.valid, codes(portable), portable.runtime_extensions) == (
        False, ["unsupported-runtime-field"], ("user-invocable",)
    ), "a host field outside the portable core needs the host's say-so"
    adapted = validate_skill_text(host, "incident-summary", allowed_runtime_extensions={"user-invocable"})
    assert (adapted.valid, adapted.core_fields, adapted.runtime_extensions) == (
        True, ("description", "metadata", "name"), ("user-invocable",)
    ), "an allowed extension is still listed as an extension"
    bad_name = validate_skill_text(PORTABLE.replace("name: incident-summary", "name: Incident_Summary"), "incident-summary")
    assert codes(bad_name) == ["name-format"], "one name issue at most"

    broken = validate_skill_text(skill_md("name: incident-summary", "name: incident-summary", body=""), "incident-summary")
    assert codes(broken) == ["frontmatter-syntax"], "a syntax error is the only issue reported"
    assert (broken.valid, broken.name, broken.body) == (False, None, "")

    everything = validate_skill_text(
        skill_md(
            "name: " + "incident-summary-" * 4 + "v2",
            "description: '   '",
            "compatibility: " + "c" * 501,
            "user-invocable: true",
            "metadata: owner",
            "argument-hint: '[incident-id]'",
            "allowed-tools: |",
            "  Read",
            "  Grep",
            body="\n\n",
        ),
        "incident-summary",
    )
    assert codes(everything) == [
        "name-too-long",
        "description-required",
        "compatibility-too-long",
        "metadata-shape",
        "allowed-tools-shape",
        "body-required",
        "unsupported-runtime-field",
        "unsupported-runtime-field",
    ], "issues come in the documented order"
    assert ["argument-hint" in everything.issues[-2].message, "user-invocable" in everything.issues[-1].message] == [
        True, True
    ], "one unsupported-runtime-field per field, in field-name order"
    assert everything.runtime_extensions == ("argument-hint", "user-invocable"), "runtime_extensions are sorted"

    base = ["name: incident-summary", "description: Summarize an incident timeline."]
    cases = [
        (["name: " + "x" * 64, base[1]], "x" * 64, []),
        (["name: " + "x" * 65, base[1]], "x" * 65, ["name-too-long"]),
        (['name: ""', base[1]], "incident-summary", ["name-required"]),
        ([base[1]], "incident-summary", ["name-required"]),
        ([base[0], "description: " + "d" * 1024], "incident-summary", []),
        ([base[0], "description: " + "d" * 1025], "incident-summary", ["description-too-long"]),
        ([base[0], "description: " + "说" * 1024], "incident-summary", []),
        ([base[0], 'description: " "'], "incident-summary", ["description-required"]),
        ([base[0]], "incident-summary", ["description-required"]),
        (base + ["compatibility: " + "c" * 500], "incident-summary", []),
        (base + ["compatibility: " + "兼" * 500], "incident-summary", []),
        (base + ['compatibility: "  "'], "incident-summary", ["compatibility-empty"]),
        (base + ["compatibility: ''"], "incident-summary", ["compatibility-empty"]),
        (base + ["allowed-tools: Read Grep"], "incident-summary", []),
        (base + ["allowed-tools: Bash(git:*)  Read"], "incident-summary", []),
        (base + ["allowed-tools:"], "incident-summary", ["allowed-tools-shape"]),
        (base + ['allowed-tools: "  "'], "incident-summary", ["allowed-tools-shape"]),
        (base + ['allowed-tools: "Read\\tGrep"'], "incident-summary", ["allowed-tools-shape"]),
        (base + ["metadata:", "  owner: reliability"], "incident-summary", []),
    ]
    for lines, directory, expected in cases:
        assert codes(validate_skill_text(skill_md(*lines), directory)) == expected, (
            f"lengths count characters and blank values are missing: {lines[-1][:40]!r} -> {expected}"
        )
    assert codes(validate_skill_text(skill_md(*base, body="  \n\n"), "incident-summary")) == ["body-required"], (
        "a body with no text is missing"
    )

    two = skill_md(*base, "user-invocable: false", "argument-hint: '[incident-id]'")
    report = validate_skill_text(two, "incident-summary", iter(["user-invocable", "argument-hint"]))
    assert report.valid, "the host's allowed extensions can come as any iterable"

    fields = {"name": "release-readiness", "description": "Use when: a version is about to be tagged.",
              "user-invocable": "false", "metadata": {"lesson": "22"}}
    report = validate_skill_text(render_skill(fields, "# Release readiness\n"), "release-readiness", {"user-invocable"})
    assert (report.valid, report.description) == (True, fields["description"]), "a written skill validates"


# One host's lifecycle events, as (skill, stage, extra fields).
LIFECYCLE = [
    ("release-readiness", "discovered"),
    ("incident-summary", "discovered"),
    ("release-readiness", "validated", {"ok": True}),
    ("incident-summary", "validated", {"ok": False}),
    ("release-readiness", "cataloged"),
    ("incident-summary", "ended"),
    ("release-readiness", "selected"),
    ("release-risk-review", "discovered"),
    ("release-readiness", "activated"),
    ("release-risk-review", "validated", {"ok": True}),
    ("release-readiness", "resource_loaded", {"path": "references/release-policy.md"}),
    ("release-risk-review", "cataloged"),
    ("release-readiness", "tool_called", {"tool": "inspect_release"}),
    ("release-risk-review", "selected"),
    ("release-risk-review", "resource_loaded", {"path": "references/risk-matrix.md"}),
    ("release-readiness", "verified"),
    ("release-risk-review", "activated"),
    ("release-readiness", "ended"),
    ("deploy-helper", "discovered"),
    ("release-risk-review", "ended"),
    ("deploy-helper", "validated", {"ok": False}),
    ("deploy-helper", "activated"),  # the user typed /deploy-helper
    ("changelog-style", "discovered"),
    ("deploy-helper", "tool_called", {"tool": "kubectl"}),
    ("deploy-helper", "ended"),
    ("changelog-style", "validated", {"ok": True}),
    ("changelog-style", "cataloged"),
    ("changelog-style", "selected"),
    ("changelog-style", "activated"),
    ("changelog-style", "tool_called", {"tool": "format_changelog"}),
    ("changelog-style", "verified"),
    ("changelog-style", "tool_called", {"tool": "write_file"}),
    ("changelog-style", "ended"),
    ("incident-summary", "discovered"),  # reinstalled with its name fixed
    ("incident-summary", "validated", {"ok": True}),
    ("incident-summary", "cataloged"),
    ("skill-contract-reviewer", "discovered"),
    ("incident-summary", "selected"),
    ("incident-summary", "activated"),
    ("release-readiness", "discovered"),  # a rescan
    ("incident-summary", "ended"),
    ("release-readiness", "validated", {"ok": True}),
    ("skill-contract-reviewer", "cataloged"),
]
TAP_LINE = re.compile(r"(ok|not ok) [1-9][0-9]* - [a-z0-9-]+( # [a-z_ ]+)?|1\.\.[0-9]+")


@pytest.mark.skip("Part 4")
def test_lifecycle_tap() -> None:
    """Each skill session gets a TAP line the moment it ends; the plan comes last."""
    pulled: list[int] = []

    async def host():
        for i, (skill, stage, *extra) in enumerate(LIFECYCLE):
            pulled.append(i)
            yield {"skill": skill, "stage": stage, **(extra[0] if extra else {})}

    async def report() -> list[tuple[int, str]]:
        return [(len(pulled), line) async for line in tap_report(host())]

    received = asyncio.run(report())
    rows = "".join(line for _, line in received).split("\n")
    assert rows.pop() == "" and all(TAP_LINE.fullmatch(row) for row in rows), (
        f"every line is a TAP result or the plan, and ends with a newline: {rows[:3]}"
    )
    assert rows == [
        "ok 1 - incident-summary",
        "ok 2 - release-readiness",
        "not ok 3 - release-risk-review # resource_loaded before activated",
        "not ok 4 - deploy-helper # activated after failed validation",
        "not ok 5 - changelog-style # tool_called not verified",
        "ok 6 - incident-summary",
        "not ok 7 - skill-contract-reviewer # cataloged before validated",
        "not ok 8 - release-readiness # session not ended",
        "1..8",
    ], "one result per session, numbered as sessions end; open sessions last, then the plan"
    assert [count for count, _ in received] == [6, 18, 20, 25, 33, 41, 43, 43, 43], (
        "a result comes out the moment its session ends"
    )

    async def nothing():
        return
        yield

    async def empty() -> list[str]:
        return [line async for line in tap_report(nothing())]

    assert asyncio.run(empty()) == ["1..0\n"], "no sessions, an empty plan"

    async def rejected():
        yield {"skill": "deploy-helper", "stage": "discovered"}
        yield {"skill": "deploy-helper", "stage": "validated", "ok": False}
        yield {"skill": "deploy-helper", "stage": "cataloged"}
        yield {"skill": "deploy-helper", "stage": "ended"}

    async def lines(events) -> list[str]:
        return [line async for line in tap_report(events)]

    assert asyncio.run(lines(rejected())) == ["not ok 1 - deploy-helper # cataloged after failed validation\n", "1..1\n"], (
        "a package that failed validation never reaches the catalog"
    )


WORKFLOW = {
    "release-readiness": (
        "---\n"
        "name: release-readiness\n"
        "description: Inspect a release candidate when the user asks whether a version is ready to publish.\n"
        "---\n"
        "# Release readiness\n"
        "\n"
        "1. Read `references/release-policy.md`.\n"
        "2. Invoke the `changelog-style` skill on the draft changelog.\n"
        "   If that skill is unavailable, use `assets/changelog-template.md` instead.\n"
        "3. After producing the candidate changelog, invoke the `release-risk-review` skill.\n"
        "   Pass the candidate path and require a blocking or non-blocking verdict.\n"
        "   If that skill is unavailable, stop and report the missing dependency.\n"
        "4. Ask for approval before any publish or tag action.\n"
    ),
    "release-risk-review": (
        "---\n"
        "name: release-risk-review\n"
        "description: Review a candidate changelog for blocking release risks.\n"
        "---\n"
        "Invoke the `security-scan` skill on the candidate, then check the wording: invoke the\n"
        "`changelog-style` skill and keep its verdict. If that skill is\n"
        "unavailable, stop and report the missing dependency.\n"
    ),
    "changelog-style": (
        "---\n"
        "name: changelog-style\n"
        "description: Rewrite changelog entries in the house style.\n"
        "---\n"
        "Rewrite each entry in the imperative mood and keep the issue numbers.\n"
    ),
    "skill-contract-reviewer": (
        "---\n"
        "name: skill-contract-reviewer\n"
        "description: Review an Agent Skill package before it ships.\n"
        "---\n"
        "1. When the package depends on another skill, ask for an edge written like this:\n"
        "\n"
        "   ```markdown\n"
        "   After producing the candidate changelog, invoke the `release-risk-review` skill.\n"
        "   If that skill is unavailable, stop and report the missing dependency.\n"
        "   ```\n"
        "\n"
        '2. A line such as "invoke the release-notes skill" is not an edge: the name goes in backticks.\n'
    ),
    "deploy-gate": (
        "---\n"
        "name: deploy-gate\n"
        "description: Use before a production deploy, when another skill says to invoke the `deploy-gate` skill.\n"
        "---\n"
        "1. Invoke the `release-readiness` skill; stop if that skill is unavailable.\n"
        "2. Wait for a human approval.\n"
        "3. Invoke the `release-readiness` skill again on the final tag.\n"
    ),
    "incident-triage": (
        "---\n"
        "name: incident-triage\n"
        "description: Turn incident notes into a triage summary.\n"
        "---\n"
        "Summarize the notes. When the incident is severe, invoke the `pager-escalation` skill,\n"
        "and page the on-call engineer by hand if that skill is unavailable.\n"
    ),
}


@pytest.mark.skip("Part 5")
def test_workflow_edges() -> None:
    """Workflow edges come from the bodies; missing and unguarded edges are reported; dependencies install first."""
    report = workflow_report(WORKFLOW)
    assert report.edges == [
        ("deploy-gate", "release-readiness"),
        ("incident-triage", "pager-escalation"),
        ("release-readiness", "changelog-style"),
        ("release-readiness", "release-risk-review"),
        ("release-risk-review", "changelog-style"),
        ("release-risk-review", "security-scan"),
    ], "one edge per dependency, from the body's prose only"
    assert report.missing == [("incident-triage", "pager-escalation"), ("release-risk-review", "security-scan")], (
        "edges to skills that are not installed"
    )
    assert report.unguarded == [("deploy-gate", "release-readiness"), ("release-risk-review", "security-scan")], (
        "a guard covers the nearest reference before it, and every reference needs one"
    )
    assert report.install_order == [
        "changelog-style",
        "incident-triage",
        "skill-contract-reviewer",
        "release-risk-review",
        "release-readiness",
        "deploy-gate",
    ], "dependencies first, in rounds, by name within a round"
