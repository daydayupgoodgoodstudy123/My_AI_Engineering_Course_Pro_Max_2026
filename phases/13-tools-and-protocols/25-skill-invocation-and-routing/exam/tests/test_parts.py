import asyncio
import gc
import json
import time

import pytest
from skillroute.arguments import ArgumentError, Binding, Param, bind, split_command, tool_arguments
from skillroute.compose import Call, Composer, Reply, SkillRequest, SkillSpec
from skillroute.policy import Actor, CorePolicyAdapter, ExtensionPolicyAdapter, InvocationPolicy, InvocationRequest
from skillroute.router import Router
from skillroute.service import Contract, NeedsInput, Ready, Refused, SkillHost
from skillroute.session import Approve, Body, Check, Compaction, ToolCall, UserTurn, lifecycle
from skillroute.state import RunState, SkillRun, Step, Write


def skill_md(name: str, description: str, *fields: str) -> str:
    """The frontmatter block of one SKILL.md, as discovery hands it over."""
    return "\n".join(["---", f"name: {name}", f"description: {description}", *fields, "---", ""])


def model(query: str) -> InvocationRequest:
    return InvocationRequest(Actor.MODEL, query)


def human(name: str) -> InvocationRequest:
    return InvocationRequest(Actor.HUMAN, "", explicit_name=name)


INCIDENT = [
    skill_md("incident-triage", "Triage incident timeline evidence.", "disable-model-invocation: true"),
    skill_md("incident-review", "Review incident timeline evidence."),
    skill_md("release-notes", "Draft release notes from merged changes."),
]
QUADRANTS = [
    skill_md("code-explain", "Explain code and plan tests."),
    skill_md("billing-export", "Export billing records for finance.", "disable-model-invocation: true"),
    skill_md("style-guide", "Apply the internal writing style guide.", "user-invocable: false"),
    skill_md("staged-rollout", "Stage a feature rollout.", "user-invocable: false", "disable-model-invocation: true"),
]
WRITTEN_AS_TEXT = [
    skill_md("deploy-plan", "Plan a deployment.", 'disable-model-invocation: "false"'),
    skill_md("audit-trail", "Review the audit trail.", "user-invocable: False"),
    skill_md("cleanup-plan", "Plan a destructive cleanup.", "disable-model-invocation: TRUE"),
]
DIGESTS = [
    skill_md("deploy-digest", "Summarize the deploy log."),
    skill_md("log-digest", "Summarize the deploy log."),
    skill_md("build-diagnostics", "Explain why a package build failed."),
]


