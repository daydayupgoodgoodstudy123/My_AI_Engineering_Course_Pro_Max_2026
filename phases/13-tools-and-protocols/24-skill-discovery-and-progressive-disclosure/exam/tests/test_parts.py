import asyncio
import gc
import hashlib
import json
import os
import random
import re
import shutil
import time
from pathlib import Path

import pytest
from skillcat.budget import SHORT_DESCRIPTION_CHARS, Budget, catalog_budget, fit_catalog
from skillcat.cache import DiscoveryCache
from skillcat.catalog import CatalogBudget, build_catalog, entry_for, model_json, shorten
from skillcat.disclosure import Activate, Read, disclosure_events
from skillcat.discovery import Collision, CollisionError, Scope, SkillCandidate, discover_scope
from skillcat.refgraph import ReferenceReport, reference_graph
from skillcat.resources import ReferencePathError, validate_reference
from skillcat.service import SkillHost


def write_skill(root: Path, name: str, description: str, body: str = "# Instructions\n") -> Path:
    package = root / name
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}", encoding="utf-8")
    return package


def raises(exc: type[Exception], call, *args) -> bool:
    try:
        call(*args)
    except exc:
        return True
    return False


def accepted(package: Path, reference: str):
    """The path validate_reference returns, or None when it refuses the reference."""
    try:
        return validate_reference(package, reference)
    except ReferencePathError:
        return None


WORDS = "check build tag wheel image deploy notes review audit report schema release draft owner".split()


