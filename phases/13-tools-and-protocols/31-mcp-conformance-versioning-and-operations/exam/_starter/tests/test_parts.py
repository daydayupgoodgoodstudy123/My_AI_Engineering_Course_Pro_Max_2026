import asyncio
import base64
import hashlib
import itertools
import json
import re
import time
from dataclasses import replace

import pytest
from conformance.corpus import Transcript, TranscriptCorpus, fixture_filename, normalize_volatile
from conformance.differential import BOOKKEEPING, Difference, differential_report, sdk_differential
from conformance.evidence import canonical_json, digest, redact
from conformance.proxy import proxy_tap
from conformance.release import (
    CaseResult,
    HealthPolicy,
    ReleaseGate,
    attach_rollback_attestation,
    evaluate_health,
    rollback_evidence_ready,
)
from conformance.validate import Outcome, check_case, run_corpus, validate_response
from conformance.wire import TASKS_CAPABILITY, Violation

ABSENT = "<absent>"
SIGNER = "release-controller"
SIGNING_KEY = hashlib.sha256(b"deterministic non-secret exam fixture").digest()
TRUSTED = {SIGNER: SIGNING_KEY}
POLICY = HealthPolicy(min_samples=100, max_error_rate=0.01, max_p95_ms=500.0)
HEALTHY = {"sampleCount": 1200, "errorRate": 0.002, "p95Ms": 180.0}
SECRETS = ("sk-live-4f1c9", "ak-77d0e", "rt-9x2qa", "cs-51aab", "sid=c0ffee")
SDK_OK = {
    "semanticMatch": True,
    "differences": [],
    "rawDigest": digest({"tools": []}),
    "sdkDigest": digest({"tools": []}),
}
PROXY_OK = {
    "passed": True,
    "issues": [],
    "ingressDigest": digest("ingress"),
    "originDigest": digest("origin"),
    "egressDigest": digest("egress"),
    "evidence": {"egress": {"status": 200, "headers": {"Set-Cookie": "sid=c0ffee; HttpOnly"}}},
}


def modern_meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def rpc(method: str, request_id: int | None = 1, **params) -> dict:
    body = {"jsonrpc": "2.0", "method": method, "params": {"_meta": modern_meta(), **params}}
    if request_id is not None:
        body["id"] = request_id
    return body


def tool(name: str, description: str = "Look up the stock for one SKU.") -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}}},
    }


def without_absent(fields: dict) -> dict:
    return {key: value for key, value in fields.items() if value != ABSENT}


def signed_rollback(**changes) -> dict:
    evidence = {
        "version": "1.0.0",
        "healthy": True,
        "registryStatus": "active",
        "admissionEvidenceDigest": digest({"release": "1.0.0"}),
        "artifactDigest": digest({"artifact": "inventory-1.0.0"}),
        "descriptorDigest": digest({"tools": ["inventory_get"]}),
    }
    evidence.update(changes)
    return attach_rollback_attestation(without_absent(evidence), SIGNER, SIGNING_KEY)


def canary_case(i: int, bearer: str = "sk-live-4f1c9", stock: int = 12) -> CaseResult:
    """A tools/call transcript as a canary captured it, credentials and all."""
    sku = f"A-{i:04d}"
    evidence = {
        "headers": {
            "Authorization": f"Bearer {bearer}",
            "X-Api-Key": "ak-77d0e",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": "inventory_get",
        },
        "request": rpc(
            "tools/call",
            i,
            name="inventory_get",
            arguments={"sku": sku, "access_token": "rt-9x2qa", "tokenCount": 3},
        ),
        "responseStatus": 200,
        "responseBody": {
            "jsonrpc": "2.0",
            "id": i,
            "result": {
                "resultType": "complete",
                "content": [{"type": "text", "text": f"{sku}: {stock} in stock"}],
                "structuredContent": {"sku": sku, "stock": stock, "client.secret": "cs-51aab"},
            },
        },
    }
    return CaseResult(f"golden-inventory-{i:04d}", True, "accepted as expected", evidence)


def evaluate(gate: ReleaseGate, cases, health=HEALTHY, rollback=None, sdk=None) -> dict:
    return gate.evaluate(
        cases,
        [SDK_OK] if sdk is None else sdk,
        [PROXY_OK],
        health,
        signed_rollback() if rollback is None else rollback,
    )