@pytest.mark.skip("Part 1")
def test_route_eligible_first() -> None:
    """Policy decides the selection set, relevance ranks it, and routing abstains when it cannot tell."""
    router = Router(INCIDENT, ExtensionPolicyAdapter(InvocationPolicy()))
    query = "triage this incident timeline evidence"
    for actor, mode in ((Actor.MODEL, "implicit-model"), (Actor.AGENT, "implicit-agent")):
        decision = router.route(InvocationRequest(actor, query))
        assert (decision.activated, decision.skill_name, decision.mode, decision.score) == (
            True,
            "incident-review",
            mode,
            0.5,
        ), "a blocked top match must not keep an eligible skill from being ranked"
    closed = Router(INCIDENT, ExtensionPolicyAdapter(InvocationPolicy(allow_model=False))).route(model(query))
    assert (closed.activated, closed.skill_name) == (False, None), "with nothing eligible, routing abstains"

    assert router.route(human("incident-triage")).activated, (
        "disable-model-invocation leaves explicit human invocation alone"
    )
    host = Router(QUADRANTS, ExtensionPolicyAdapter(InvocationPolicy(application_allowlist=("staged-rollout",))))
    assert host.eligible(Actor.HUMAN) == ["billing-export", "code-explain"], (
        "humans may invoke the shared and the human-only skills"
    )
    assert host.eligible(Actor.MODEL) == host.eligible(Actor.AGENT) == ["code-explain", "style-guide"], (
        "the model and agents may select the shared and the model-only skills"
    )
    refused = host.route(human("style-guide"))
    assert (refused.activated, refused.reason) == (False, "blocked by host extension user-invocable=false"), (
        "naming a skill does not bypass the policy"
    )
    assert host.route(InvocationRequest(Actor.APPLICATION, "", explicit_name="staged-rollout")).activated, (
        "an application can still preload a skill neither humans nor the model may invoke"
    )
    core = Router(QUADRANTS, CorePolicyAdapter(InvocationPolicy()))
    assert core.eligible(Actor.HUMAN) == core.eligible(Actor.MODEL) == [
        "billing-export",
        "code-explain",
        "staged-rollout",
        "style-guide",
    ], "the core adapter gives host fields no meaning"
    text = Router(WRITTEN_AS_TEXT, ExtensionPolicyAdapter(InvocationPolicy()))
    assert (text.eligible(Actor.HUMAN), text.eligible(Actor.MODEL)) == (
        ["cleanup-plan", "deploy-plan"],
        ["audit-trail", "deploy-plan"],
    ), "a host field written as text means what the boolean means"

    tie = Router(DIGESTS, ExtensionPolicyAdapter(InvocationPolicy())).route(model("summarize the deploy log"))
    assert (tie.activated, tie.skill_name, tie.candidates) == (False, None, ("deploy-digest", "log-digest")), (
        "an exact tie is ambiguous: activate nothing and let the host ask"
    )
    weak = Router(DIGESTS, ExtensionPolicyAdapter(InvocationPolicy())).route(model("summarize it for me, please"))
    assert (weak.activated, weak.candidates, weak.reason) == (False, (), "best match did not meet the host threshold"), (
        "a tie too weak to clear the threshold is not worth asking about"
    )
    one_blocked = [DIGESTS[0], skill_md("log-digest", "Summarize the deploy log.", "disable-model-invocation: true")]
    decision = Router(one_blocked, ExtensionPolicyAdapter(InvocationPolicy())).route(model("summarize the deploy log"))
    assert (decision.activated, decision.skill_name) == (True, "deploy-digest"), (
        "only eligible skills can make a request ambiguous"
    )
    near = [DIGESTS[0], skill_md("build-log", "Summarize the build log."), DIGESTS[2]]
    assert Router(near, ExtensionPolicyAdapter(InvocationPolicy())).route(model("summarize the deploy log")).activated
    wide = Router(near, ExtensionPolicyAdapter(InvocationPolicy(ambiguity_margin=0.25)))
    assert wide.route(model("summarize the deploy log")).candidates == ("build-log", "deploy-digest"), (
        "a runner-up within the ambiguity margin makes the request ambiguous"
    )

    big = [
        skill_md(
            f"ops-{i:04d}",
            f"Run maintenance task {i} for the platform team and report what changed.",
            "license: MIT",
            "allowed-tools: Read Grep",
            f"disable-model-invocation: {'true' if i % 3 else 'false'}",
            f"argument-hint: <target-{i}>",
        )
        for i in range(3000)
    ]
    catalog = Router(big, ExtensionPolicyAdapter(InvocationPolicy()))
    catalog.route(human("ops-0000"))  # the first request may pay for loading the catalog
    names = [f"ops-{(i * 37) % 3000:04d}" for i in range(50)]
    gc.collect()
    start = time.perf_counter()
    decisions = [catalog.route(human(name)) for name in names]
    elapsed = time.perf_counter() - start
    assert [(d.activated, d.skill_name) for d in decisions] == [(True, name) for name in names]
    assert elapsed < 0.02, "route should be fast on a big catalog"


SHA_A = "4f2c9e1a7b3d5c8e9f0a1b2c3d4e5f6a7b8c9d0e"
SHA_B = "4f2c9e1a7b3d" + "e7" * 14  # the tag moved: another commit, same first 12 characters
ARGS = {"candidate": "2.10", "notes": "", "dry_run": True, "min_approvals": 2, "publish": False}
CHECKS = {"ci": {"passed": 412, "failed": 0, "flaky": []}, "coverage": 0.875, "blocking": None}
DRAFT = {"id": 0, "draft": True, "url": "https://example.test/releases/0"}