@pytest.mark.skip("Part 1")
def test_discovery_pipeline(tmp_path) -> None:
    """Discovery stays shallow, rank decides collisions, reads stay in the package, and publishing scales."""
    workspace = tmp_path / "repo" / ".agents" / "skills"
    user = tmp_path / "home" / ".agents" / "skills"
    builtin = tmp_path / "agent-runtime" / "skills"
    release = write_skill(workspace, "release-readiness", "Validate this repository's release candidate. Use before a tag.")
    author = write_skill(workspace, "skill-author", "Write and review Agent Skills. Use when asked for a new SKILL.md.")
    write_skill(author / "examples", "release-readiness", "The example package from the authoring guide.")
    write_skill(author / "tests" / "fixtures", "minimal-skill", "The smallest valid package.")
    write_skill(workspace, "incident-review", "Write a blameless incident review. Use after an outage.")
    write_skill(user, "release-readiness", "Check any release candidate. Use when a version is ready to publish.")
    write_skill(user, "meeting-brief", "Prepare a meeting brief from notes. Use before a meeting.")
    write_skill(builtin, "meeting-brief", "Summarize a meeting. Use when notes are attached.")
    write_skill(builtin, "release-readiness", "Run the generic release checklist. Use for any package.")
    scopes = [Scope("workspace", workspace, 0), Scope("user", user, 1), Scope("builtin", builtin, 2)]

    catalog = SkillHost(scopes).catalog(CatalogBudget(max_catalog_chars=100_000))
    assert [c.name for c in discover_scope(scopes[0]).candidates] == [
        "incident-review",
        "release-readiness",
        "skill-author",
    ], "a SKILL.md deeper inside a package is not a package of its own"
    assert [(e.name, e.scope) for e in catalog.entries] == [
        ("incident-review", "workspace"),
        ("release-readiness", "workspace"),
        ("skill-author", "workspace"),
        ("meeting-brief", "user"),
    ], "the lower rank wins a collision"
    found = {(c.scope, c.name): c for scope in scopes for c in discover_scope(scope).candidates}
    assert catalog.collisions == (
        Collision("meeting-brief", found["user", "meeting-brief"], (found["builtin", "meeting-brief"],)),
        Collision(
            "release-readiness",
            found["workspace", "release-readiness"],
            (found["user", "release-readiness"], found["builtin", "release-readiness"]),
        ),
    ), "shadowed candidates stay in the diagnostics, best rank first"
    write_skill(tmp_path / "plugins" / "a", "pdf-tools", "Fill PDF forms. Use when a form is attached.")
    write_skill(tmp_path / "plugins" / "b", "pdf-tools", "Edit PDF files. Use when a PDF needs changes.")
    plugins = [Scope("plugin-a", tmp_path / "plugins" / "a", 3), Scope("plugin-b", tmp_path / "plugins" / "b", 3)]
    assert raises(CollisionError, SkillHost(scopes + plugins).catalog, CatalogBudget(max_catalog_chars=100_000)), (
        "two packages with one name at one rank are an error, whatever their paths"
    )

    references = release / "references"
    references.mkdir()
    (references / "python-release.md").write_text("# Python release\n", encoding="utf-8")
    (references / "latest.md").symlink_to("python-release.md")
    secret = tmp_path / "private" / "sign-off.md"
    secret.parent.mkdir()
    secret.write_text("deploy key: hunter2\n", encoding="utf-8")
    (references / "team-notes.md").symlink_to(secret)
    vendor = tmp_path / "vendor-docs"
    vendor.mkdir()
    (vendor / "guide.md").write_text("# Vendor guide\n", encoding="utf-8")
    (references / "vendor").symlink_to(vendor, target_is_directory=True)
    linked = tmp_path / "linked-skills"
    linked.symlink_to(workspace, target_is_directory=True)
    package = linked / "release-readiness"  # the same package, reached through a symlinked root
    assert accepted(package, "references/latest.md") == references / "python-release.md", (
        "a symlink that stays inside the package is fine"
    )
    assert accepted(package, "references/team-notes.md") is None, "a symlink that leaves the package is refused"
    assert accepted(package, "references/vendor/guide.md") is None, (
        "a symlinked directory that leaves the package is refused"
    )
    for bad in ("../incident-review/SKILL.md", str(references / "python-release.md"), "references\\latest.md"):
        assert accepted(package, bad) is None, f"{bad!r} is not a clean reference"
    for bad in ("references/missing.md", "references"):
        assert accepted(package, bad) is None, f"{bad!r} does not name a file"

    rng = random.Random(24)
    many = [
        SkillCandidate(
            f"skill-{i:04d}",
            " ".join(rng.choice(WORDS) for _ in range(rng.randint(3, 28))).capitalize() + ".",
            "user",
            1,
            Path(f"/srv/skills/skill-{i:04d}"),
        )
        for i in range(1800)
    ]
    rng.shuffle(many)
    gc.collect()  # time build_catalog, not the collection of the candidates built above
    start = time.perf_counter()
    big = build_catalog(many, CatalogBudget(max_entries=len(many), max_catalog_chars=6_000))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15, "publishing a big catalog should be fast"
    names = sorted(c.name for c in many)
    kept = len(big.entries)
    assert big.catalog_chars == len(model_json(big.entries)) <= 6_000, (
        "catalog_chars is the length of the text the model receives"
    )
    assert [e.name for e in big.entries] == names[:kept] and big.omitted == tuple(names[kept:]), (
        "entries are cut from the end, and omitted keeps priority order"
    )
    by_name = {c.name: c for c in many}
    assert len(model_json([*big.entries, entry_for(by_name[names[kept]])])) > 6_000, "every entry that fits is kept"
    three = [by_name[name] for name in names[:3]]
    exact = len(model_json([entry_for(c) for c in three[:2]]))
    assert [e.name for e in build_catalog(three, CatalogBudget(max_catalog_chars=exact)).entries] == names[:2], (
        "an entry that fits exactly is kept"
    )
    one = len(model_json([entry_for(three[0])]))
    assert build_catalog(three, CatalogBudget(max_entries=2, max_catalog_chars=one)).omitted == tuple(names[1:3]), (
        "omitted lists every left-out name in priority order"
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.skip("Part 2")
def test_discovery_cache(tmp_path) -> None:
    """A JSON snapshot gives back exactly what discovery finds, and notices every change to SKILL.md."""
    root = tmp_path / "Team Skills" / "Größe Ölung" / ".agents" / "skills"
    release_md = write(
        root / "release-readiness" / "SKILL.md",
        "---\nname: release-readiness\ndescription: |\n  Validate a Python release candidate.\n"
        "  Use when a tag is about to be pushed.\nmetadata:\n  owner: Release Engineering\n  tier: gold\n"
        "---\n\n# Release readiness\n",
    )
    write(root / "release-readiness" / "examples" / "demo" / "SKILL.md", "---\nname: demo\ndescription: An example.\n---\n")
    write(
        root / "incident-review" / "SKILL.md",
        '---\nname: incident-review\ndescription: "Write a blameless review: what failed, why, what changes."\n---\n',
    )
    write(root / "Bad_Name" / "SKILL.md", "---\nname: Bad_Name\ndescription: Not kebab-case.\n---\n")
    write(root / "notes-helper" / "SKILL.md", "---\nname: note-helper\ndescription: Name and directory differ.\n---\n")
    write(root / "drafts" / "README.md", "No SKILL.md here.\n")
    scope = Scope("workspace", root, 0)
    path = tmp_path / "discovery.json"

    cache = DiscoveryCache(path)
    assert cache.discover(scope) == discover_scope(scope), "the cache returns what discovery returns"
    assert cache.parsed == ["Bad_Name", "incident-review", "notes-helper", "release-readiness"], (
        "an empty cache inspects every package"
    )
    assert path.is_file(), "the snapshot is saved at the path the cache was given"
    json.loads(path.read_text(encoding="utf-8"))
    reopened = DiscoveryCache(path)
    assert reopened.discover(scope) == discover_scope(scope), "a reopened cache returns exactly what discovery returns"
    assert reopened.parsed == [], "unchanged packages are served from the snapshot"

    before = release_md.stat()
    release_md.write_bytes(release_md.read_bytes().replace(b"Python", b"Pyth0n"))  # same size
    os.utime(release_md, ns=(before.st_atime_ns, before.st_mtime_ns))
    edited = DiscoveryCache(path)
    assert edited.discover(scope) == discover_scope(scope), "an edit is seen even when size and mtime are unchanged"
    assert edited.parsed == ["release-readiness"], "only the changed package is inspected again"
    assert hashlib.sha256(release_md.read_bytes()).hexdigest() in path.read_text(encoding="utf-8"), (
        "the snapshot records the SHA-256 of each SKILL.md, which stays the same in the next session"
    )

    home = tmp_path / "home" / ".agents" / "skills"
    shutil.copytree(root / "incident-review", home / "incident-review")  # the same bytes, installed twice
    shutil.copytree(root / "incident-review", home / "incident-review-old")
    user = Scope("user", home, 1)
    shared = DiscoveryCache(path)
    assert shared.discover(user) == discover_scope(user), "a package is identified by its directory, not by its bytes"
    assert shared.parsed == ["incident-review", "incident-review-old"], "a package seen for the first time is inspected"
    again = DiscoveryCache(path)
    assert again.discover(scope) == discover_scope(scope) and again.parsed == [], (
        "one scope never overwrites another in the snapshot"
    )
    renamed = Scope("project", root, 2)
    assert DiscoveryCache(path).discover(renamed) == discover_scope(renamed), (
        "a policy change is never served from the snapshot"
    )

    shutil.rmtree(root / "incident-review")
    (root / "Bad_Name").rename(root / "bad-name")
    fixed = root / "bad-name" / "SKILL.md"
    fixed.write_text(fixed.read_text(encoding="utf-8").replace("Bad_Name", "bad-name"), encoding="utf-8")
    later = DiscoveryCache(path)
    assert later.discover(scope) == discover_scope(scope), "a removed package is gone and a renamed one is found"
    assert later.parsed == ["bad-name"], "only the new package is inspected"


def count_tokens(text: str) -> int:
    """A stand-in tokenizer: every word, number and punctuation mark is one token."""
    return len(re.findall(r"\w+|[^\w\s]", text))


ROOTS = {0: ("workspace", "/work/acme-api/.agents/skills"), 1: ("user", "/home/dana/.agents/skills"), 2: ("builtin", "/opt/agent-runtime/skills")}
FLEET = [
    SkillCandidate(name, description, ROOTS[rank][0], rank, Path(ROOTS[rank][1]) / name)
    for rank, name, description in [
        (0, "release-readiness", "Validate this repository's release candidate and write a readiness report. Use when a version, tag or package is about to be published, or the user asks \"is it ready to ship?\"."),
        (0, "incident-review", "Write a blameless incident review from the timeline, alerts and chat log. Use after an outage is resolved and the on-call engineer asks for the write-up."),
        (0, "schema-migration", "Plan a database schema migration with a rollback step and a data backfill. Use when a pull request changes models, tables or indexes."),
        (0, "api-changelog", "Summarize breaking and additive API changes between two tags for the public changelog. Use when the release manager asks what changed for integrators."),
        (0, "flaky-test-triage", "Group failing CI runs by root cause and decide which tests to quarantine. Use when the same test fails on main without a code change."),
        (0, "dependency-upgrade", "Upgrade one dependency at a time, run the tests, and record what broke. Use when a security advisory or a major version lands for a pinned package."),
        (1, "meeting-brief", "Prepare a one-page meeting brief from notes, open questions and decisions. Use before a scheduled meeting when the user shares an agenda."),
        (1, "expense-report", "Turn receipts into an expense report with categories, totals and missing items. Use when the user uploads receipts or asks to file expenses."),
        (1, "code-review", "Review a diff for correctness, tests and naming, and suggest concrete fixes. Use when the user asks for a review or pastes a patch."),
        (1, "commit-message", "Write a conventional commit message from a staged diff. Use when the user is about to commit and asks for a message."),
        (1, "standup-notes", "Draft standup notes from yesterday's commits, tickets and calendar. Use when the user asks what to say at standup."),
        (1, "pr-description", "Write a pull request description with context, changes and a test plan. Use when a branch is pushed and the user opens a pull request."),
        (1, "interview-loop", "Plan an interview loop with one competency per interviewer and a scorecard. Use when a hiring manager opens a new role."),
        (1, "reading-notes", "Turn a paper or a long article into structured reading notes with quotes and page numbers. Use when the user shares a PDF and asks for notes."),
        (1, "weekly-report", "把本周的提交、工单和会议纪要整理成中文周报，按项目分组并列出风险。Use when the user asks for a 周报 or a weekly summary in Chinese."),
        (2, "pdf-forms", "Fill, flatten and validate PDF forms field by field, keeping signatures intact.\nUse when the user attaches a PDF form and the values to put in it, or asks why a form will not submit."),
        (2, "spreadsheet-cleanup", "Clean a messy spreadsheet: split merged cells, fix headers, normalize dates. Use when a CSV or workbook will not import cleanly."),
        (2, "slide-outline", "Outline a slide deck with one message per slide and speaker notes. Use when the user asks for a presentation and gives a topic."),
        (2, "image-captions", "Write alt text and captions for the images in a document or slide deck. Use when a page has images without alt text or an accessibility check fails on them."),
        (2, "csv-to-chart", "Pick a chart type for a CSV and produce the chart specification. Use when the user asks to \"plot this\" or attaches a table."),
        (2, "email-draft", "Draft a reply that answers every question in an email thread, in the sender's tone. Use when the user pastes a thread and asks for a response or a polite decline."),
        (2, "translation-check", "Check a translation against its source for meaning, numbers, names and terminology. Use when the user supplies both texts and asks whether the translation is faithful."),
        (2, "citation-format", "Format citations and a bibliography in a named style such as APA or Chicago. Use when a manuscript cites sources inconsistently."),
        (2, "docx-redline", "Compare two versions of a Word document and list the substantive changes. Use when the user asks \"what changed?\" between drafts."),
        (2, "calendar-invite", "Turn a proposed meeting into a calendar invitation with time zones checked. Use when the user agrees on a time in chat."),
        (2, "web-research", "Research a question across several sources and cite every claim with a link. Use when the user asks a question that needs current information or a comparison of vendors."),
        (2, "unit-converter", "Convert units and currencies with the conversion shown step by step and the rate date stated.\nUse when a number comes with a unit or a currency the user does not use."),
        (2, "regex-builder", "Build and explain a regular expression from examples that must and must not match. Use when the user asks for a pattern, or a validation rule keeps rejecting good input."),
        (2, "sql-explain", "Explain a SQL query plan, point at the slowest step and suggest an index. Use when the user pastes EXPLAIN output, a slow query or a timeout from the database."),
        (2, "diagram-sketch", "Sketch an architecture diagram as Mermaid from a written description. Use when the user describes components and asks for a picture."),
        (2, "budget-forecast", "Project a monthly budget from past spending with a best and worst case. Use when the user shares statements and asks how the year ends."),
        (2, "markdown-tables", "Convert pasted data into a Markdown table with aligned columns and a caption. Use when the user pastes rows from a spreadsheet into a document."),
        (2, "json-schema-draft", "Draft a JSON Schema from example payloads, marking which fields are required. Use when the user shares sample requests and asks for a schema."),
    ]
]
PRIORITY = [c.name for c in sorted(FLEET, key=lambda c: (c.rank, c.name))]


@pytest.mark.skip("Part 3")
def test_catalog_budget() -> None:
    """The catalog gets 2 percent of a known context window, or 8,000 characters when the window is unknown."""
    assert catalog_budget(None) == Budget(8_000, "chars"), "an unknown window gets the 8,000-character fallback"
    assert catalog_budget(128_000) == Budget(2_560, "tokens"), "a known window gets 2 percent of its tokens"
    assert catalog_budget(1_000_000) == Budget(20_000, "tokens"), "a known window is never capped at 8,000"
    assert catalog_budget(199_999) == Budget(3_999, "tokens"), "2 percent is rounded down to a whole token"
    assert raises(ValueError, catalog_budget, 0), "a window of 0 tokens is an error, not an unknown window"

    shuffled = FLEET[:]
    random.Random(7).shuffle(shuffled)
    by_name = {c.name: c for c in FLEET}

    roomy = fit_catalog(shuffled, 1_000_000, count_tokens)
    assert [e.name for e in roomy.entries] == PRIORITY, "entries come in priority order: rank, then name"
    assert len(model_json(roomy.entries)) > 8_000 and roomy.shortened == roomy.omitted == (), (
        "a known window is not also held to 8,000 characters"
    )
    exact = fit_catalog(shuffled, 50 * roomy.used, count_tokens)  # 2 percent of this window is the full cost
    assert exact.used == exact.budget.limit and exact.shortened == exact.omitted == (), (
        "a catalog that fits its budget exactly is published whole"
    )

    fallback = fit_catalog(shuffled, None, count_tokens)
    assert fallback.used == len(model_json(fallback.entries)) <= 8_000, (
        "the fallback counts the characters of the exact text the model receives"
    )
    assert (fallback.shortened, fallback.omitted) == (
        ("spreadsheet-cleanup", "sql-explain", "translation-check", "unit-converter", "web-research"),
        (),
    ), "descriptions are shortened lowest priority first, and only until the catalog fits"
    assert [e.description for e in fallback.entries if e.name in fallback.shortened] == [
        shorten(by_name[name].description, SHORT_DESCRIPTION_CHARS) for name in fallback.shortened
    ] and [e.name for e in fallback.entries] == PRIORITY, "shortening cuts the description and nothing else"

    tokens = fit_catalog(shuffled, 120_000, count_tokens)
    assert tokens.used == count_tokens(model_json(tokens.entries)) <= 2_400, "a token budget is measured in tokens"
    assert (tokens.shortened, tokens.omitted) == (tuple(PRIORITY[-7:]), ()), (
        "descriptions are shortened lowest priority first, and only until the catalog fits"
    )

    tight = fit_catalog(shuffled, 40_000, count_tokens)
    assert tight.used == count_tokens(model_json(tight.entries)) <= 800, "a token budget is measured in tokens"
    assert tight.omitted == tuple(PRIORITY[12:]), "when shortening is not enough, the lowest-priority entries go"
    assert tight.shortened == tuple(PRIORITY[:12]), "an omitted entry is listed as omitted only"
    assert fit_catalog(FLEET[::-1], 40_000, count_tokens) == tight, "the input order changes nothing"


RELEASE_BODY = """# Release readiness

Check a release candidate before it is published – one report per tag.

## Choose the path

- For a Python package, read [python-release.md](references/python-release.md).
- For a container image, read [container-release.md](references/container-release.md).
- For a documentation-only release, read [docs-release.md](references/docs-release.md).
- For an internal sign-off, read [team-notes.md](references/team-notes.md).

## Report

Return one line per check and a final verdict.
"""
LOGFMT_PAIR = re.compile(r'([a-z][a-z_.]*)=("(?:[^"\\\x00-\x1f\x7f]|\\["\\nrt]|\\u[0-9a-f]{4})*"|[^\s"=\\\x00-\x1f\x7f]+)')
UNESCAPE = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}


