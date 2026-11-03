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
    raise NotImplementedError


def check_case(transcript: Transcript) -> CaseResult:
    """Run one fixture and say whether it reached its expected outcome.

    expect None: the response validates as a result or an accepted notification.
    expect an int: the response validates as a JSON-RPC error with exactly that code.
    expect a rule name: the response breaks exactly that rule; another rule, or none, fails.
    The result carries the raw evidence {"headers", "request", "responseStatus", "responseBody"}.
    """
    raise NotImplementedError


def run_corpus(corpus: TranscriptCorpus) -> list[CaseResult]:
    """Check every stored fixture, in name order."""
    return [check_case(corpus.load(name)) for name in corpus.names()]
