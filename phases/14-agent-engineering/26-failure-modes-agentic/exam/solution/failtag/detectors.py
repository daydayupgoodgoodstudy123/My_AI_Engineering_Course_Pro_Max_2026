"""Failure-mode detectors for agent traces.

The five industry-recurring modes (hallucinated actions, scope creep, cascading errors,
context loss, tool misuse) plus success hallucination. Each detector returns its label
when the trace matches and None otherwise; tag() runs them all in DETECTORS order.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .trace import Trace, TraceStep, references

TOOL_ARGS = {
    "search": {"query"},
    "read_file": {"path"},
    "write_file": {"path", "content"},
    "list_dir": {"path"},
}
KNOWN_TOOLS = set(TOOL_ARGS)

WRITE_VERBS = ("write", "create", "save", "update", "edit")
SUCCESS_VERBS = WRITE_VERBS + ("make",)

# "do not <verb> ..." -> the tools that verb forbids
VERB_TOOLS = {
    "modify": frozenset({"write_file"}),
    "write": frozenset({"write_file"}),
    "edit": frozenset({"write_file"}),
    "read": frozenset({"read_file"}),
    "list": frozenset({"list_dir"}),
    "search": frozenset({"search"}),
}


@dataclass(frozen=True)
class Rule:
    tools: frozenset[str]
    prefix: str | None = None


def mentions(request: str, verbs: tuple[str, ...]) -> bool:
    """True when the request uses one of the verbs as a whole word, ignoring case and punctuation."""
    words = set(re.findall(r"[a-z]+", request.lower()))
    return any(verb in words for verb in verbs)


def parse_constraint(text: str) -> Rule | None:
    """Read a "do not <verb> [<target>]" constraint as a rule on tool calls.

    The verb picks the forbidden tools from VERB_TOOLS. A target ending in "/" limits the
    rule to calls whose path argument starts with it; any other target forbids every call
    to those tools. Anything else (no "do not", or a verb missing from VERB_TOOLS) is not
    a tool rule and gives None.
    """
    words = text.lower().split()
    if words[:2] != ["do", "not"] or len(words) < 3:
        return None
    tools = VERB_TOOLS.get(words[2])
    if tools is None:
        return None
    target = words[3] if len(words) > 3 else ""
    return Rule(tools, target if target.endswith("/") else None)


def violates(rule: Rule, step: TraceStep) -> bool:
    if step.kind != "tool_call" or step.name not in rule.tools:
        return False
    return rule.prefix is None or str(step.args.get("path", "")).startswith(rule.prefix)


def is_hallucinated(step: TraceStep) -> bool:
    return step.kind == "tool_call" and step.name not in KNOWN_TOOLS


def is_misused(step: TraceStep) -> bool:
    """A known tool called without one of its required arguments."""
    expected = TOOL_ARGS.get(step.name)
    return step.kind == "tool_call" and expected is not None and not expected <= set(step.args)


def is_write(step: TraceStep) -> bool:
    return step.kind == "tool_call" and step.name == "write_file"


def detect_hallucinated_action(trace: Trace) -> str | None:
    """The agent called a tool that does not exist."""
    if any(is_hallucinated(step) for step in trace.steps):
        return "hallucinated_action"
    return None


def detect_scope_creep(trace: Trace) -> str | None:
    """The agent wrote a file although the request never asked for a write."""
    if not mentions(trace.user_request, WRITE_VERBS) and any(is_write(s) for s in trace.steps):
        return "scope_creep"
    return None


def detect_cascading_errors(trace: Trace) -> str | None:
    """A failed tool call whose result at least two later tool calls go on to use.

    A later call uses the failed result when references() names the failed step. Calls that
    do not use it are independent work and do not count; a call counts once however many
    times it uses the result.
    """
    consumers: Counter[int] = Counter()
    for step in trace.steps:
        if step.kind == "tool_call":
            consumers.update(references(step))
    for i, step in enumerate(trace.steps):
        if step.kind == "tool_call" and step.status == "error" and consumers[i] >= 2:
            return "cascading_errors"
    return None


def detect_context_loss(trace: Trace) -> str | None:
    """A tool call breaks one of the trace's "do not ..." constraints."""
    rules = [rule for rule in map(parse_constraint, trace.constraints) if rule]
    for step in trace.steps:
        if any(violates(rule, step) for rule in rules):
            return "context_loss"
    return None


def detect_tool_misuse(trace: Trace) -> str | None:
    """A known tool called with the wrong arguments."""
    if any(is_misused(step) for step in trace.steps):
        return "tool_misuse"
    return None


def detect_success_hallucination(trace: Trace) -> str | None:
    """The agent claimed success on a write task, but the target state did not change."""
    if (
        mentions(trace.user_request, SUCCESS_VERBS)
        and trace.final_success_claim
        and not trace.target_state_changed
    ):
        return "success_hallucination"
    return None


DETECTORS = (
    detect_hallucinated_action,
    detect_scope_creep,
    detect_cascading_errors,
    detect_context_loss,
    detect_tool_misuse,
    detect_success_hallucination,
)


def tag(trace: Trace) -> list[str]:
    """Every mode the trace shows, in DETECTORS order."""
    return [label for label in (detect(trace) for detect in DETECTORS) if label]
