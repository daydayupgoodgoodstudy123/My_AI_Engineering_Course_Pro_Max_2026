"""A per-step safety service for a session that moves across pages."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from .desktop import FakeDesktop
from .safety import Action, has_injection
from .screen import Screen

KINDS = ("click", "type", "navigate")


@dataclass(frozen=True)
class Decision:
    outcome: str  # "allow", "blocked" or "denied"
    rule: str | None = None  # the check that stopped the action; None when allowed
    element: str | None = None  # eid the action lands on, if any


class SafetyService:
    """Decides every action of a session before it runs.

    allowed_hosts entries are either an exact host ("docs.example.org") or "*." plus a
    domain ("*.example.com"), which allows every subdomain of that domain but not the
    domain itself. Hosts compare case-insensitively; only http and https URLs can be allowed.

    human_confirm(prompt) is the human in the loop. Every refusal is appended to denials as
    (url of the screen, eid).
    """

    def __init__(self, allowed_hosts: tuple[str, ...], human_confirm: Callable[[str], bool]) -> None:
        self.allowed_hosts = tuple(h.lower() for h in allowed_hosts)
        self.human_confirm = human_confirm
        self.denials: list[tuple[str, str]] = []

    def host_allowed(self, url: str) -> bool:
        """Whether url points at an allowed host."""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme.lower() not in ("http", "https") or not host:
            return False
        for entry in self.allowed_hosts:
            if entry.startswith("*."):
                if host.endswith(entry[1:]):
                    return True
            elif host == entry:
                return True
        return False

    def decide(self, action: Action, screen: Screen) -> Decision:
        """Decide one action against the screen it is about to run on.

        Checks run in this order and the first one that fails is the only rule reported:
          "injection"    the screen's DOM text carries an injection marker: every action
                         on that screen is blocked
          "kind"         only click, type and navigate exist
          "target"       a click needs an element at the point; typing needs a focused element
          "destination"  navigate(url), and a click on a link (its href), must go to an
                         allowed host
          "text"         typed text carrying an injection marker
          "denied"       the human already refused this element on this page (same url and
                         eid) in this session: blocked without asking again
        Then a sensitive element (button, link or field) needs human_confirm; a yes allows
        this one action only, a no returns outcome "denied" with rule "confirm".
        """
        if has_injection(screen.dom_text):
            return Decision("blocked", "injection")
        if action.kind not in KINDS:
            return Decision("blocked", "kind")
        el = None
        if action.kind == "click":
            el = screen.element_at(action.args["x"], action.args["y"])
            if el is None:
                return Decision("blocked", "target")
        elif action.kind == "type":
            el = screen.focused()
            if el is None:
                return Decision("blocked", "target")
        eid = el.eid if el is not None else None
        if action.kind == "navigate" and not self.host_allowed(action.args["url"]):
            return Decision("blocked", "destination")
        if el is not None and el.role == "link" and el.href and not self.host_allowed(el.href):
            return Decision("blocked", "destination", eid)
        if action.kind == "type" and has_injection(action.args["text"]):
            return Decision("blocked", "text", eid)
        if el is not None and el.sensitive:
            if (screen.url, el.eid) in self.denials:
                return Decision("blocked", "denied", eid)
            if not self.human_confirm(f"{action.kind} {el.label!r} on {screen.url}"):
                self.denials.append((screen.url, el.eid))
                return Decision("denied", "confirm", eid)
        return Decision("allow", None, eid)


def run_session(
    model: Callable[[Screen], Action | None],
    desktop: FakeDesktop,
    service: SafetyService,
    max_steps: int = 50,
) -> list[tuple[Action, Decision]]:
    """Drive the desktop until model returns None or max_steps actions have been decided.

    Each step shows the model the current screen, decides its action against that same
    screen, and sends the action to the desktop only when it is allowed.
    """
    log: list[tuple[Action, Decision]] = []
    for _ in range(max_steps):
        screen = desktop.screen()
        action = model(screen)
        if action is None:
            break
        decision = service.decide(action, screen)
        log.append((action, decision))
        if decision.outcome != "allow":
            continue
        if action.kind == "click":
            desktop.click(action.args["x"], action.args["y"])
        elif action.kind == "type":
            desktop.type(action.args["text"])
        else:
            desktop.navigate(action.args["url"])
    return log