@pytest.mark.skip("Part 2")
def test_resume_state(tmp_path) -> None:
    """A run picks up where it stopped, revalidates its commit, and never repeats a recorded write."""
    path = tmp_path / "artifacts" / "release-readiness.json"

    def resume(commit: str = SHA_A, arguments: dict = ARGS) -> SkillRun:
        return SkillRun.resume(path, "release-readiness", "v2.4.0", commit, arguments)

    run = resume()
    assert run.state == RunState("release-readiness", "v2.4.0", SHA_A, ARGS), "no file yet: a fresh run"
    run.complete("collect-checks", CHECKS)
    assert resume().state.steps == [Step("collect-checks", CHECKS)], "a completed step is on disk as soon as it is recorded"
    run.complete("diff-dependencies", [])
    run.complete("approvals", 0)
    sent: list[str] = []

    def post_status(key: str):
        sent.append(key)
        return None  # 204 No Content

    def open_draft(key: str):
        sent.append(key)
        return DRAFT

    assert run.write_once("status:v2.4.0", "github:commit-status", post_status) is None
    assert run.write_once("draft:v2.4.0", "github:release", open_draft) == DRAFT
    writes = [Write("status:v2.4.0", "github:commit-status", None), Write("draft:v2.4.0", "github:release", DRAFT)]

    again = resume()  # the next process, after an interruption
    assert again.state == RunState(
        "release-readiness",
        "v2.4.0",
        SHA_A,
        ARGS,
        [Step("collect-checks", CHECKS), Step("diff-dependencies", []), Step("approvals", 0)],
        writes,
    ), "the state reads back exactly, in the order it happened"
    assert again.write_once("draft:v2.4.0", "github:release", open_draft) == DRAFT, (
        "a recorded write answers with its recorded result"
    )
    assert again.write_once("status:v2.4.0", "github:commit-status", post_status) is None
    assert sent == ["status:v2.4.0", "draft:v2.4.0"], "a recorded write is never repeated, even one that answered nothing"
    with pytest.raises(ValueError):
        again.complete("approvals", 1)
    with pytest.raises(ValueError):
        again.complete("probe-endpoints", {200: 14, 404: 1})
    assert resume().state == again.state and len(again.state.steps) == 3, (
        "a step already done, or an output JSON would change, is refused and nothing is recorded"
    )

    with pytest.raises(ValueError):
        resume(commit=SHA_A[:7])
    moved = resume(commit=SHA_B)
    assert moved.state == RunState("release-readiness", "v2.4.0", SHA_B, ARGS, [], writes), (
        "a moved commit drops the completed steps and keeps the recorded writes"
    )
    assert moved.write_once("draft:v2.4.0", "github:release-draft", open_draft) == DRAFT and len(sent) == 2, (
        "the idempotency key alone identifies a recorded write"
    )
    rerun = resume(arguments={**ARGS, "dry_run": False})
    retag = SkillRun.resume(path, "release-readiness", "v2.4.1", SHA_A, ARGS)
    assert (rerun.state.steps, rerun.state.writes, retag.state.steps, retag.state.writes) == ([], writes, [], writes), (
        "other arguments, or another candidate on the same commit, make another run"
    )

    def unavailable(key: str):
        sent.append(key)
        raise ConnectionError("503 from chat")

    with pytest.raises(ConnectionError):
        moved.write_once("notify:v2.4.0", "chat:release-channel", unavailable)
    assert resume(commit=SHA_B).state.writes == writes, "a write that failed is not recorded"
    assert moved.write_once("notify:v2.4.0", "chat:release-channel", lambda key: {"ts": "1730.5"}) == {"ts": "1730.5"}, (
        "a failed write runs again, under the same key, on the next attempt"
    )
    assert resume(commit=SHA_B).state.writes == [*writes, Write("notify:v2.4.0", "chat:release-channel", {"ts": "1730.5"})], (
        "a write that went through is recorded with its result"
    )
    with pytest.raises(ValueError):
        SkillRun.resume(path, "security-change-review", "v2.4.0", SHA_B, ARGS)

    golden = {
        "skill": "release-readiness",
        "candidate": "v2.5.0",
        "commit": SHA_B,
        "arguments": {"candidate": "v2.5.0"},
        "steps": [{"name": "collect-checks", "output": {"ci": "green"}}],
        "writes": [{"key": "status:v2.5.0", "target": "github:commit-status", "result": None}],
    }
    shared = tmp_path / "written-by-the-skill.json"
    shared.write_text(json.dumps(golden), encoding="utf-8")
    resumed = SkillRun.resume(shared, "release-readiness", "v2.5.0", SHA_B, {"candidate": "v2.5.0"})
    assert resumed.state == RunState(
        "release-readiness",
        "v2.5.0",
        SHA_B,
        {"candidate": "v2.5.0"},
        [Step("collect-checks", {"ci": "green"})],
        [Write("status:v2.5.0", "github:commit-status", None)],
    ), "the host reads the file the skill's instructions wrote"
    resumed.complete("approvals", 2)
    assert json.loads(shared.read_text(encoding="utf-8")) == {
        **golden,
        "steps": [*golden["steps"], {"name": "approvals", "output": 2}],
    }, "the host writes the layout the skill's instructions read"


