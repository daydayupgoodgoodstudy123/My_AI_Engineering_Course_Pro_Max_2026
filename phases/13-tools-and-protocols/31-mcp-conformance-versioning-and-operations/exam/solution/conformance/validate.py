"""Judge recorded responses against the conformance rules, and run fixtures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .corpus import Transcript, TranscriptCorpus
from .release import CaseResult
from .wire import (
    COMPLETE_ONLY_METHODS,
    CORE_RESULT_TYPES,
    ERAS,
    EXTENSION_RESULT_TYPES,
    LEGACY,
    MAX_COMPLETION_VALUES,
    PROTOCOL_ERROR_STATUS,
    TASK_METHOD,
    TASK_STATUSES,
    Violation,
)


@dataclass(frozen=True)
class Outcome:
    """What a valid response means."""

    kind: str  # "result", "error" or "notification"
    result_type: str | None = None  # the semantic resultType of a result
    inferred: bool = False  # True when a legacy result left resultType out
    error_code: int | None = None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_response(
    request: dict[str, Any],
    status: int,
    body: Any,
    era: str,
    capabilities: frozenset[str] = frozenset(),
) -> Outcome:
    """Judge one HTTP response to a JSON-RPC request or notification, as it crossed the wire.

    body is the parsed JSON body, or None when the response had no body. The first broken rule
    raises Violation(rule, detail); rules are checked in this order:

      notification         a notification (a request with no "id") gets HTTP 202 and no body
      missing-body         a request gets a body
      envelope             the body is an object whose "jsonrpc" is "2.0"
      exclusive            it holds exactly one of "result" and "error"
      error-shape          an error is an object with an integer code and a string message
      error-status         a code in PROTOCOL_ERROR_STATUS travels with that HTTP status
      result-status        a result travels with HTTP 200
      result-shape         a result is an object
      missing-result-type  a modern result names its resultType; a legacy result may leave it
                           out, and is then complete
      unknown-result-type  resultType is a core result type, or a type an extension in
                           capabilities adds
      method-result-type   tools/list and completion/complete answer complete, and only
                           tools/call answers task
      tools-payload        tools/list: a tools array; every tool an object with a non-empty
                           name no other tool has, a non-empty description, and an inputSchema
                           object whose type is "object"
      completion-payload   completion/complete: a completion object; values a list of at most
                           MAX_COMPLETION_VALUES strings; total, if present, an integer no
                           smaller than the number of values; hasMore, if present, a boolean
      task-payload         a task: non-empty string taskId, status, createdAt and lastUpdatedAt;
                           status in TASK_STATUSES; ttlMs present, null or a non-negative
                           integer; pollIntervalMs, if present, a non-negative integer

    Members the rules do not mention are additive and accepted, whatever their names.
    Returns Outcome("notification"), Outcome("error", error_code=...) or
    Outcome("result", result_type=..., inferred=...).
    """
    if era not in ERAS:
        raise ValueError(f"unknown era {era!r}")
    if "id" not in request:
        if status != 202 or body is not None:
            raise Violation("notification", f"a notification got HTTP {status} and body {body!r}")
        return Outcome("notification")
    if body is None:
        raise Violation("missing-body", f"HTTP {status} carried no JSON-RPC response")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        raise Violation("envelope", "the body is not a JSON-RPC 2.0 response object")
    if ("result" in body) == ("error" in body):
        raise Violation("exclusive", "a response holds exactly one of result and error")

    if "error" in body:
        error = body["error"]
        if (
            not isinstance(error, dict)
            or not _is_int(error.get("code"))
            or not isinstance(error.get("message"), str)
        ):
            raise Violation("error-shape", "an error needs an integer code and a string message")
        code = error["code"]
        expected = PROTOCOL_ERROR_STATUS.get(code)
        if expected is not None and status != expected:
            raise Violation("error-status", f"error {code} travels with HTTP {expected}, not {status}")
        return Outcome("error", error_code=code)

    if status != 200:
        raise Violation("result-status", f"a result travels with HTTP 200, not {status}")
    result = body["result"]
    if not isinstance(result, dict):
        raise Violation("result-shape", f"a result is an object, not {result!r}")
    method = request.get("method")
    result_type = result.get("resultType")
    inferred = False
    if result_type is None:
        if era != LEGACY:
            raise Violation("missing-result-type", "a modern result names its resultType")
        result_type, inferred = "complete", True
    else:
        allowed = set(CORE_RESULT_TYPES)
        for capability in capabilities:
            allowed |= EXTENSION_RESULT_TYPES.get(capability, frozenset())
        if not isinstance(result_type, str) or result_type not in allowed:
            raise Violation(
                "unknown-result-type", f"resultType {result_type!r} is unknown or not negotiated"
            )
    if (method in COMPLETE_ONLY_METHODS and result_type != "complete") or (
        result_type == "task" and method != TASK_METHOD
    ):
        raise Violation("method-result-type", f"{method} cannot answer {result_type}")
    _check_payload(method, result_type, result)
    return Outcome("result", result_type=result_type, inferred=inferred)


def _check_payload(method: Any, result_type: str, result: dict[str, Any]) -> None:
    if method == "tools/list":
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise Violation("tools-payload", "tools/list needs a tools array")
        names: set[str] = set()
        for tool in tools:
            if not isinstance(tool, dict):
                raise Violation("tools-payload", "every tool is an object")
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                raise Violation("tools-payload", "every tool needs a non-empty name")
            if name in names:
                raise Violation("tools-payload", f"two tools are named {name!r}")
            names.add(name)
            description = tool.get("description")
            if not isinstance(description, str) or not description:
                raise Violation("tools-payload", f"tool {name!r} needs a description")
            schema = tool.get("inputSchema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                raise Violation("tools-payload", f"tool {name!r} needs an object-root inputSchema")
    elif method == "completion/complete":
        completion = result.get("completion")
        if not isinstance(completion, dict):
            raise Violation("completion-payload", "completion/complete needs a completion object")
        values = completion.get("values")
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise Violation("completion-payload", "completion.values is a list of strings")
        if len(values) > MAX_COMPLETION_VALUES:
            raise Violation("completion-payload", f"at most {MAX_COMPLETION_VALUES} values")
        total = completion.get("total")
        if total is not None and (not _is_int(total) or total < len(values)):
            raise Violation("completion-payload", "completion.total is an integer >= len(values)")
        has_more = completion.get("hasMore")
        if has_more is not None and not isinstance(has_more, bool):
            raise Violation("completion-payload", "completion.hasMore is a boolean")
    if result_type == "task":
        for field in ("taskId", "status", "createdAt", "lastUpdatedAt"):
            value = result.get(field)
            if not isinstance(value, str) or not value:
                raise Violation("task-payload", f"a task needs a non-empty {field}")
        if result["status"] not in TASK_STATUSES:
            raise Violation("task-payload", f"unknown task status {result['status']!r}")
        if "ttlMs" not in result:
            raise Violation("task-payload", "a task needs ttlMs")
        ttl = result["ttlMs"]
        if ttl is not None and (not _is_int(ttl) or ttl < 0):
            raise Violation("task-payload", "ttlMs is null or a non-negative integer")
        poll = result.get("pollIntervalMs")
        if poll is not None and (not _is_int(poll) or poll < 0):
            raise Violation("task-payload", "pollIntervalMs is a non-negative integer")


def check_case(transcript: Transcript) -> CaseResult:
    """Run one fixture and say whether it reached its expected outcome.

    expect None: the response validates as a result or an accepted notification.
    expect an int: the response validates as a JSON-RPC error with exactly that code.
    expect a rule name: the response breaks exactly that rule; another rule, or none, fails.
    The result carries the raw evidence {"headers", "request", "responseStatus", "responseBody"}.
    """
    evidence = {
        "headers": transcript.headers,
        "request": transcript.request,
        "responseStatus": transcript.response_status,
        "responseBody": transcript.response_body,
    }
    expect = transcript.expect
    try:
        outcome = validate_response(
            transcript.request,
            transcript.response_status,
            transcript.response_body,
            transcript.era,
            transcript.capabilities,
        )
    except Violation as violation:
        passed = isinstance(expect, str) and violation.rule == expect
        return CaseResult(transcript.name, passed, f"broke {violation.rule}: {violation.detail}", evidence)
    if expect is None:
        passed = outcome.kind in ("result", "notification")
    elif isinstance(expect, str):
        passed = False
    else:
        passed = outcome.kind == "error" and outcome.error_code == expect
    return CaseResult(transcript.name, passed, f"validated as {outcome.kind}", evidence)


def run_corpus(corpus: TranscriptCorpus) -> list[CaseResult]:
    """Check every stored fixture, in name order."""
    return [check_case(corpus.load(name)) for name in corpus.names()]
