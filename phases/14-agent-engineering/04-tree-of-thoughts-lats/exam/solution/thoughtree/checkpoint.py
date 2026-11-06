"""Checkpoints for long LATS searches: a Search packed into bytes with struct, and back.

A search that is stopped, saved, loaded and run again must end exactly where an uninterrupted
search ends. So a checkpoint keeps everything run() depends on: the seed, c, the number of
iterations done, the solution if there is one, and every node with its state, trace, visits,
value_sum and children, in order.

The byte layout is up to you, within these rules:
- The data starts with MAGIC, then VERSION as an unsigned 16-bit little-endian integer.
- Numbers stay exact: every number is stored as its numerator and its denominator, each a
  signed 64-bit integer. Saving a number that does not fit raises ValueError.
- Floats keep every bit.
- load raises ValueError for anything that is not one complete checkpoint: another magic or
  version, missing bytes, or bytes left over at the end.
"""
from __future__ import annotations

import struct
from fractions import Fraction

from .game import OPS, Step
from .tree import Node, Search

MAGIC = b"LATS"
VERSION = 1

# magic, version, seed, c, iterations, nodes
_HEADER = struct.Struct("<4sHqdqI")
# solution steps, -1 for no solution yet
_COUNT = struct.Struct("<i")
# visits, value_sum, numbers in the state, children
_NODE = struct.Struct("<QdBI")
# numerator, denominator
_NUMBER = struct.Struct("<qq")


def save(search: Search) -> bytes:
    """Pack a search into checkpoint bytes.

    Nodes are written depth first: a node, then the subtree of each of its children in order.
    A node's record holds its statistics, its state, and the step that led to it (the root has
    none); traces are rebuilt from those steps on load.
    """
    nodes = list(_depth_first(search.root))
    out = bytearray()
    try:
        out += _HEADER.pack(MAGIC, VERSION, search.seed, search.c, search.iterations, len(nodes))
        if search.solution is None:
            out += _COUNT.pack(-1)
        else:
            out += _COUNT.pack(len(search.solution))
            for step in search.solution:
                _put_step(out, step)
        for node in nodes:
            out += _NODE.pack(node.visits, node.value_sum, len(node.state), len(node.children))
            for x in node.state:
                _put_number(out, x)
            if node is not search.root:
                _put_step(out, node.trace[-1])
    except struct.error as exc:
        raise ValueError(f"the search does not fit a checkpoint: {exc}") from exc
    return bytes(out)


def load(data: bytes) -> Search:
    """Unpack checkpoint bytes into a Search equal to the one saved."""
    reader = _Reader(data)
    try:
        magic, version, seed, c, iterations, count = reader.take(_HEADER)
        if magic != MAGIC:
            raise ValueError("not a ThoughTree checkpoint")
        if version != VERSION:
            raise ValueError(f"unsupported checkpoint version {version}")
        (steps,) = reader.take(_COUNT)
        if steps < -1:
            raise ValueError("corrupt solution length")
        solution = None if steps == -1 else [reader.step() for _ in range(steps)]
        root = reader.node(None)
    except struct.error as exc:
        raise ValueError("truncated checkpoint") from exc
    if reader.offset != len(data):
        raise ValueError("unexpected bytes after the checkpoint")
    if reader.nodes != count:
        raise ValueError("node count does not match the header")
    return Search(root, seed, c, iterations, solution)


def _depth_first(node: Node):
    yield node
    for child in node.children:
        yield from _depth_first(child)


def _put_number(out: bytearray, x: Fraction) -> None:
    out += _NUMBER.pack(x.numerator, x.denominator)


def _put_step(out: bytearray, step: Step) -> None:
    out += step.op.encode("ascii")
    for x in (step.a, step.b, step.result):
        _put_number(out, x)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0
        self.nodes = 0

    def take(self, fmt: struct.Struct) -> tuple:
        values = fmt.unpack_from(self.data, self.offset)
        self.offset += fmt.size
        return values

    def number(self) -> Fraction:
        numerator, denominator = self.take(_NUMBER)
        if denominator <= 0:
            raise ValueError("corrupt number")
        return Fraction(numerator, denominator)

    def step(self) -> Step:
        op = chr(self.data[self.offset]) if self.offset < len(self.data) else ""
        if op not in OPS:
            raise ValueError("corrupt step")
        self.offset += 1
        a, b, result = self.number(), self.number(), self.number()
        return Step(a, op, b, result)

    def node(self, parent: Node | None) -> Node:
        visits, value_sum, size, n_children = self.take(_NODE)
        self.nodes += 1
        state = tuple(self.number() for _ in range(size))
        trace = [] if parent is None else parent.trace + [self.step()]
        node = Node(state, trace, visits, value_sum)
        node.children = [self.node(node) for _ in range(n_children)]
        return node