READINESS_PARAMS = (
    Param("candidate", required=True),
    Param("notes", default=""),
    Param("dry_run", "--dry-run", flag=True, default=False),
    Param("min_approvals", "--min-approvals", default="1"),
    Param("publish", "--publish", flag=True, default=False, fixed=True),
)
READINESS_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate": {"type": "string"},
        "notes": {"type": "string"},
        "dry_run": {"type": "boolean"},
        "min_approvals": {"type": "integer"},
        "publish": {"type": "boolean"},
    },
    "required": ["candidate", "publish"],
    "additionalProperties": False,
}
DEFAULTS = {"notes": "", "dry_run": False, "min_approvals": "1", "publish": False}


@pytest.mark.skip("Part 3")
def test_bind_arguments() -> None:
    """Text becomes an argument vector, then named values, then typed values, and never a shell command."""
    assert split_command('/release-readiness v2.4.0 --dry-run "notes with spaces"') == (
        "release-readiness",
        ["v2.4.0", "--dry-run", "notes with spaces"],
    ), "quotes keep the spaces inside one argument"
    assert split_command('/release-readiness v2.4.0 "say \\"ship it\\" twice" \'C:\\temp\' ""') == (
        "release-readiness",
        ["v2.4.0", 'say "ship it" twice', "C:\\temp", ""],
    ), "escaped quotes, single quotes and empty arguments follow the host's rules"
    assert split_command('/release-readiness --min-approvals="2" v2.4.0') == (
        "release-readiness",
        ["--min-approvals=2", "v2.4.0"],
    ), "pieces that touch form one argument"
    assert split_command("/release-readiness v2.4.0 #412 ~/notes $HOME") == (
        "release-readiness",
        ["v2.4.0", "#412", "~/notes", "$HOME"],
    ), "nothing is expanded or dropped"
    for broken in ('/release-readiness "v2.4.0', "/release-readiness v2.4.0 'rc", "release-readiness v2.4.0"):
        with pytest.raises(ArgumentError):
            split_command(broken)

    assert bind(READINESS_PARAMS, ["v2.4.0", "--dry-run", "notes with spaces"]) == Binding(
        {**DEFAULTS, "candidate": "v2.4.0", "notes": "notes with spaces", "dry_run": True}
    ), "positionals, flags and defaults bind by name"
    assert bind(READINESS_PARAMS, ["--min-approvals=2", "v2.4.0", "--", "--dry-run"]) == Binding(
        {**DEFAULTS, "candidate": "v2.4.0", "notes": "--dry-run", "min_approvals": "2"}
    ), "after -- every argument is positional"
    assert bind(READINESS_PARAMS, ["--dry-run", "--min-approvals", "2"]) == Binding(
        {**DEFAULTS, "dry_run": True, "min_approvals": "2"}, ("candidate",)
    ), "a missing required argument is asked for, never guessed"
    dashed = bind(READINESS_PARAMS, ["--min-approvals", "-1", "v2.4.0", "-rc"])
    assert dashed == Binding({**DEFAULTS, "candidate": "v2.4.0", "notes": "-rc", "min_approvals": "-1"}), (
        "only -- marks an option: a value may start with a single dash"
    )
    for argv in (
        ["v2.4.0", "--publish"],
        ["v2.4.0", "--force"],
        ["v2.4.0", "first", "second"],
        ["v2.4.0", "--min-approvals"],
        ["v2.4.0", "--min-approvals", "--dry-run"],
        ["v2.4.0", "--min-approvals", "2", "--min-approvals", "3"],
        ["v2.4.0", "--dry-run=yes"],
        ["v2.4.0", "--min", "2"],
    ):
        with pytest.raises(ArgumentError):
            bind(READINESS_PARAMS, argv)

    typed = tool_arguments(bind(READINESS_PARAMS, ["2.10", "007", "--min-approvals", "3"]).values, READINESS_SCHEMA)
    assert typed == {"candidate": "2.10", "notes": "007", "dry_run": False, "min_approvals": 3, "publish": False}, (
        "text becomes a number only where the schema asks for an integer"
    )
    assert tool_arguments(dashed.values, READINESS_SCHEMA)["min_approvals"] == -1, "an integer may carry a minus sign"
    for bad in (
        {"candidate": "v2.4.0", "publish": False, "min_approvals": "3.0"},
        {"candidate": "v2.4.0", "publish": False, "min_approvals": "three"},
        {"candidate": "v2.4.0", "publish": False, "force": True},
        {"candidate": "v2.4.0", "publish": "false"},
        {"candidate": True, "publish": False},
        {"candidate": "v2.4.0"},
    ):
        with pytest.raises(ArgumentError):
            tool_arguments(bad, READINESS_SCHEMA)

    catalog = Router(
        [
            skill_md("release-readiness", "Inspect a prepared release candidate.", "disable-model-invocation: true"),
            QUADRANTS[2],
        ],
        ExtensionPolicyAdapter(InvocationPolicy()),
    )
    host = SkillHost(catalog, {"release-readiness": Contract(READINESS_PARAMS, READINESS_SCHEMA)})
    assert host.prepare('/release-readiness "v2.4.0; rm -rf ~" "$(whoami) | tee"') == Ready(
        "release-readiness",
        {"candidate": "v2.4.0; rm -rf ~", "notes": "$(whoami) | tee", "dry_run": False, "min_approvals": 1, "publish": False},
    ), "arguments stay data from the command line to the tool"
    assert host.prepare("/release-readiness --dry-run") == NeedsInput("release-readiness", ("candidate",))
    assert host.prepare("/style-guide --anything") == Refused("style-guide", "blocked by host extension user-invocable=false"), (
        "the policy decides before any argument is bound"
    )


