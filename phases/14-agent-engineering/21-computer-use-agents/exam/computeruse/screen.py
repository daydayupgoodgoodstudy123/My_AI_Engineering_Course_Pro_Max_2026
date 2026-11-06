"""What the agent sees: a screen of labeled elements at pixel coordinates."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Element:
    eid: str
    label: str
    x: int
    y: int
    w: int
    h: int
    role: str = "button"  # "button", "textbox" or "link"
    sensitive: bool = False  # login, purchase, CAPTCHA, delete, card or password fields
    href: str | None = None  # where a link goes


@dataclass
class Screen:
    """One screenshot's worth of UI.

    elements are in paint order: a later element is drawn on top of an earlier one.
    focus is the eid of the focused textbox, if any. A Screen is a snapshot and is never
    changed after it is created; the desktop shows a new Screen when the UI changes.
    """

    elements: list[Element]
    dom_text: str = ""
    focus: str | None = None
    url: str = ""

    def element_at(self, x: int, y: int) -> Element | None:
        """The topmost element covering pixel (x, y), or None.

        An element covers the pixels with x <= px < x + w and y <= py < y + h, so two
        elements that share an edge never both cover a pixel on it.
        """
        for el in reversed(self.elements):
            if el.x <= x <= el.x + el.w and el.y <= y <= el.y + el.h:
                return el
        return None

    def get(self, eid: str) -> Element:
        """The element with this eid. Unknown ids raise KeyError."""
        for el in self.elements:
            if el.eid == eid:
                return el
        raise KeyError(eid)

    def focused(self) -> Element | None:
        return self.get(self.focus) if self.focus is not None else None
