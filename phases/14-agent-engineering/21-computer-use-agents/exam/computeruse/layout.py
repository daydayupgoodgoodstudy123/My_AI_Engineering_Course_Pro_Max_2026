"""Hit testing in a nested UI tree, from coordinates in a scaled-down screenshot."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """A box in the UI tree.

    x and y are relative to the parent's content origin, which is the parent's own corner
    moved left by scroll_x and up by scroll_y. Children are painted after their parent and
    in list order, so a later sibling is drawn on top of an earlier one and of everything
    inside it.
    """

    name: str
    x: int
    y: int
    w: int
    h: int
    children: list["Node"] = field(default_factory=list)
    clip: bool = False  # descendants are visible only inside this node's box
    scroll_x: int = 0
    scroll_y: int = 0
    visible: bool = True


def to_screen(x: int, y: int, shot: tuple[int, int], screen: tuple[int, int]) -> tuple[int, int]:
    """Map pixel (x, y) of a screenshot of size shot = (w, h) onto a screen of size screen.

    Screenshot pixel x covers the screen span from x * W / w up to (x + 1) * W / w, where
    (W, H) = screen. The result is the screen pixel at the centre of that span, rounded down.
    The same rule applies to y.
    """
    raise NotImplementedError


def locate(root: Node, x: int, y: int) -> tuple[str, ...] | None:
    """Names from root down to the node that receives a click at screen pixel (x, y).

    root's x and y are screen coordinates. A node covers the pixels x0 <= px < x0 + w and
    y0 <= py < y0 + h of its box on the screen. The click goes to the topmost visible node
    covering the pixel; a node is drawn over its ancestors, so along one branch the deepest
    node covering the pixel is the one on top. Also:
    - a later sibling wins over an earlier one, even where the earlier one has descendants;
    - a child outside its parent's box still receives clicks there, unless the parent or
      another ancestor clips;
    - scroll offsets of every ancestor add up;
    - an invisible node and its whole subtree receive nothing and hide nothing.
    Returns None when nothing covers the pixel.
    """
    raise NotImplementedError