SESSION_SKILLS = [
    skill_md("release-readiness", "Inspect a prepared release candidate and report readiness.", "disable-model-invocation: true"),
    skill_md("incident-review", "Review incident timeline evidence."),
    skill_md("style-guide", "Apply the internal writing style guide.", "user-invocable: false"),
]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


def ndjson(chunks: list[str]) -> list[dict]:
    text = "".join(chunks)
    assert text.endswith("\n"), "every line ends with a newline"
    return [json.loads(line) for line in text.split("\n")[:-1]]


def at(turn: int, skill: str, stage: str, **extra) -> dict:
    return {"turn": turn, "skill": skill, "stage": stage, **extra}


@pytest.mark.skip("Part 4")
def test_session_lifecycle() -> None:
    """Activation lasts across turns, approvals last one turn, and compaction forces a reload."""
    router = Router(SESSION_SKILLS, ExtensionPolicyAdapter(InvocationPolicy()))
    revisions = {"release-readiness": "r1", "incident-review": "r7", "style-guide": "r3"}
    loads: list[str] = []

    def load_body(name: str) -> Body:
        loads.append(name)
        return Body(name, revisions[name], f"# {name}\n\nFollow the steps.\n")

    async def session():
        yield UserTurn("/release-readiness v2.4.0")
        yield Approve(("ci.status", "git.log"))
        yield ToolCall("release-readiness", "ci.status")
        yield UserTurn("/release-readiness v2.4.0 --dry-run")
        yield ToolCall("release-readiness", "git.log")
        yield Approve(("git.log",))
        yield Approve(("ci.status",))
        yield ToolCall("release-readiness", "git.log")
        yield UserTurn("/incident-review")
        yield Approve(("timeline.read",))
        revisions["release-readiness"] = "r2"  # its SKILL.md changed while the session went on
        yield Compaction()
        yield ToolCall("incident-review", "timeline.read")
        yield UserTurn("/style-guide")
        yield ToolCall("release-readiness", "git.log")
        yield Check("release-readiness", False)
        yield Approve(("git.log",))
        yield ToolCall("release-readiness", "git.log")
        yield Check("release-readiness", True)
        yield UserTurn("apply the internal writing style guide")
        yield ToolCall("incident-review", "git.log")
        yield Check("incident-review", True)
        yield UserTurn("what is the weather like")
        yield UserTurn("triage this incident timeline evidence")
        yield ToolCall("release-readiness", "git.log")
        yield Check("release-readiness", True)

    events = ndjson(collect(lifecycle(session(), router, load_body)))
    expected = {
        1: [
            at(1, "release-readiness", "eligible", actor="human"),
            at(1, "release-readiness", "selected", score=1.0),
            at(1, "release-readiness", "activated", revision="r1"),
            at(1, "release-readiness", "executing", tool="ci.status"),
        ],
        2: [
            at(2, "release-readiness", "denied", reason="tool not approved in this turn", tool="git.log"),
            at(2, "release-readiness", "executing", tool="git.log"),
        ],
        3: [
            at(3, "incident-review", "eligible", actor="human"),
            at(3, "incident-review", "selected", score=1.0),
            at(3, "incident-review", "activated", revision="r7"),
            at(3, "incident-review", "reloaded", revision="r7"),
            at(3, "incident-review", "executing", tool="timeline.read"),
        ],
        4: [
            at(4, "style-guide", "denied", reason="blocked by host extension user-invocable=false"),
            at(4, "release-readiness", "reloaded", revision="r2"),
            at(4, "release-readiness", "denied", reason="tool not approved in this turn", tool="git.log"),
            at(4, "release-readiness", "executing", tool="git.log"),
            at(4, "release-readiness", "completed"),
        ],
        5: [
            at(5, "incident-review", "denied", reason="tool not approved in this turn", tool="git.log"),
            at(5, "incident-review", "completed"),
        ],
        6: [],
        7: [
            at(7, "incident-review", "eligible", actor="model"),
            at(7, "incident-review", "selected", score=0.5),
            at(7, "incident-review", "activated", revision="r7"),
            at(7, "release-readiness", "denied", reason="skill not active", tool="git.log"),
        ],
    }
    messages = {
        1: "an explicit invocation goes through every stage before the skill works",
        2: "the skill stays active, and an approval lasts only until its turn ends",
        3: "after a compaction the body is reloaded before the skill works again",
        4: "each skill reloads its own body, and only a passing check completes it",
        5: "a turn that continues the active skills routes nothing, and starts with no approvals",
        6: "an implicit turn that selects nothing emits nothing",
        7: "a completed skill is gone until something activates it again",
    }
    for turn, lines in expected.items():
        assert [e for e in events if e.get("turn") == turn] == lines, messages[turn]
    assert events == [line for lines in expected.values() for line in lines], "lines come out in the order things happen"
    assert loads == ["release-readiness", "incident-review", "incident-review", "release-readiness", "incident-review"], (
        "bodies are loaded on activation and after a compaction, and at no other time"
    )

    pulled: list[int] = []

    async def busy():
        yield UserTurn("/incident-review")
        for i in range(200):
            pulled.append(i)
            yield Approve((f"tool-{i}",))

    async def first_line() -> str:
        agen = lifecycle(busy(), router, load_body)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert ndjson([asyncio.run(first_line())])[0]["stage"] == "eligible"
    assert len(pulled) <= 1, "each stage goes out as soon as it happens"


