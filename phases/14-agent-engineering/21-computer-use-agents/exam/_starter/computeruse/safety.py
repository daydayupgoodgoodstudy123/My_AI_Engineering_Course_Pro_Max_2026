"""The per-step safety classifier: every action is judged before it runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .screen import Screen

INJECTION_MARKERS = (
    "ignore all instructions",
    "ignore previous instructions",
    "system:",
    "override:",
    "act as",
)


@dataclass(frozen=True)
class Action:
    kind: str  # "click" {"x", "y"}, "type" {"text"}, "navigate" {"url"}
    args: dict[str, Any]


@dataclass(frozen=True)
class SafetyVerdict:
    allow: bool
    reason: str
    needs_confirmation: bool = False
    element: str | None = None  # eid of the element the action lands on


def has_injection(text: str) -> str | None:
    """The first injection marker found in text (case-insensitive), or None."""
    lowered = text.lower()
    for marker in INJECTION_MARKERS:
        if marker in lowered:
            return marker
    return None


class SafetyClassifier:
    def __init__(self, allowed_labels: tuple[str, ...]) -> None:
        self.allowed_labels = set(allowed_labels)

    def assess(self, action: Action, screen: Screen) -> SafetyVerdict:
        """Judge one action against the screen it is about to run on.

        Screenshots and DOM text are untrusted input, never permission. Rules, first match wins:
        - DOM text carrying an injection marker blocks every action on that screen.
        - click: blocked when no element is at the point or its label is not allowlisted.
          A sensitive button or link needs confirmation; focusing a textbox does not.
        - type: the text goes to the focused element. Blocked when nothing is focused, when
          its label is not allowlisted, or when the text carries an injection marker.
          Typing into a sensitive field (a password, a card number) needs confirmation.
        - any other kind is blocked.
        verdict.element is the eid of the element the action lands on.
        """
        if has_injection(screen.dom_text):
            return SafetyVerdict(False, "DOM contains injection markers")
        if action.kind == "click":
            x, y = action.args["x"], action.args["y"]
            el = screen.element_at(x, y)
            if el is None:
                return SafetyVerdict(False, f"no element at ({x}, {y})")
            if el.label not in self.allowed_labels:
                return SafetyVerdict(False, f"label {el.label!r} not in allowlist", element=el.eid)
            if el.sensitive and el.role != "textbox":
                return SafetyVerdict(
                    True,
                    f"label {el.label!r} is sensitive; confirm required",
                    needs_confirmation=True,
                    element=el.eid,
                )
            return SafetyVerdict(True, "ok", element=el.eid)
        if action.kind == "type":
            el = screen.focused()
            if el is None:
                return SafetyVerdict(False, "nothing is focused")
            if el.label not in self.allowed_labels:
                return SafetyVerdict(False, f"label {el.label!r} not in allowlist", element=el.eid)
            marker = has_injection(action.args["text"])
            if marker:
                return SafetyVerdict(
                    False, f"typed text contains injection marker: {marker!r}", element=el.eid
                )
            return SafetyVerdict(True, "ok", element=el.eid)
        return SafetyVerdict(False, f"unknown action kind: {action.kind}")
