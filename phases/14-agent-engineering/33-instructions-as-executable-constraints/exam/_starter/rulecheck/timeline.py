"""Judge a turn from its ordered event log, the way each category reads it.

TurnTrace keeps the lesson's summary fields, and a summary has no order: read_state_file
cannot say whether the read came before the first tool call. judge() reads the events.
"""
from __future__ import annotations

from dataclasses import dataclass

from .checker import THRESHOLD
from .rules import Rule
from .turn import ACCEPTANCE, RELEASE_SCRIPT, STATE_FILE, Event


@dataclass(frozen=True)
class Verdict:
    slug: str
    passed: bool
    at: int | None = None


class Watch:
    """Which events each check is about, one method per check name.

    A method takes one event and says whether the rule watches it; the rule's category decides
    what the watched events must satisfy.
    """

    def state_file_fresh(self, event: Event) -> bool:
        return event.kind == "read" and event.subject == STATE_FILE

    def no_release_script_edits(self, event: Event) -> bool:
        return event.kind == "write" and event.subject == RELEASE_SCRIPT

    def tests_pass(self, event: Event) -> bool:
        return event.kind == "run" and event.subject == ACCEPTANCE

    def opened_question_when_unsure(self, event: Event) -> bool:
        return event.kind == "decide"

    def new_dependency_approved(self, event: Event) -> bool:
        return event.kind == "install"


def judge(
    rules: list[Rule],
    events: list[Event],
    watch: Watch | None = None,
    threshold: float = THRESHOLD,
) -> list[Verdict]:
    """One verdict per rule, in rule order. A rule watches the events its check method on
    watch accepts; at is the index of the event that broke the rule.

    startup: work starts at the first tool call that no startup rule watches. Every startup
        rule needs one of its watched events before that point, or it fails there. A turn
        that makes no such tool call never starts work, and its startup rules pass.
    forbidden: fails at the first event it watches.
    definition_of_done: the last event it watches is the proof. The rule fails at the proof
        when its exit code is not 0, at the first write or install after a passing proof
        (the proof is stale), and with at=None when there is no proof at all.
    uncertainty: a watched event whose confidence is below threshold needs an ask event
        after the previous watched event and before itself; the rule fails at the first
        one without.
    approval: a watched event needs an earlier approve event whose subject normalizes to the
        same name; the rule fails at the first one without.

    BrokenRule, before anything is judged, for a rule whose check is not a public method of
    watch or whose category is not one of the five.
    """
    raise NotImplementedError