CONVERSATION = ("user: is v2.4.0 ready to ship?", "assistant: checking the candidate")
REVIEW_REQUEST = SkillRequest(
    "security-change-review",
    "Review dependency changes in the candidate diff",
    ("artifacts/release.diff",),
    "risk-report.json",
    "dependency files changed",
    None,
    2,
)


def scripted_skills(seen: dict) -> list[SkillSpec]:
    def release_readiness(ctx):
        seen[ctx.skill] = ctx.visible
        risk = ctx.call(REVIEW_REQUEST)
        changelog = ctx.call(
            SkillRequest("changelog-check", "Check the changelog entry", (), "changelog.json", "gate", {"changelog": "unverified"})
        )
        notes = ctx.call(SkillRequest("notes-writer", "Draft release notes", (), "release-notes.md", "report", ""))
        smoke = ctx.call(SkillRequest("smoke-test", "Smoke-test the candidate", (), "smoke.json", "gate", {"smoke": "not run"}, 3))
        summary = ctx.call(SkillRequest("summary-writer", "Summarize the findings", (), "summary.md", "report"))
        report = {"risk": risk, "changelog": changelog, "notes": notes, "smoke": smoke, "summary": summary}
        return Reply("readiness-report.json", report)

    def security_change_review(ctx):
        seen[ctx.skill] = ctx.visible
        seen["request"] = ctx.request
        audit = ctx.call(
            SkillRequest("dependency-audit", "Audit changed packages", ctx.request.inputs, "audit.json", "lockfile changed", None, 3)
        )
        again = ctx.call(SkillRequest("release-readiness", "Re-check readiness", (), "readiness-report.json", "context", "skipped", 2))
        return Reply("risk-report.json", {"risk": "low", "audit": audit, "readiness": again})

    def dependency_audit(ctx):
        seen[ctx.skill] = ctx.visible
        licenses = ctx.call(
            SkillRequest("license-scan", "Scan licenses", ctx.request.inputs, "licenses.json", "new packages", {"licenses": "unchecked"}, 5)
        )
        loop = ctx.call(SkillRequest("release-readiness", "Confirm the candidate", (), "readiness-report.json", "context", "skipped", 9))
        return Reply("audit.json", {"packages": 3, "licenses": licenses, "loop": loop})

    def license_scan(ctx):
        seen[ctx.skill] = ctx.visible
        return Reply("licenses.json", {"licenses": "ok"})

    def notes_writer(ctx):
        seen[ctx.skill] = ctx.visible
        return Reply("notes.md", "Fixed two bugs.")

    def smoke_test(ctx):
        seen[ctx.skill] = ctx.visible
        env = ctx.call(SkillRequest("flaky-env", "Provision a test environment", (), "env.json", "smoke needs an env", None, 3))
        return Reply("smoke.json", {"env": env})

    def summary_writer(ctx):
        seen[ctx.skill] = ctx.visible
        return Reply("summary.md", "ready, with caveats")

    return [
        SkillSpec("release-readiness", release_readiness),
        SkillSpec("security-change-review", security_change_review, "fork"),
        SkillSpec("dependency-audit", dependency_audit, "shared"),
        SkillSpec("license-scan", license_scan, "fork"),
        SkillSpec("notes-writer", notes_writer, "fork"),
        SkillSpec("smoke-test", smoke_test, "shared"),
        SkillSpec("summary-writer", summary_writer, "fork"),
    ]


