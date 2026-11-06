"""A scripted stand-in for the virtual display (Xvfb) and its mouse and keyboard."""
from __future__ import annotations

import json
from dataclasses import asdict, replace

from .screen import Element, Screen

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeDesktop:
    """Shows one Screen at a time and executes clicks, typing and navigation on it.

    pages maps a URL to the Screen shown there. events records every input that
    reached the desktop, in order.
    """

    def __init__(self, screen: Screen, pages: dict[str, Screen] | None = None) -> None:
        self._screen = screen
        self.pages = dict(pages or {})
        self.events: list[tuple] = []

    def screen(self) -> Screen:
        """What a screenshot taken now would show."""
        return self._screen

    def screenshot(self) -> bytes:
        """The current screen as image bytes (a PNG signature, then the layout)."""
        layout = {
            "url": self._screen.url,
            "focus": self._screen.focus,
            "dom": self._screen.dom_text,
            "elements": [asdict(el) for el in self._screen.elements],
        }
        return PNG_SIGNATURE + json.dumps(layout, sort_keys=True).encode("utf-8")

    def show(self, screen: Screen) -> None:
        """The application redraws the display."""
        self._screen = screen

    def click(self, x: int, y: int) -> Element | None:
        """Press the mouse at (x, y). The topmost element there receives the click.

        A link navigates to its href; a textbox takes the focus.
        """
        el = self._screen.element_at(x, y)
        self.events.append(("click", x, y, el.eid if el else None))
        if el is not None:
            if el.role == "link" and el.href:
                self.navigate(el.href)
            elif el.role == "textbox":
                self._screen = replace(self._screen, focus=el.eid)
        return el

    def type(self, text: str) -> None:
        el = self._screen.focused()
        if el is None:
            raise RuntimeError("typing with nothing focused")
        self.events.append(("type", el.eid, text))

    def navigate(self, url: str) -> None:
        if url not in self.pages:
            raise LookupError(f"no page at {url}")
        self.events.append(("navigate", url))
        self._screen = self.pages[url]
