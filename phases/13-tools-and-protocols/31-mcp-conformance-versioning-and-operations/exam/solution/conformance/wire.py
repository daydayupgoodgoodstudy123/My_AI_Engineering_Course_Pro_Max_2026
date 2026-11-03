"""Wire facts the harness checks against: MCP 2026-07-28 and the earlier initialization era."""
from __future__ import annotations

MODERN = "modern"
LEGACY = "legacy"
ERAS = (MODERN, LEGACY)
MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"

CORE_RESULT_TYPES = frozenset({"complete", "input_required"})
TASKS_CAPABILITY = "io.modelcontextprotocol/tasks"
EXTENSION_RESULT_TYPES = {TASKS_CAPABILITY: frozenset({"task"})}
COMPLETE_ONLY_METHODS = frozenset({"tools/list", "completion/complete"})
TASK_METHOD = "tools/call"
TASK_STATUSES = frozenset({"working", "input_required", "completed", "cancelled", "failed"})
MAX_COMPLETION_VALUES = 100

# The HTTP status each known protocol error travels with.
PROTOCOL_ERROR_STATUS = {-32020: 400, -32021: 400, -32022: 400, -32601: 404}

RULES = (
    "notification",
    "missing-body",
    "envelope",
    "exclusive",
    "error-shape",
    "error-status",
    "result-status",
    "result-shape",
    "missing-result-type",
    "unknown-result-type",
    "method-result-type",
    "tools-payload",
    "completion-payload",
    "task-payload",
)


class Violation(Exception):
    """A response broke one conformance rule. rule is one of RULES."""

    def __init__(self, rule: str, detail: str) -> None:
        if rule not in RULES:
            raise ValueError(f"unknown rule {rule!r}")
        super().__init__(f"{rule}: {detail}")
        self.rule = rule
        self.detail = detail