@pytest.mark.skip("Part 1")
def test_release_gate() -> None:
    """Promotion needs redacted evidence, a real health window and a pinned, active rollback target."""
    gate = ReleaseGate(POLICY, TRUSTED)
    cases = [canary_case(i) for i in range(3)]
    report = evaluate(gate, cases)
    assert report["action"] == "promote", f"every evidence source passes: {report['reasons']}"
    shipped = canonical_json(report)
    leaked = [secret for secret in SECRETS if secret in shipped]
    assert not leaked, f"no credential reaches the report, however its key is spelled: {leaked}"
    variants = [
        "Authorization",
        "proxy-authorization",
        "Set-Cookie",
        "x_api_key",
        "API.KEY",
        "accessToken",
        "access-token",
        "access.token",
        "REFRESH_TOKEN",
        "registration.access.token",
        "Client-Secret",
        "PassWord",
    ]
    assert redact({key: "private" for key in variants}) == {key: "[REDACTED]" for key in variants}, (
        "case, hyphen, underscore and dot variants of a secret key share one policy"
    )
    kept = {
        "query": "where is order 7?",
        "tokenCount": 3,
        "secretary": "Ada",
        "passwordPolicy": {"minLength": 12},
        "note": "Bearer is a scheme name",
    }
    assert redact(kept) == kept, "only keys whose canonical form is on the denylist are redacted"
    nested = {"batch": [{"params": {"arguments": {"Password": "pw-1", "sku": "A-1"}}}]}
    assert redact(nested) == {"batch": [{"params": {"arguments": {"Password": "[REDACTED]", "sku": "A-1"}}}]}, (
        "secrets are redacted at any depth, inside lists too"
    )
    assert redact({"secret": {"value": "s-1"}, "Cookie": ["a=1", "b=2"], "sku": "A-1"}) == {
        "secret": "[REDACTED]",
        "Cookie": "[REDACTED]",
        "sku": "A-1",
    }, "a secret key's whole value is replaced, whatever its type"

    no_samples = {"errorRate": 0.0, "p95Ms": 90.0}
    assert evaluate(gate, cases, health=no_samples)["action"] == "rollback", (
        "a canary that reported no samples never promotes"
    )
    assert evaluate_health({"sampleCount": 100, "errorRate": 0.01, "p95Ms": 500}, POLICY) == (True, []), (
        "a window exactly at the thresholds is healthy"
    )
    for window in (
        {"sampleCount": 99, "errorRate": 0.0, "p95Ms": 90.0},
        {"sampleCount": 1200, "errorRate": 0.0101, "p95Ms": 90.0},
        {"sampleCount": 1200, "errorRate": 0.0, "p95Ms": 500.5},
        {"sampleCount": 1200, "p95Ms": 90.0},
        {"sampleCount": 1200, "errorRate": 0.0},
        {"sampleCount": "1200", "errorRate": 0.0, "p95Ms": 90.0},
        {"sampleCount": 1200.0, "errorRate": 0.0, "p95Ms": 90.0},
        {"sampleCount": 1200, "errorRate": None, "p95Ms": 90.0},
        {"sampleCount": 1200, "errorRate": 0.0, "p95Ms": "90"},
    ):
        healthy, reasons = evaluate_health(window, POLICY)
        assert healthy is False and reasons, (
            f"a missing, mistyped or out-of-bounds observation fails the window: {window}"
        )

    failing = [canary_case(0), replace(canary_case(1), passed=False, detail="broke task-payload")]
    report = evaluate(gate, failing)
    assert report["action"] == "rollback", "a failing candidate rolls back to a ready target"
    assert "transcript failed: golden-inventory-0001" in report["reasons"], "the reasons name the failed case"
    deprecated = signed_rollback(registryStatus="deprecated")
    assert evaluate(gate, failing, rollback=deprecated)["action"] == "hold", (
        "a failing candidate holds when its rollback target is no longer active in the Registry"
    )
    assert evaluate(gate, cases, rollback=deprecated)["action"] == "hold", (
        "promotion needs a ready rollback target too"
    )
    empty = evaluate(gate, [])
    assert empty["action"] == "rollback" and "conformance transcript evidence is empty" in empty["reasons"], (
        "empty transcript evidence never promotes"
    )
    assert rollback_evidence_ready(signed_rollback(), TRUSTED), "signed, pinned, active evidence is ready"
    for field, value in (
        ("registryStatus", "Active"),
        ("registryStatus", "deleted"),
        ("registryStatus", None),
        ("registryStatus", ABSENT),
        ("artifactDigest", "sha256:" + "a" * 64),
        ("descriptorDigest", "pending"),
        ("admissionEvidenceDigest", "z" * 64),
        ("artifactDigest", "a" * 64 + "\n"),
        ("descriptorDigest", "a" * 63),
        ("artifactDigest", ABSENT),
        ("healthy", "yes"),
        ("version", " "),
    ):
        assert not rollback_evidence_ready(signed_rollback(**{field: value}), TRUSTED), (
            f"{field}={value!r} is not rollback evidence, even when signed"
        )
    tampered = signed_rollback()
    tampered["version"] = "9.9.9"
    assert not rollback_evidence_ready(tampered, TRUSTED), "the signature covers every field"
    assert not rollback_evidence_ready(signed_rollback(), {"someone-else": SIGNING_KEY}), (
        "only a trusted signer counts"
    )

    many = [canary_case(i) for i in range(320)]
    start = time.perf_counter()
    big = evaluate(gate, many)
    elapsed = time.perf_counter() - start
    assert big["action"] == "promote" and len(big["caseDigests"]) == 320, "every case gets a digest"
    assert elapsed < 0.15, f"the gate should stay fast on a large corpus: {elapsed:.2f} s for 320 cases"

    base = evaluate(gate, cases)
    rotated = evaluate(gate, [canary_case(i, bearer="sk-live-rotated") for i in range(3)])
    assert (rotated["caseDigests"], rotated["evidenceDigest"]) == (
        base["caseDigests"],
        base["evidenceDigest"],
    ), "digests cover the redacted evidence, so rotating a credential leaves them alone"
    changed = evaluate(gate, [canary_case(0), canary_case(1, stock=11), canary_case(2)])
    first, second = cases[0].name, cases[1].name
    assert changed["caseDigests"][second] != base["caseDigests"][second], (
        "a change to anything but a secret changes that case's digest"
    )
    assert changed["evidenceDigest"] != base["evidenceDigest"], (
        "a change to anything but a secret changes the bundle digest"
    )
    assert changed["caseDigests"][first] == base["caseDigests"][first], (
        "each case digest covers that case's own evidence"
    )
    assert base["caseDigests"][first] == digest(redact(cases[0].evidence)), (
        "a case digest is the digest of that case's redacted evidence"
    )


def must_raise(error: type[BaseException], message: str, call, *args) -> None:
    try:
        call(*args)
    except error:
        return
    pytest.fail(message)


def resume_name_header() -> str:
    return "=?base64?" + base64.b64encode("résumé_lookup".encode("utf-8")).decode("ascii") + "?="


def corpus_fixtures() -> list[Transcript]:
    return [
        Transcript(
            "golden-modern-list",
            "modern",
            {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"},
            rpc("tools/list", 1),
            200,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "resultType": "complete",
                    "tools": [tool("inventory_get")],
                    "futureHint": {"safeToIgnore": True},
                },
            },
        ),
        Transcript(
            "negative-conflicting-method-headers",
            "modern",
            {
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/call",
                "mcp-method": "tools/list",
                "Mcp-Name": "inventory_get",
            },
            rpc("tools/call", 2, name="inventory_get", arguments={"sku": "A-0002"}),
            400,
            {"jsonrpc": "2.0", "id": 2, "error": {"code": -32020, "message": "conflicting Mcp-Method"}},
            expect=-32020,
        ),
        Transcript(
            "golden-notification-no-response",
            "modern",
            {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "notifications/course/progress"},
            rpc("notifications/course/progress", None, progress=0.5),
            202,
            None,
        ),
        Transcript(
            "golden-legacy-list",
            "legacy",
            {"mcp-protocol-version": "2025-11-25"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            200,
            {"jsonrpc": "2.0", "id": 3, "result": {"tools": []}},
        ),
        Transcript(
            "Golden Résumé Lookup",
            "modern",
            {
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/call",
                "Mcp-Name": resume_name_header(),
            },
            rpc("tools/call", 4, name="résumé_lookup", arguments={"query": "naïve café ☕", "limit": 3}),
            200,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "result": {"resultType": "complete", "content": [{"type": "text", "text": "2 matches\r\n"}]},
            },
        ),
        Transcript(
            "negative-task-without-capability",
            "modern",
            {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "report_generate"},
            rpc("tools/call", 5, name="report_generate", arguments={}),
            200,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "result": {
                    "resultType": "task",
                    "taskId": "task-0",
                    "status": "working",
                    "createdAt": "1970-01-01T00:00:00Z",
                    "lastUpdatedAt": "1970-01-01T00:00:00Z",
                    "ttlMs": None,
                },
            },
            expect="unknown-result-type",
        ),
        Transcript(
            "golden-task-result",
            "modern",
            {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "report_generate"},
            rpc("tools/call", 6, name="report_generate", arguments={}),
            200,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "result": {
                    "resultType": "task",
                    "taskId": "task-0",
                    "status": "working",
                    "createdAt": "1970-01-01T00:00:00Z",
                    "lastUpdatedAt": "1970-01-01T00:00:00Z",
                    "ttlMs": 900000,
                    "pollIntervalMs": 1000,
                },
            },
            capabilities=frozenset({TASKS_CAPABILITY, "io.example/audit"}),
        ),
    ]