def logfmt(line: str) -> list[tuple[str, str]]:
    """Parse one logfmt line strictly: key=value pairs one space apart, values bare or quoted."""
    pairs, pos = [], 0
    while True:
        match = LOGFMT_PAIR.match(line, pos)
        assert match, f"not a logfmt line: {line!r}"
        key, raw = match.groups()
        if raw.startswith('"'):
            raw = re.sub(r'\\(u[0-9a-f]{4}|.)', lambda m: chr(int(m[1][1:], 16)) if len(m[1]) > 1 else UNESCAPE[m[1]], raw[1:-1])
        pairs.append((key, raw))
        pos = match.end()
        if pos == len(line):
            return pairs
        assert line[pos] == " " and line[pos + 1 : pos + 2] not in ("", " "), f"not a logfmt line: {line!r}"
        pos += 1


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def arrive(items: list):
    for item in items:
        yield item


@pytest.mark.skip("Part 4")
def test_disclosure_log(tmp_path) -> None:
    """Every activation and read is logged as one logfmt line, as soon as it is handled, without content."""
    root = tmp_path / "skills"
    release = write_skill(root, "release-readiness", "Validate a release candidate. Use before a tag.", RELEASE_BODY)
    write_skill(root, "incident-review", "Write an incident review. Use after an outage.")
    refs = release / "references"
    python = write(refs / "python-release.md", "# Python release\n\nBuild the sdist and the wheel, then check pyproject.toml.\n")
    write(refs / "container-release.md", ("Prüfe die Größe des Images, höchstens 500 MB. " * 30)[:1000])
    docs = "Rebuild the docs site – then check every link.\n" * 20
    write(refs / "docs-release.md", docs + "." * (1024 - len(docs.encode("utf-8"))))
    write(refs / "legacy.md", "# Legacy\n")
    write(tmp_path / "private" / "sign-off.md", "deploy key: hunter2\n")
    (refs / "team-notes.md").symlink_to(tmp_path / "private" / "sign-off.md")
    entries = [entry_for(c) for c in discover_scope(Scope("workspace", root, 0)).candidates]
    reasons = ["", 'tag says "v2.1.0"', "version=2.1.0", "C:\\builds\\wheel", "prüfe-wheel"]
    requests = [
        Read("release-readiness", "references/python-release.md", "candidate contains pyproject.toml"),
        Activate("release-readiness"),
        Read("release-readiness", "references/python-release.md", "candidate contains pyproject.toml"),
        Read("release-readiness", "references/container-release.md", "Dockerfile found"),
        Read("release-readiness", "references/docs-release.md", "only docs/ changed\nno code touched"),
        Read("release-readiness", "references/legacy.md", "just in case"),
        Read("release-readiness", "references/team-notes.md", "sign-off needed"),
        Read("incident-review", "references/timeline.md", "pager fired"),
        Activate("ghost-skill"),
        *(Read("release-readiness", "references/python-release.md", reason) for reason in reasons),
        Read("release-readiness", "../incident-review/SKILL.md", "shared steps"),
    ]
    text = "".join(collect(disclosure_events(arrive(requests), entries, max_read_bytes=1024)))
    assert text.endswith("\n"), "every event ends with a newline"
    events = [logfmt(line) for line in text.split("\n")[:-1]]
    assert len(events) == len(requests), "one event per request"

    def refused(resource: str, why: str, skill: str = "release-readiness") -> list:
        return [("event", "skill.resource.refused"), ("skill", skill), ("resource", resource), ("reason", why)]

    def loaded(resource: str, why: str, size: int) -> list:
        return [
            ("event", "skill.resource.loaded"),
            ("skill", "release-readiness"),
            ("resource", resource),
            ("reason", why),
            ("bytes", str(size)),
        ]

    size = len(python.read_bytes())
    assert events[0] == refused("references/python-release.md", "not_active"), "a read before activation is refused"
    assert events[1] == [
        ("event", "skill.activated"),
        ("skill", "release-readiness"),
        ("bytes", str(len(RELEASE_BODY.strip().encode("utf-8")))),
    ], "an activation logs the size of the body"
    assert events[2] == loaded("references/python-release.md", "candidate contains pyproject.toml", size), (
        "a declared branch of an active skill is loaded and logged with its reason and size"
    )
    assert events[3] == refused("references/container-release.md", "too_large"), "the read limit counts UTF-8 bytes"
    assert events[4] == loaded("references/docs-release.md", "only docs/ changed\nno code touched", 1024), (
        "a file of exactly max_read_bytes bytes is loaded"
    )
    assert events[5] == refused("references/legacy.md", "not_declared"), "only the branches SKILL.md declares are read"
    assert events[6] == refused("references/team-notes.md", "invalid_path"), "a branch that leaves the package is refused"
    assert events[7] == refused("references/timeline.md", "not_active", "incident-review"), "each skill is activated on its own"
    assert events[8] == [("event", "skill.refused"), ("skill", "ghost-skill"), ("reason", "not_in_catalog")], (
        "only a skill in the catalog can be activated"
    )
    assert events[9:-1] == [loaded("references/python-release.md", reason, size) for reason in reasons], (
        "a reason comes through exactly, whatever characters it holds"
    )
    assert events[-1] == refused("../incident-review/SKILL.md", "not_declared"), (
        "a read is refused with the first reason that applies, in the documented order"
    )
    assert "hunter2" not in text and "sdist" not in text, "content is never logged"

    pulled: list[int] = []

    async def busy():
        yield Activate("release-readiness")
        yield Read("release-readiness", "references/python-release.md", "candidate contains pyproject.toml")
        for i in range(500):
            pulled.append(i)
            yield Read("release-readiness", "references/legacy.md", f"just in case {i}")

    async def first_two() -> list[str]:
        agen = disclosure_events(busy(), entries)
        got = [await agen.__anext__(), await agen.__anext__()]
        await agen.aclose()
        return got

    _, second = asyncio.run(first_two())
    assert logfmt(second.rstrip("\n"))[0] == ("event", "skill.resource.loaded")
    assert len(pulled) <= 1, "every request is logged as soon as it is handled"


