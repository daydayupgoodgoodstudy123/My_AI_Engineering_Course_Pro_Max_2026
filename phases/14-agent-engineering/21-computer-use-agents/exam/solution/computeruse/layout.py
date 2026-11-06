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
    (sw, sh), (W, H) = shot, screen
    return (2 * x + 1) * W // (2 * sw), (2 * y + 1) * H // (2 * sh)


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
    return _visit(root, x, y, 0, 0, None)


def _visit(node: Node, px: int, py: int, ox: int, oy: int, clip) -> tuple[str, ...] | None:
    if not node.visible:
        return None
    left, top = ox + node.x, oy + node.y
    inside_clip = clip is None or (clip[0] <= px < clip[2] and clip[1] <= py < clip[3])
    if not inside_clip:
        return None
    box = (left, top, left + node.w, top + node.h)
    child_clip = clip
    if node.clip:
        child_clip = box if clip is None else (
            max(box[0], clip[0]), max(box[1], clip[1]), min(box[2], clip[2]), min(box[3], clip[3])
        )
    cx, cy = left - node.scroll_x, top - node.scroll_y
    for child in reversed(node.children):
        hit = _visit(child, px, py, cx, cy, child_clip)
        if hit is not None:
            return (node.name,) + hit
    if box[0] <= px < box[2] and box[1] <= py < box[3]:
        return (node.name,)
    return None