def relay(name: str, target: str, max_depth: int = 5) -> SkillSpec:
    def run(ctx):
        got = ctx.call(SkillRequest(target, f"continue for {name}", (), "note", "chain", "cut", max_depth))
        return Reply("note", f"{name}<{got}")

    return SkillSpec(name, run)


def rows(call: Call, depth: int = 0) -> list[tuple]:
    out = [(depth, call.skill, call.status, call.detail, call.used_fallback)]
    for child in call.calls:
        out += rows(child, depth + 1)
    return out


@pytest.mark.skip("Part 5")
def test_skill_chains() -> None:
    """Skill-to-skill calls run on the host's chain: cycles and depth are refused, fallbacks or stops decide the rest."""
    seen: dict = {}
    tree = Composer(scripted_skills(seen)).run("release-readiness", "Is v2.4.0 ready?", CONVERSATION)
    found = rows(tree)
    assert (2, "release-readiness", "refused", "cycle: release-readiness -> security-change-review -> release-readiness", True) in found, (
        "a skill calling back into its caller is refused, with the whole path"
    )
    long_cycle = "cycle: release-readiness -> security-change-review -> dependency-audit -> release-readiness"
    assert (3, "release-readiness", "refused", long_cycle, True) in found, "a cycle through a third skill is refused too"
    assert (3, "license-scan", "refused", "depth 3 exceeds max_depth 2", True) in found, (
        "a deeper request cannot raise the depth an earlier request allowed"
    )
    assert (1, "changelog-check", "refused", "unknown skill changelog-check", True) in found, (
        "a missing skill is refused, and the caller goes on with the fallback"
    )
    assert (1, "notes-writer", "failed", "expected release-notes.md, got notes.md", True) in found, (
        "a reply under another contract is not a reply"
    )
    assert found[-3:] == [
        (1, "smoke-test", "failed", "stopped", True),
        (2, "flaky-env", "refused", "unknown skill flaky-env", False),
        (1, "summary-writer", "completed", "", False),
    ], "a failure without a fallback stops its caller, whose own fallback takes over, and the chain recovers"
    audit = {"packages": 3, "licenses": {"licenses": "unchecked"}, "loop": "skipped"}
    risk = {"risk": "low", "audit": audit, "readiness": "skipped"}
    assert tree == Call(
        "release-readiness",
        "completed",
        result={
            "risk": risk,
            "changelog": {"changelog": "unverified"},
            "notes": "",
            "smoke": {"smoke": "not run"},
            "summary": "ready, with caveats",
        },
        calls=(
            Call(
                "security-change-review",
                "completed",
                result=risk,
                calls=(
                    Call(
                        "dependency-audit",
                        "completed",
                        result=audit,
                        calls=(
                            Call("license-scan", "refused", "depth 3 exceeds max_depth 2", used_fallback=True),
                            Call("release-readiness", "refused", long_cycle, used_fallback=True),
                        ),
                    ),
                    Call(
                        "release-readiness",
                        "refused",
                        "cycle: release-readiness -> security-change-review -> release-readiness",
                        used_fallback=True,
                    ),
                ),
            ),
            Call("changelog-check", "refused", "unknown skill changelog-check", used_fallback=True),
            Call("notes-writer", "failed", "expected release-notes.md, got notes.md", used_fallback=True),
            Call("smoke-test", "failed", "stopped", used_fallback=True, calls=(Call("flaky-env", "refused", "unknown skill flaky-env"),)),
            Call("summary-writer", "completed", result="ready, with caveats"),
        ),
    ), "the tree records every call, in the order made, with what each one returned"
    assert seen == {
        "release-readiness": CONVERSATION,
        "security-change-review": (),
        "request": REVIEW_REQUEST,
        "dependency-audit": (),
        "notes-writer": (),
        "smoke-test": CONVERSATION,
        "summary-writer": (),
    }, "a forked skill sees only its request; a shared skill sees what its caller sees"

    alone = Composer(scripted_skills({})).run("smoke-test", "Smoke-test v2.4.0", CONVERSATION)
    assert alone == Call("smoke-test", "failed", "stopped", calls=(Call("flaky-env", "refused", "unknown skill flaky-env"),)), (
        "a stop with nothing above it fails the session's skill"
    )
    loop = Composer([relay("triage", "collect"), relay("collect", "summarize"), relay("summarize", "collect")]).run(
        "triage", "Triage the outage"
    )
    assert rows(loop) == [
        (0, "triage", "completed", "", False),
        (1, "collect", "completed", "", False),
        (2, "summarize", "completed", "", False),
        (3, "collect", "refused", "cycle: triage -> collect -> summarize -> collect", True),
    ] and loop.result == "triage<collect<summarize<cut", "a cycle below the session's skill is a cycle too"
    short = Composer([relay("triage", "collect"), relay("collect", "summarize", 1), relay("summarize", "collect")]).run(
        "triage", "Triage the outage"
    )
    assert rows(short) == [
        (0, "triage", "completed", "", False),
        (1, "collect", "completed", "", False),
        (2, "summarize", "refused", "depth 2 exceeds max_depth 1", True),
    ] and short.result == "triage<collect<cut", "a request's own max_depth bounds the call it makes"

    def first_input(ctx):
        return Reply("note", ctx.request.inputs[0])

    with pytest.raises(IndexError):
        Composer([relay("triage", "collect"), SkillSpec("collect", first_input)]).run("triage", "Triage the outage")