SKILL_MD = """---
name: release-readiness
description: Validate a release candidate. Use before a tag.
---

# Release readiness

The package format is in the [Agent Skills specification](https://agentskills.io/specification).

## Choose the path

- For a Python package, read [python-release.md](references/python-release.md).
- For a container image, read [container-release.md](references/container-release.md#before-you-start).
- For a documentation-only release, read [docs-release.md](./references/docs-release.md).
- For anything else, read [the references](references/) for more.

Run [check_version.py](scripts/check_version.py) before tagging. Questions go to [the release team](mailto:release@example.com).

## Writing a new branch

```markdown
- For a Rust crate, read [archive.md](references/archive.md).
```

Back to [the paths](#choose-the-path).
"""
PACKAGE = {
    "references/python-release.md": "# Python release\n\n1. Build the sdist and the wheel.\n"
    "2. Walk through [the PyPI checklist](checklists/pypi.md).\n"
    "3. Draft the changelog from [the template](../assets/changelog-template.md).\n"
    "4. Shipping an image too? Read [container-release.md](container-release.md?plain=1).\n"
    "5. The old [PyPI notes](checklists/old-pypi.md#upload) were removed.\n",
    "references/container-release.md": "# Container release\n\n## Before you start\n\n"
    "Sign the image with [the signing checklist](checklists/signing.md#cosign).\n"
    "The shared policy is in [incident-review](../../incident-review/references/policy.md).\n\n"
    "~~~text\n[old layout](archive.md)\n~~~\n",
    "references/docs-release.md": "# Documentation-only release\n\nRebuild the site, then go back to [the skill](../SKILL.md).\n",
    "references/checklists/pypi.md": "# PyPI checklist\n\n- [ ] The version matches the tag.\n- [ ] Signed, see [signing](signing.md).\n",
    "references/checklists/signing.md": "# Signing\n\nRotate keys as in [key rotation](../key-rotation.md). Back to [PyPI](pypi.md).\n",
    "references/key-rotation.md": "# Key rotation\n\nRotate the signing key every 90 days.\n",
    "references/archive.md": "# Archived layout\n",
    "references/legacy.md": "# Legacy notes\n",
    "scripts/check_version.py": 'CHECKS = {"pep440": bool}\n\n\ndef run(name, version):\n    return CHECKS[name](version)\n',
    "assets/changelog-template.md": "# Changelog\n\n## [Unreleased](https://keepachangelog.com/)\n",
    "assets/logo.txt": "logo\n",
}


