"""The task frame: what an agent must know before it edits, and the checks that say so."""
from __future__ import annotations

from dataclasses import dataclass, field

from .repo import Repo

UNKNOWN_KINDS = ("discoverable", "decidable", "human", "deferred")


@dataclass(frozen=True)
class RepositoryFact:
    """A claim about the repository and the receipt that backs it (see parse_receipt).

    supports names the planned decisions the fact settles.
    """

    claim: str
    evidence: str
    supports: tuple[str, ...] = ()


@dataclass(frozen=True)
class Unknown:
    """A gap the frame admits to.

    kind is one of UNKNOWN_KINDS and decision is the planned decision it belongs to.
    A discoverable unknown says in look_at where the answer is (a path or a command).
    """

    question: str
    kind: str
    decision: str
    look_at: str = ""


@dataclass
class TaskFrame:
    goal: str
    allowed_paths: list[str]
    forbidden_paths: list[str]
    acceptance: list[str]
    facts: list[RepositoryFact] = field(default_factory=list)
    unknowns: list[Unknown] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LineReceipt:
    path: str
    line: int


@dataclass(frozen=True)
class CommandReceipt:
    command: str
    result: str


def parse_receipt(evidence: str) -> LineReceipt | CommandReceipt:
    """Read a fact's receipt. There are two forms:

        "path:line"              line `line` (counted from 1) of a file in the snapshot
        "$ command -> result"    a command that was run and what it printed, as free
                                 text; neither part may be empty

    Anything else raises ValueError.
    """
    text = evidence.strip()
    if text.startswith("$ "):
        command, sep, result = text[2:].partition(" -> ")
        if not sep or not command.strip() or not result.strip():
            raise ValueError(f"a command receipt needs the command and what it returned: {evidence!r}")
        return CommandReceipt(command.strip(), result.strip())
    path, sep, line = text.rpartition(":")
    if not sep or not path or not (line.isascii() and line.isdigit()) or int(line) < 1:
        raise ValueError(f"not a receipt: {evidence!r}")
    return LineReceipt(path, int(line))


def receipt_problem(evidence: str, repo: Repo) -> str | None:
    """Why a receipt does not resolve in repo, or None when it does.

    A line receipt resolves when its file is in the snapshot and has that line. A command
    receipt is an observation that cannot be replayed here; it resolves when well formed.
    """
    try:
        receipt = parse_receipt(evidence)
    except ValueError as exc:
        return str(exc)
    if isinstance(receipt, CommandReceipt):
        return None
    if receipt.path not in repo:
        return f"{receipt.path} is not in the repository"
    if receipt.line > repo.line_count(receipt.path):
        return f"{receipt.path} has no line {receipt.line}"
    return None


def covers(entry: str, path: str) -> bool:
    """True when path lies at or below entry.

    An entry ending in "/**" stands for everything below that directory; any other entry
    is one file. path may itself be a "dir/**" entry.
    """
    if entry.endswith("/**"):
        return path.startswith(entry[:-2])
    return path == entry


def overlapping(allowed: list[str], forbidden: list[str]) -> list[str]:
    """The entries that lie in both lists, sorted, each once.

    That is every allowed entry at or below a forbidden one, and every forbidden entry at
    or below an allowed one.
    """
    found = {a for a in allowed for f in forbidden if covers(f, a)}
    found |= {f for f in forbidden for a in allowed if covers(a, f)}
    return sorted(found)


def validate(frame: TaskFrame, repo: Repo) -> list[str]:
    """Why the frame cannot start yet, in this order; [] means it can.

    "goal is empty", "allowed paths are empty", "forbidden paths are empty",
    "acceptance evidence is empty", "repository facts are empty", then
    "unsupported fact: <claim>" for every fact whose receipt does not resolve in repo, in
    fact order, then "paths are both allowed and forbidden: <entries>" with the
    overlapping entries joined by ", ".
    """
    issues: list[str] = []
    if not frame.goal.strip():
        issues.append("goal is empty")
    if not frame.allowed_paths:
        issues.append("allowed paths are empty")
    if not frame.forbidden_paths:
        issues.append("forbidden paths are empty")
    if not frame.acceptance:
        issues.append("acceptance evidence is empty")
    if not frame.facts:
        issues.append("repository facts are empty")
    for fact in frame.facts:
        if receipt_problem(fact.evidence, repo) is not None:
            issues.append(f"unsupported fact: {fact.claim}")
    overlap = overlapping(frame.allowed_paths, frame.forbidden_paths)
    if overlap:
        issues.append(f"paths are both allowed and forbidden: {', '.join(overlap)}")
    return issues
