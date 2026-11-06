"""The agent loop: screenshot, classify, confirm when needed, execute."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .desktop import FakeDesktop
from .safety import Action, SafetyClassifier


@dataclass(frozen=True)
class Step:
    action: Action
    outcome: str  # "done", "blocked", "denied" or "aborted"
    detail: str  # the label acted on when done, otherwise the reason


def run_agent(
    actions: list[Action],
    desktop: FakeDesktop,
    classifier: SafetyClassifier,
    human_confirm: Callable[[str], bool],
) -> list[Step]:
    """Run actions one at a time on the desktop, with a safety check before each.

    Every action is assessed against the screen as it is when that action runs. A blocked
    action is skipped. When the verdict needs confirmation, human_confirm(reason) decides,
    and a denied action is skipped.

    A confirmation covers the element the human was asked about. After a yes, a click runs
    only if that element is still the topmost one at the point on the current screen, and
    typing only if that element still has the focus; otherwise the step is aborted and
    nothing is sent to the desktop.
    """
    trace: list[Step] = []
    for action in actions:
        screen = desktop.screen()
        verdict = classifier.assess(action, screen)
        if not verdict.allow:
            trace.append(Step(action, "blocked", verdict.reason))
            continue
        if verdict.needs_confirmation:
            if not human_confirm(verdict.reason):
                trace.append(Step(action, "denied", verdict.reason))
                continue
            now = desktop.screen()
            if action.kind == "click":
                still = now.element_at(action.args["x"], action.args["y"])
                same = still is not None and still.eid == verdict.element
            else:
                same = now.focus == verdict.element
            if not same:
                trace.append(Step(action, "aborted", "screen changed during confirmation"))
                continue
        if action.kind == "click":
            el = desktop.click(action.args["x"], action.args["y"])
            trace.append(Step(action, "done", el.label))
        elif action.kind == "type":
            label = desktop.screen().focused().label
            desktop.type(action.args["text"])
            trace.append(Step(action, "done", label))
    return trace