@pytest.mark.skip("Part 5")
def test_reference_graph(tmp_path) -> None:
    """Every file SKILL.md reaches gets its fewest number of links; deep, dead and unconditional references are reported."""
    package = tmp_path / "release-readiness"
    write(package / "SKILL.md", SKILL_MD)
    for name, text in PACKAGE.items():
        write(package / name, text)
    write(tmp_path / "incident-review" / "references" / "policy.md", "# Shared policy\n")  # exists, but in another package
    report = reference_graph(package)
    depth = report.depth
    assert "references/legacy.md" not in depth, "a link to a whole directory is reported, not followed"
    assert depth.get("references/checklists/pypi.md") == 2 and depth.get("references/docs-release.md") == 1, (
        "a link is resolved against the directory of the file that holds it"
    )
    assert "references/container-release.md" in depth and not any(
        "#" in path or "?" in path for path in [*depth, *(target for _, target in report.broken)]
    ), "#fragments and ?queries do not name new files"
    assert depth["references/container-release.md"] == 1 and depth["references/key-rotation.md"] == 3, (
        "depth is the fewest links it takes"
    )
    assert report.directory_links == [("SKILL.md", "references")], "a link to a whole directory is reported, not followed"
    assert "references/archive.md" not in depth, "links in fenced code blocks are examples, not references"
    assert all(source.endswith(".md") for source, _ in report.broken), "only Markdown files are read for links"
    assert not any(":" in target for _, target in report.broken), "links with a scheme are not references"
    assert report.dead == ["references/archive.md", "references/legacy.md"], (
        "dead files are the files under references/ that nothing reaches"
    )
    assert ("references/python-release.md", "checklists/old-pypi.md") in report.broken, (
        "a broken link is reported with its target as written"
    )
    assert report.deep == [
        "assets/changelog-template.md",
        "references/checklists/pypi.md",
        "references/checklists/signing.md",
        "references/key-rotation.md",
    ], "every file that takes two or more links is deep"
    assert report == ReferenceReport(
        depth={
            "SKILL.md": 0,
            "references/python-release.md": 1,
            "references/container-release.md": 1,
            "references/docs-release.md": 1,
            "scripts/check_version.py": 1,
            "references/checklists/pypi.md": 2,
            "assets/changelog-template.md": 2,
            "references/checklists/signing.md": 2,
            "references/key-rotation.md": 3,
        },
        deep=[
            "assets/changelog-template.md",
            "references/checklists/pypi.md",
            "references/checklists/signing.md",
            "references/key-rotation.md",
        ],
        dead=["references/archive.md", "references/legacy.md"],
        directory_links=[("SKILL.md", "references")],
        broken=[
            ("references/container-release.md", "../../incident-review/references/policy.md"),
            ("references/python-release.md", "checklists/old-pypi.md"),
        ],
    ), "the whole report"
