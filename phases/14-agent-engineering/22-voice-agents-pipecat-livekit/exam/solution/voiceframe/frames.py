"""Frames: the typed units that move through a voice pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DOWNSTREAM = "downstream"  # source to sink: audio in, speech out
UPSTREAM = "upstream"  # feedback and control: cancel, metrics, barge-in


@dataclass
class Frame:
    kind: str
    payload: Any = None
    direction: str = DOWNSTREAM
    turn: int = 0