def task_call(name: str, task_id, created, updated, windows=(), expect=None) -> Transcript:
    return Transcript(
        name,
        "modern",
        {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "report_generate"},
        rpc(
            "tools/call",
            12,
            name="report_generate",
            arguments={"windows": [{"createdAt": start, "days": 7} for start in windows]},
        ),
        200,
        {
            "jsonrpc": "2.0",
            "id": 12,
            "result": {
                "resultType": "task",
                "taskId": task_id,
                "status": "working",
                "createdAt": created,
                "lastUpdatedAt": updated,
                "ttlMs": 900000,
            },
        },
        capabilities=frozenset({TASKS_CAPABILITY}),
        expect=expect,
    )


@pytest.mark.skip("Part 2")
def test_transcript_corpus(tmp_path) -> None:
    """Fixtures come back exactly as recorded: one JSON file per case, with its era."""
    assert fixture_filename("Negative: Header/Body Mismatch") == "negative-header-body-mismatch.json", (
        "a file name is the case name lowercased, each run of other characters one '-'"
    )
    assert fixture_filename("../../etc/passwd") == "etc-passwd.json", "a case name never leaves the corpus"
    must_raise(ValueError, "a name with no letters or digits has no file", fixture_filename, "?!")

    root = tmp_path / "fixtures"
    corpus = TranscriptCorpus(root)
    fixtures = corpus_fixtures()
    paths = [corpus.save(transcript) for transcript in fixtures]
    assert [path.name for path in paths] == [
        "golden-modern-list.json",
        "negative-conflicting-method-headers.json",
        "golden-notification-no-response.json",
        "golden-legacy-list.json",
        "golden-r-sum-lookup.json",
        "negative-task-without-capability.json",
        "golden-task-result.json",
    ], "each case is saved under fixture_filename(name)"
    assert sorted(path.name for path in root.iterdir()) == sorted(path.name for path in paths), (
        "one file per case, and nothing else"
    )

    reopened = TranscriptCorpus(root)
    assert reopened.names() == sorted(transcript.name for transcript in fixtures), (
        "names come back exactly as given, read from the files"
    )
    conflicting = reopened.load("negative-conflicting-method-headers")
    assert sorted(conflicting.headers) == ["MCP-Protocol-Version", "Mcp-Method", "Mcp-Name", "mcp-method"], (
        "header names keep their case: Mcp-Method and mcp-method are two captured headers"
    )
    for transcript in fixtures:
        assert reopened.load(transcript.name) == transcript, f"{transcript.name} comes back exactly as recorded"
    extensions = frozenset(f"io.example/ext-{letter}" for letter in "hdbgafce")
    spread = corpus.save(replace(fixtures[0], name="golden-many-extensions", capabilities=extensions))
    assert json.loads(spread.read_text(encoding="utf-8"))["capabilities"] == sorted(extensions), (
        "capabilities are stored as a sorted list"
    )
    spread.unlink()
    assert json.loads(paths[-1].read_text(encoding="utf-8")) == {
        "name": "golden-task-result",
        "era": "modern",
        "capabilities": ["io.example/audit", TASKS_CAPABILITY],
        "headers": fixtures[-1].headers,
        "request": fixtures[-1].request,
        "responseStatus": 200,
        "responseBody": fixtures[-1].response_body,
        "expect": None,
    }, "the file holds the documented record"

    for other in ("Golden Modern List", "GOLDEN-MODERN-LIST"):
        must_raise(
            ValueError,
            f"two names that share a fixture file are refused: {other!r}",
            corpus.save,
            replace(fixtures[0], name=other, response_status=500),
        )
    assert json.loads(paths[0].read_text(encoding="utf-8"))["name"] == "golden-modern-list", (
        "a refused name leaves the other case's file alone"
    )
    assert reopened.load("golden-modern-list") == fixtures[0], "a refused name leaves the other case alone"
    must_raise(KeyError, "load finds a case by its exact name", reopened.load, "Golden Modern List")
    must_raise(KeyError, "an unknown case is a KeyError", reopened.load, "golden-modern-lists")
    rerecorded = replace(fixtures[0], response_status=503, response_body=None)
    corpus.save(rerecorded)
    assert reopened.load("golden-modern-list") == rerecorded, "saving a name again replaces its fixture"
    must_raise(
        ValueError,
        "an unknown era is refused",
        corpus.save,
        replace(fixtures[0], name="golden-bad-era", era="2026-07-28"),
    )

    hand_written = {
        "name": "golden-hand-written",
        "era": "modern",
        "headers": {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"},
        "request": rpc("tools/list", 1),
        "responseStatus": 200,
        "responseBody": {"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete", "tools": []}},
    }
    (root / "golden-hand-written.json").write_text(json.dumps(hand_written), encoding="utf-8")
    assert corpus.load("golden-hand-written") == Transcript(
        "golden-hand-written",
        "modern",
        hand_written["headers"],
        hand_written["request"],
        200,
        hand_written["responseBody"],
    ), "a hand-written fixture in the documented format loads, without capabilities or expect"
    (root / "golden-hand-written.json").write_text(json.dumps({**hand_written, "era": "2026-07-28"}), encoding="utf-8")
    must_raise(ValueError, "a protocol version is not an era", corpus.load, "golden-hand-written")
    del hand_written["era"]
    (root / "golden-hand-written.json").write_text(json.dumps(hand_written), encoding="utf-8")
    must_raise(
        ValueError,
        "a fixture without an era is refused: the era decides how its response is judged",
        corpus.load,
        "golden-hand-written",
    )
    (root / "golden-hand-written.json").unlink()

    first = task_call(
        "golden-task-call",
        "t-8f3a1c",
        "2026-08-21T10:00:00Z",
        "2026-08-21T10:00:02Z",
        windows=("2026-08-01T00:00:00Z", "2026-08-08T00:00:00Z"),
    )
    path = corpus.save(first)
    recorded = path.read_bytes()
    corpus.save(
        task_call(
            "golden-task-call",
            "t-02bd77",
            "2026-09-02T17:45:10Z",
            "2026-09-02T17:45:11Z",
            windows=("2026-08-29T00:00:00Z", "2026-09-05T00:00:00Z"),
        )
    )
    assert path.read_bytes() == recorded, "re-recording the same behaviour writes the same fixture"
    stored = reopened.load("golden-task-call")
    result = stored.response_body["result"]
    assert (result["taskId"], result["createdAt"], result["lastUpdatedAt"]) == (
        "task-0",
        "1970-01-01T00:00:00Z",
        "1970-01-01T00:00:00Z",
    ), "volatile ids and timestamps are normalized before they are stored"
    assert stored.request["params"]["arguments"]["windows"] == [
        {"createdAt": "1970-01-01T00:00:00Z", "days": 7}
    ] * 2, "volatile values are normalized at any depth, inside lists too"
    assert stored == normalize_volatile(first), "load returns what normalize_volatile made of the capture"
    assert first.response_body["result"]["taskId"] == "t-8f3a1c", "normalizing leaves the live capture alone"
    assert first.request["params"]["arguments"]["windows"][0]["createdAt"] == "2026-08-01T00:00:00Z", (
        "normalizing leaves the live capture alone, nested values too"
    )
    malformed = task_call("negative-task-required-fields", "", 1724234400, None, expect="task-payload")
    corpus.save(malformed)
    assert reopened.load("negative-task-required-fields") == malformed, (
        "an empty, numeric or null value is what a negative case recorded, and it stays"
    )


