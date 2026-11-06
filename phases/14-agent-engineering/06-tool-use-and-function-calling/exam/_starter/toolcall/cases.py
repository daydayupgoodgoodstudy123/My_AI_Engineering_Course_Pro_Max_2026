"""BFCL-style evaluation cases, and the dbm file that keeps them."""
from __future__ import annotations

import dbm
import json
from dataclasses import dataclass, field
from typing import Any

from .registry import validate

# Berkeley Function Calling Leaderboard V4's five categories and their weights.
WEIGHTS = {"agentic": 0.4, "multi_turn": 0.3, "live": 0.1, "non_live": 0.1, "hallucination": 0.1}
CATEGORIES = tuple(WEIGHTS)
AST_CATEGORIES = ("live", "non_live")  # graded on the calls themselves
STATE_CATEGORIES = ("agentic", "multi_turn")  # graded on the state the calls leave behind


@dataclass(frozen=True)
class Call:
    """One function call the model made: a tool name and its JSON arguments."""

    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Case:
    """One evaluation case.

    question: the user's turns, in order.
    tools: the catalog offered to the model, {"name", "description", "input_schema"} entries.
    accepted: the acceptable answers, in order of preference. Each is the complete list of
      calls a correct model makes; the calls inside one answer have no order. Live and
      Non-Live cases are graded against them. A Hallucination case has none: no tool fits.
    initial_state, expected_state: the drive before the calls, and the drive a correct
      trajectory leaves behind. Multi-Turn and Agentic cases are graded on them.
    """

    case_id: str
    category: str
    question: list[str]
    tools: list[dict[str, Any]]
    accepted: list[list[Call]] = field(default_factory=list)
    initial_state: dict[str, Any] | None = None
    expected_state: dict[str, Any] | None = None


class CaseBank:
    """Evaluation cases in a dbm file, one key per case, each value the case as JSON.

    A case comes back exactly as it was added, value types included: 5, 5.0 and "5" are
    different answers to the scorer. An id is any non-empty string without "#" or a line
    break (ids are written into TAP lines); "/", spaces and non-ASCII text are fine.
    """

    def __init__(self, path: str) -> None:
        """Open the bank at path, creating it when needed; an existing bank keeps its cases."""
        raise NotImplementedError

    def add(self, case: Case) -> None:
        """Store a new case.

        Raise ValueError, and store nothing, when the id is invalid or already stored, the
        category is not one of CATEGORIES, an accepted answer is empty, an accepted call names a
        tool outside the case's catalog or fails validate() against that tool's input_schema, a
        Hallucination case lists accepted answers, a Live or Non-Live case lists none, or a
        Multi-Turn or Agentic case lacks its initial or expected state. Validation never changes
        what is stored.
        """
        raise NotImplementedError

    def get(self, case_id: str) -> Case:
        """The stored case. An unknown id raises KeyError."""
        raise NotImplementedError

    def ids(self, category: str | None = None) -> list[str]:
        """Stored case ids, sorted, optionally from one category only."""
        raise NotImplementedError

    def cases(self, category: str | None = None) -> list[Case]:
        """Stored cases, in ids() order."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
