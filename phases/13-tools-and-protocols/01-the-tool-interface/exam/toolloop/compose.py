"""Composite tools: a tool built from other tools can do whatever they can do."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .tools import Tool


@dataclass(frozen=True)
class Effect:
    kind: str  # "pure" or "consequential"
    path: tuple[str, ...]  # why it is consequential (see classify); () when pure
    actions: tuple[str, ...]  # the tools declared consequential that it can set off, sorted, each once


def classify(tools: Iterable[Tool]) -> dict[str, Effect]:
    """The effective kind of every tool, following the calls of composite tools.

    A tool is consequential if it is declared consequential, or if any tool it can reach
    through calls is. path says why: it starts at the tool and follows calls down to a
    tool declared consequential, stopping at the first one. When there are several such
    paths, path is the alphabetically first, comparing paths name by name.

    The call graph has no cycles. A call to a tool that is not in tools raises ValueError
    naming it.
    """
    raise NotImplementedError
