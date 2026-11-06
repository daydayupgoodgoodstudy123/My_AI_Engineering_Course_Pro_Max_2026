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

from .tree import Search

MAGIC = b"LATS"
VERSION = 1


def save(search: Search) -> bytes:
    """Pack a search into checkpoint bytes."""
    raise NotImplementedError


def load(data: bytes) -> Search:
    """Unpack checkpoint bytes into a Search equal to the one saved."""
    raise NotImplementedError