def ok(result, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def fail(code, message="refused", request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def judged(request, status, body, era="modern", capabilities=frozenset()):
    """The Outcome of a valid response, or the name of the rule it breaks."""
    try:
        return validate_response(request, status, body, era, capabilities)
    except Violation as violation:
        return violation.rule


def task(**changes) -> dict:
    result = {
        "resultType": "task",
        "taskId": "t-2",
        "status": "working",
        "createdAt": "2026-08-21T10:00:00Z",
        "lastUpdatedAt": "2026-08-21T10:00:00Z",
        "ttlMs": 900000,
        "pollIntervalMs": 1000,
    }
    result.update(changes)
    return without_absent(result)


def completion(values, **extra) -> dict:
    return {"resultType": "complete", "completion": {"values": values, **extra}}


@pytest.mark.skip("Part 3")
def test_response_conformance(tmp_path) -> None:
    """Responses are judged as they crossed the wire, fixtures prove their exact rule, and the
    corpus decides the release."""
    listing = rpc("tools/list")
    call = rpc("tools/call", 1, name="report_generate", arguments={})
    complete = rpc("completion/complete")
    tasks = frozenset({TASKS_CAPABILITY})
    good_tools = {"resultType": "complete", "tools": [tool("inventory_get"), tool("inventory_put")]}

    assert judged(listing, 200, ok({**good_tools, "futureHint": {"mode": "new"}})) == Outcome(
        "result", "complete"
    ), "an unknown member beside a known result is additive"
    assert judged(listing, 200, ok({"resultType": "future_mode", "tools": []})) == "unknown-result-type", (
        "an unknown resultType is a lifecycle the client cannot follow"
    )
    assert judged(listing, 200, ok({"resultType": {"kind": "complete"}, "tools": []})) == "unknown-result-type", (
        "a resultType that is not a string is unknown"
    )
    assert judged(listing, 200, ok({"resultType": "surprise", "tools": "none"})) == "unknown-result-type", (
        "the discriminator is checked before the payload"
    )
    assert judged(listing, 200, ok({"tools": []})) == "missing-result-type", (
        "a modern result names its resultType"
    )
    legacy_body = ok({"tools": [tool("inventory_get")]})
    assert judged(listing, 200, legacy_body, era="legacy") == Outcome("result", "complete", inferred=True), (
        "a legacy result without resultType is complete"
    )
    assert legacy_body == ok({"tools": [tool("inventory_get")]}), (
        "judging a legacy result leaves the wire evidence as it was: no synthesized resultType"
    )
    assert judged(listing, 200, ok({"tools": "none"}), era="legacy") == "tools-payload", (
        "an inferred complete still carries the method's payload"
    )
    assert judged(listing, 200, ok({"resultType": "surprise", "tools": []}), era="legacy") == (
        "unknown-result-type"
    ), "the legacy era only excuses a missing resultType"

    assert judged(listing, 200, ok({"resultType": "input_required", "tools": []})) == "method-result-type", (
        "tools/list answers complete"
    )
    assert judged(complete, 200, ok({"resultType": "input_required"})) == "method-result-type", (
        "completion/complete answers complete"
    )
    assert judged(call, 200, ok({"resultType": "input_required"})) == Outcome("result", "input_required"), (
        "tools/call may answer input_required"
    )
    assert judged(call, 200, ok(task())) == "unknown-result-type", "task needs the negotiated Tasks capability"
    assert judged(call, 200, ok(task()), capabilities=tasks) == Outcome("result", "task"), (
        "with the Tasks capability, tools/call may answer with a task"
    )
    assert judged(rpc("server/discover"), 200, ok(task()), capabilities=tasks) == "method-result-type", (
        "only tools/call answers with a task"
    )

    assert judged(listing, 200, ok({"resultType": "complete", "tools": []})) == Outcome("result", "complete"), (
        "an empty tools/list is conformant"
    )
    assert judged(listing, 200, ok({"resultType": "complete"})) == "tools-payload", (
        "a complete tools/list carries a tools array"
    )
    for why, tools in (
        ("duplicate names", [tool("inventory_get"), tool("inventory_get", "Same name, other text.")]),
        ("an empty name", [tool("")]),
        ("an array inputSchema", [{**tool("inventory_get"), "inputSchema": {"type": "array"}}]),
        ("no description", [{"name": "inventory_get", "inputSchema": {"type": "object"}}]),
        ("an empty description", [tool("inventory_get", "")]),
        ("no inputSchema", [{"name": "inventory_get", "description": "No schema."}]),
        ("a tool that is not an object", ["inventory_get"]),
    ):
        assert judged(listing, 200, ok({"resultType": "complete", "tools": tools})) == "tools-payload", (
            f"a tools/list with {why} is not conformant, whatever its resultType says"
        )
    hundred = [f"env-{i:03d}" for i in range(100)]
    assert judged(complete, 200, ok(completion(hundred, total=250, hasMore=True))) == Outcome(
        "result", "complete"
    ), "a completion may return 100 values"
    assert judged(complete, 200, ok(completion(["development", "staging"]))) == Outcome("result", "complete"), (
        "total and hasMore are optional"
    )
    assert judged(complete, 200, ok(completion(["development", "staging"], total=2))) == Outcome(
        "result", "complete"
    ), "total may equal the number of values"
    for why, broken in (
        ("101 values", completion(hundred + ["env-100"])),
        ("a total below the number of values", completion(["development", "staging"], total=1)),
        ("a string total", completion(["development", "staging"], total="3")),
        ("a boolean total", completion(["development"], total=True)),
        ("a string hasMore", completion(["development"], hasMore="false")),
        ("a value that is not a string", completion(["staging", 7])),
        ("no completion object", {"resultType": "complete", "values": ["staging"]}),
        ("no values", {"resultType": "complete", "completion": {"total": 0}}),
    ):
        assert judged(complete, 200, ok(broken)) == "completion-payload", (
            f"a completion/complete with {why} is not conformant"
        )
    assert judged(call, 200, ok(task(ttlMs=None)), capabilities=tasks) == Outcome("result", "task"), (
        "ttlMs may be null"
    )
    assert judged(call, 200, ok(task(ttlMs=0, pollIntervalMs=0)), capabilities=tasks) == Outcome("result", "task"), (
        "zero is a non-negative ttlMs and pollIntervalMs"
    )
    for why, broken in (
        ("no ttlMs", task(ttlMs=ABSENT)),
        ("a negative ttlMs", task(ttlMs=-1)),
        ("a boolean ttlMs", task(ttlMs=True)),
        ("an unknown status", task(status="running")),
        ("an empty createdAt", task(createdAt="")),
        ("no taskId", task(taskId=ABSENT)),
        ("a negative pollIntervalMs", task(pollIntervalMs=-5)),
    ):
        assert judged(call, 200, ok(broken), capabilities=tasks) == "task-payload", (
            f"a task with {why} is not conformant"
        )

    assert judged(listing, 200, {**ok(good_tools), "jsonrpc": "1.0"}) == "envelope", "jsonrpc is exactly 2.0"
    assert judged(listing, 200, [ok(good_tools)]) == "envelope", "a response is one JSON-RPC object"
    assert judged(listing, 200, {}) == "envelope", "an empty object is a body, but not a JSON-RPC response"
    assert judged(listing, 200, {**ok(good_tools), "error": {"code": -32603, "message": "both"}}) == (
        "exclusive"
    ), "a response holds a result or an error, not both"
    assert judged(listing, 200, {"jsonrpc": "2.0", "id": 1}) == "exclusive", "a response holds one of them"
    assert judged(listing, 400, fail("-32020")) == "error-shape", "an error code is an integer"
    assert judged(listing, 400, {"jsonrpc": "2.0", "id": 1, "error": {"code": -32020}}) == "error-shape", (
        "an error carries a message"
    )
    assert judged(listing, 400, {"jsonrpc": "2.0", "id": 1, "error": "header mismatch"}) == "error-shape", (
        "an error is an object"
    )
    assert judged(call, 400, fail(-32020)) == Outcome("error", error_code=-32020), (
        "a -32020 refusal on HTTP 400 is conformant"
    )
    assert judged(call, 500, fail(-32020)) == "error-status", "a proxy-collapsed -32020 is not conformant"
    assert judged(call, 400, fail(-32022)) == Outcome("error", error_code=-32022), "-32022 travels with 400"
    assert judged(call, 401, fail(-32021)) == "error-status", "-32021 travels with HTTP 400"
    assert judged(call, 404, fail(-32601)) == Outcome("error", error_code=-32601), "-32601 travels with 404"
    assert judged(call, 400, fail(-32601)) == "error-status", "method not found travels with HTTP 404"
    assert judged(call, 500, fail(-32603)) == Outcome("error", error_code=-32603), (
        "codes outside PROTOCOL_ERROR_STATUS are not tied to a status"
    )
    assert judged(listing, 202, ok(good_tools)) == "result-status", "a result travels with HTTP 200"
    assert judged(call, 200, ok(None)) == "result-shape", "middleware that wraps a None return is caught"
    assert judged(call, 200, None) == "missing-body", "a request gets a JSON-RPC response"
    assert judged(call, 500, None) == "missing-body", "a bare HTTP 500 is not a JSON-RPC response"

    note = rpc("notifications/course/progress", None, progress=0.5)
    assert judged(note, 202, None) == Outcome("notification"), "a notification gets 202 and nothing else"
    for status, body in (
        (200, {"jsonrpc": "2.0", "result": None}),
        (202, {"jsonrpc": "2.0", "result": None}),
        (202, {}),
        (204, None),
        (200, None),
    ):
        assert judged(note, status, body) == "notification", (
            f"a notification never gets a JSON-RPC response: HTTP {status} with {body!r}"
        )

    golden = Transcript("golden-list", "modern", {"Mcp-Method": "tools/list"}, listing, 200, ok(good_tools))
    checked = check_case(golden)
    assert checked == CaseResult(
        "golden-list",
        True,
        checked.detail,
        {"headers": golden.headers, "request": listing, "responseStatus": 200, "responseBody": ok(good_tools)},
    ), "a golden case passes and carries its raw evidence"
    unknown = replace(
        golden, name="negative-unknown", response_body=ok({"resultType": "surprise"}), expect="unknown-result-type"
    )
    assert check_case(unknown).passed, "a negative case passes when the response breaks its rule"
    wrong_rule = replace(unknown, response_body={**ok({"resultType": "surprise"}), "jsonrpc": "1.0"})
    assert not check_case(wrong_rule).passed, "a negative case proves its own rule, not just any failure"
    assert not check_case(replace(unknown, response_body=ok(good_tools))).passed, (
        "a negative case fails when the response is accepted"
    )
    mismatch = Transcript(
        "negative-header-body-mismatch",
        "modern",
        {"Mcp-Method": "tools/call", "Mcp-Name": "inventory_delete"},
        rpc("tools/call", 2, name="inventory_get", arguments={}),
        400,
        fail(-32020, "Mcp-Name header mismatch", request_id=2),
        expect=-32020,
    )
    assert check_case(mismatch).passed, "the server refused with the expected code, on HTTP 400"
    for why, broken in (
        ("on HTTP 500", replace(mismatch, response_status=500)),
        ("with another code", replace(mismatch, response_body=fail(-32022, request_id=2))),
        ("as a bare HTTP 500", replace(mismatch, response_status=500, response_body=None)),
        ("as a result", replace(mismatch, response_status=200, response_body=ok({"resultType": "complete"}, 2))),
    ):
        assert not check_case(broken).passed, (
            f"a refusal counts only as a valid JSON-RPC error with the expected code, not {why}"
        )
    assert not check_case(replace(golden, response_status=404, response_body=fail(-32601))).passed, (
        "a golden case expects a result, not a refusal"
    )

    corpus = TranscriptCorpus(tmp_path / "corpus")
    for transcript in corpus_fixtures() + [golden, unknown, mismatch]:
        corpus.save(transcript)
    cases = run_corpus(corpus)
    assert [case.name for case in cases] == corpus.names() and all(case.passed for case in cases), (
        f"every stored fixture reaches its expected outcome: {[c.name for c in cases if not c.passed]}"
    )
    gate = ReleaseGate(POLICY, TRUSTED)
    assert evaluate(gate, cases)["action"] == "promote", "a conformant corpus promotes"
    corpus.save(replace(unknown, name="negative-unknown-but-accepted", response_body=ok(good_tools)))
    report = evaluate(gate, run_corpus(corpus))
    assert report["action"] == "rollback" and report["reasons"] == [
        "transcript failed: negative-unknown-but-accepted"
    ], "one fixture that misses its expectation rolls the release back"


EXCHANGE_OK = {
    "jsonrpc": "2.0",
    "id": 7,
    "result": {"resultType": "complete", "content": [{"type": "text", "text": "12 in stock"}]},
}
REWRITTEN = {
    "jsonrpc": "2.0",
    "id": 7,
    "result": {"resultType": "complete", "content": [{"type": "text", "text": "12 in stock (cached)"}]},
}
MISMATCH = {"jsonrpc": "2.0", "id": 8, "error": {"code": -32020, "message": "Mcp-Name header mismatch"}}
NOT_FOUND = {"jsonrpc": "2.0", "id": 9, "error": {"code": -32601, "message": "Method not found"}}
GENERIC = {"message": "upstream failed"}
ISSUED = {
    "jsonrpc": "2.0",
    "id": 10,
    "result": {"resultType": "complete", "structuredContent": {"accessToken": "at-raw-1234", "expiresIn": 3600}},
}
ISSUED_REDACTED = {
    "jsonrpc": "2.0",
    "id": 10,
    "result": {"resultType": "complete", "structuredContent": {"accessToken": "[REDACTED]", "expiresIn": 3600}},
}


def view(exchange: str, kind: str, at: int, status: int | None = None, body=None) -> dict:
    event = {"exchange": exchange, "view": kind, "at": at}
    if kind == "ingress":
        event["headers"] = {"Authorization": "Bearer sk-live-4f1c9", "Mcp-Method": "tools/call"}
        event["body"] = rpc("tools/call", 7, name="inventory_get", arguments={"sku": "A-0007"})
    else:
        event["status"] = status
        event["headers"] = {"Content-Type": "application/json"}
        event["body"] = body
    return event


def exchange(name: str, at: int, origin_status: int, origin_body, egress_status: int, egress_body) -> list[dict]:
    return [
        view(name, "ingress", at),
        view(name, "origin", at + 1, origin_status, origin_body),
        view(name, "egress", at + 2, egress_status, egress_body),
    ]


SCRIPT = [
    view("ex-ok", "egress", 1000, 200, EXCHANGE_OK),
    view("ex-ok", "ingress", 1001),
    view("ex-collapse", "ingress", 1002),
    view("ex-ok", "origin", 1003, 200, EXCHANGE_OK),
    view("ex-collapse", "origin", 1004, 400, MISMATCH),
    view("ex-collapse", "egress", 1005, 500, GENERIC),
    view("ex-404", "ingress", 1100),
    view("ex-404", "ingress", 1100),
    view("ex-404", "ingress", 1101),
    view("ex-404", "egress", 1102, 500, NOT_FOUND),
    view("ex-404", "origin", 1103, 404, NOT_FOUND),
    view("ex-status", "ingress", 1200),
    view("ex-status", "origin", 1201, 200, EXCHANGE_OK),
    view("ex-status", "egress", 1202, 502, EXCHANGE_OK),
    view("ex-issued", "origin", 1300, 200, ISSUED),
    view("ex-issued", "ingress", 1301),
    view("ex-late", "ingress", 1302),
    view("ex-issued", "egress", 1303, 200, ISSUED_REDACTED),
    view("ex-ok", "egress", 1304, 200, EXCHANGE_OK),
    view("ex-late", "origin", 1400, 200, EXCHANGE_OK),
    view("ex-gap", "origin", 1350, 200, EXCHANGE_OK),
    view("ex-body", "ingress", 4000),
    view("ex-body", "origin", 4001, 200, EXCHANGE_OK),
    view("ex-body", "egress", 4002, 200, REWRITTEN),
    view("ex-edge", "ingress", 6302),
    view("ex-edge", "origin", 6400, 200, EXCHANGE_OK),
    view("ex-late", "egress", 6401, 200, EXCHANGE_OK),
    view("ex-edge", "egress", 6402, 200, EXCHANGE_OK),
    view("ex-tail", "egress", 7000, 200, EXCHANGE_OK),
    view("ex-after", "ingress", 7001),
]
TAP_LINE = re.compile(r"(ok|not ok) \d+ - \S+( # .+)?|1\.\.\d+")


def tap(events: list[dict], timeout_ms: int = 5000) -> list[tuple[int, str]]:
    """Run proxy_tap over scripted events; pair every line with how many events were pulled."""
    pulled: list[int] = []

    async def capture():
        for i, event in enumerate(events):
            pulled.append(i)
            yield event

    async def run() -> list[tuple[int, str]]:
        return [(len(pulled), line) async for line in proxy_tap(capture(), timeout_ms=timeout_ms)]

    return asyncio.run(run())


def tap_text(events: list[dict], timeout_ms: int = 5000) -> list[str]:
    return [line for _, line in tap(events, timeout_ms)]


@pytest.mark.skip("Part 4")
def test_proxy_tap() -> None:
    """Every exchange gets one TAP line the moment its evidence is complete or overdue; the plan
    comes last."""
    assert tap_text([]) == ["1..0\n"], "no exchanges: just the plan, ending with a newline"
    assert tap_text(exchange("ex-1", 0, 200, EXCHANGE_OK, 200, EXCHANGE_OK)) == ["ok 1 - ex-1\n", "1..1\n"], (
        "one TAP line per exchange, then the plan; every line ends with a newline"
    )
    for order in itertools.permutations(exchange("ex-1", 0, 200, EXCHANGE_OK, 200, EXCHANGE_OK)):
        assert tap_text(list(order)) == ["ok 1 - ex-1\n", "1..1\n"], (
            f"views arrive in any order: {[event['view'] for event in order]}"
        )
    assert tap_text(exchange("ex-1", 0, 200, ISSUED, 200, ISSUED_REDACTED)) == ["ok 1 - ex-1\n", "1..1\n"], (
        "views are compared in redacted form: a collector that redacts before it ships is not a body change"
    )
    assert tap_text(exchange("ex-1", 0, 404, NOT_FOUND, 500, NOT_FOUND)) == [
        "not ok 1 - ex-1 # proxy collapsed a protocol error into HTTP 500\n",
        "1..1\n",
    ], "an origin 404 JSON-RPC error that reaches the client as 500 was collapsed"
    assert tap_text(exchange("ex-1", 0, 400, "<html>bad request</html>", 500, "<html>bad request</html>")) == [
        "not ok 1 - ex-1 # proxy changed the HTTP status\n",
        "1..1\n",
    ], "only a JSON-RPC error can be collapsed; any other status change is still reported"
    rewritten_copy = [
        view("ex-1", "egress", 0, 200, EXCHANGE_OK),
        view("ex-1", "egress", 1, 200, REWRITTEN),
        view("ex-1", "ingress", 2),
        view("ex-1", "origin", 3, 200, EXCHANGE_OK),
    ]
    assert tap_text(rewritten_copy) == ["ok 1 - ex-1\n", "1..1\n"], (
        "the first copy of a view counts; a later copy is ignored"
    )
    slow = [
        view("ex-slow", "ingress", 0),
        view("ex-slow", "origin", 1, 200, EXCHANGE_OK),
        view("ex-slow", "egress", 6000, 200, EXCHANGE_OK),
    ]
    assert tap_text(slow) == ["ok 1 - ex-slow\n", "1..1\n"], (
        "a view that arrives while its exchange is open counts, however late its capture time"
    )

    received = tap(SCRIPT)
    rows = "".join(line for _, line in received).split("\n")
    assert rows.pop() == "" and all(TAP_LINE.fullmatch(row) for row in rows), (
        f"every line is a TAP result or the plan, and ends with a newline: {rows[:3]}"
    )
    assert rows == [
        "ok 1 - ex-ok",
        "not ok 2 - ex-collapse # proxy collapsed a protocol error into HTTP 500; proxy changed the origin JSON-RPC body",
        "not ok 3 - ex-404 # proxy collapsed a protocol error into HTTP 500",
        "not ok 4 - ex-status # proxy changed the HTTP status",
        "ok 5 - ex-issued",
        "not ok 6 - ex-body # proxy changed the origin JSON-RPC body",
        "not ok 7 - ex-late # incomplete evidence: missing egress",
        "not ok 8 - ex-gap # incomplete evidence: missing ingress, egress",
        "ok 9 - ex-edge",
        "not ok 10 - ex-tail # incomplete evidence: missing ingress, origin",
        "not ok 11 - ex-after # incomplete evidence: missing origin, egress",
        "1..11",
    ], "one line per exchange, numbered as exchanges are reported, then the plan"
    assert [count for count, _ in received] == [4, 6, 11, 14, 18, 24, 26, 26, 28, 30, 30, 30], (
        "each line comes out the moment its exchange completes or falls past its deadline"
    )
    overdue_at_once = [
        view("ex-new", "ingress", 9000),
        view("ex-old", "egress", 1000, 200, EXCHANGE_OK),
        view("ex-new", "origin", 9001, 200, EXCHANGE_OK),
        view("ex-new", "egress", 9002, 200, EXCHANGE_OK),
    ]
    assert tap(overdue_at_once) == [
        (2, "not ok 1 - ex-old # incomplete evidence: missing ingress, origin\n"),
        (4, "ok 2 - ex-new\n"),
        (4, "1..2\n"),
    ], "the clock is the latest capture time seen, so a capture already past its deadline is overdue at once"


def descriptor(name: str, **extra) -> dict:
    return {**tool(name), **extra}


@pytest.mark.skip("Part 5")
def test_sdk_differential() -> None:
    """Every lift, synthesis, drop and change between the wire and the SDK view, with its path."""
    raw = {
        "resultType": "complete",
        "tools": [],
        "futureHint": {"mode": "new"},
        "_meta": {"trace": "trace-42"},
        "ttlMs": 1000,
        "cacheScope": "private",
    }
    assert sdk_differential(raw, {"tools": [], "futureHint": {"mode": "new"}}) == [], (
        "the SDK may drop bookkeeping from the result root"
    )
    assert sdk_differential(raw, {"tools": []}) == [Difference("dropped", "/futureHint")], (
        "a dropped unknown field is reported"
    )
    assert sdk_differential({"tools": []}, {"resultType": "complete", "tools": []}) == [
        Difference("synthesized", "/resultType")
    ], "a resultType the wire never had is synthesized, not bookkeeping"
    assert sdk_differential(
        {"resultType": "input_required", "inputRequests": {}}, {"resultType": "complete", "inputRequests": {}}
    ) == [Difference("changed", "/resultType")], "only dropping bookkeeping is allowed; changing it is reported"

    three = {"tools": [tool("a", "First."), tool("b", "Second."), tool("c", "Third.")]}
    assert sdk_differential(three, {"tools": [tool("a", "First."), tool("c", "Third.")]}) == [
        Difference("changed", "/tools/1/description"),
        Difference("changed", "/tools/1/name"),
        Difference("dropped", "/tools/2"),
    ], "lists are compared by position"
    assert sdk_differential({"tools": [tool("a")]}, {"tools": [tool("a"), tool("b")]}) == [
        Difference("synthesized", "/tools/1")
    ], "an item only the SDK has is synthesized"

    nested = {"resultType": "complete", "tools": [descriptor("inventory_get", _meta={"com.example/region": "eu"})]}
    assert sdk_differential(nested, {"tools": [tool("inventory_get")]}) == [
        Difference("dropped", "/tools/0/_meta")
    ], "_meta below the result root is not bookkeeping"
    allowed = {**BOOKKEEPING, "/tools/0": frozenset({"_meta"})}
    assert sdk_differential(nested, {"tools": [tool("inventory_get")]}, allowed) == [], (
        "allowed names the objects it covers by pointer"
    )
    assert sdk_differential(nested, {"tools": [descriptor("inventory_get", _meta={"com.example/region": "EU"})]}) == [
        Difference("changed", "/tools/0/_meta/com.example~1region")
    ], "paths are JSON Pointers: a '/' in a name is written '~1'"

    assert sdk_differential(
        {"structuredContent": {"sku": "A-0007", "stock": 12}},
        {"structuredContent": {"sku": "A-0007", "stock": "12"}},
    ) == [Difference("changed", "/structuredContent/stock")], "12 and '12' are different values"
    assert sdk_differential({"completion": {"hasMore": True}}, {"completion": {"hasMore": 1}}) == [
        Difference("changed", "/completion/hasMore")
    ], "true and 1 are different JSON values"
    assert sdk_differential(
        {"content": [{"type": "text", "text": "hi"}]}, {"content": {"type": "text", "text": "hi"}}
    ) == [Difference("changed", "/content")], "a list that became an object changed, as a whole"
    assert sdk_differential({"tools": [], "nextCursor": None}, {"tools": []}) == [
        Difference("dropped", "/nextCursor")
    ], "a member set to null is not a missing member"
    assert sdk_differential({"b": 1, "d": 1}, {"a": 0, "b": 2, "c": 0}) == [
        Difference("synthesized", "/a"),
        Difference("changed", "/b"),
        Difference("synthesized", "/c"),
        Difference("dropped", "/d"),
    ], "members are reported in sorted name order, whichever side has them"
    values = [f"env-{i:02d}" for i in range(12)]
    edited = list(values)
    edited[2], edited[10] = "ENV-02", "ENV-10"
    assert sdk_differential(completion(values), {"completion": {"values": edited}}) == [
        Difference("changed", "/completion/values/2"),
        Difference("changed", "/completion/values/10"),
    ], "list items are reported in index order"

    flattened = {
        "resultType": "complete",
        "completion": {"values": ["development", "staging"], "total": 3, "hasMore": True},
    }
    assert sdk_differential(
        flattened, {"completion": {"values": ["development", "staging"]}, "total": 3, "hasMore": True}
    ) == [
        Difference("lifted", "/completion/hasMore", "/hasMore"),
        Difference("lifted", "/completion/total", "/total"),
    ], "members the SDK moved up are lifted"
    assert sdk_differential(
        {"structuredContent": {"city": "Oslo", "tempC": 4}}, {"structuredContent": {"tempC": 4}, "city": "Oslo"}
    ) == [Difference("lifted", "/structuredContent/city", "/city")], (
        "a lift is one difference, even when its new place is reported first"
    )
    assert sdk_differential(
        flattened, {"completion": {"values": ["development", "staging"]}, "total": 4, "hasMore": True}
    ) == [
        Difference("lifted", "/completion/hasMore", "/hasMore"),
        Difference("dropped", "/completion/total"),
        Difference("synthesized", "/total"),
    ], "a lift keeps its value; a different value is a drop and a synthesis"
    assert sdk_differential(
        {"content": [{"type": "text", "text": "hi"}]}, {"content": [{"type": "text"}], "text": "hi"}
    ) == [Difference("lifted", "/content/0/text", "/text")], "a member can be lifted out of a list item"
    assert sdk_differential({"a": {"x": 1}, "b": {}}, {"a": {}, "b": {"x": 1}}) == [
        Difference("dropped", "/a/x"),
        Difference("synthesized", "/b/x"),
    ], "a move sideways is not a lift"
    assert sdk_differential({"stats": {"page": {"total": 3}}, "s": {}}, {"stats": {"page": {}}, "s": {"total": 3}}) == [
        Difference("synthesized", "/s/total"),
        Difference("dropped", "/stats/page/total"),
    ], "a lift goes to an ancestor object, not to any shallower one"
    assert sdk_differential({"a": {"x": 1}, "b": {"x": 1}}, {"a": {}, "b": {}, "x": 1}) == [
        Difference("lifted", "/a/x", "/x"),
        Difference("dropped", "/b/x"),
    ], "each member takes part in at most one lift"

    wire = {
        "resultType": "complete",
        "tools": [tool("inventory_get")],
        "futureHint": {"preserve": True},
        "_meta": {"trace": "trace-42"},
    }
    lossy = differential_report(wire, {"tools": [tool("inventory_get")]})
    faithful = differential_report(wire, {"tools": [tool("inventory_get")], "futureHint": {"preserve": True}})
    assert lossy["differences"] == [{"kind": "dropped", "path": "/futureHint", "to": None}], (
        "the report lists each difference"
    )
    gate = ReleaseGate(POLICY, TRUSTED)
    assert evaluate(gate, [canary_case(0)], sdk=[lossy])["action"] == "rollback", (
        "an SDK that loses a wire field blocks promotion"
    )
    assert evaluate(gate, [canary_case(0)], sdk=[faithful])["action"] == "promote", (
        "the same SDK view with the field kept promotes"
    )
