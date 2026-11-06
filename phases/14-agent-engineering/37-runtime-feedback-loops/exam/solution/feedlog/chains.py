"""Retry chains: which attempts led to which, so a review sees every failure before the final result."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .record import FeedbackRecord


@dataclass(frozen=True)
class Chain:
    attempts: tuple[str, ...]  # command ids, first attempt first
    orphaned_from: str | None  # the parent the first attempt points at, when that record is gone
    exit_code: int | None  # the last attempt's
    last_failure: str | None  # the latest attempt that exited non-zero


def retry_chains(records: Sequence[FeedbackRecord]) -> list[Chain]:
    """Link records into retry chains through parent_command_id.

    records come in the order they were written, as FeedbackLog.load_all returns them. Earlier and
    later always mean position in records, never started_at, both for the order of the chains and
    for a record that retries a record written after it.

    - A chain starts at a first attempt: a record with no parent, or one whose parent is not
      among records any more (rotated away). Such a chain is orphaned_from that parent's id.
    - It follows retries to an attempt nobody retried. An attempt retried more than once forks:
      each retry leads its own chain, and the chains share the attempts before the fork.
    - exit_code is the last attempt's. last_failure is the latest attempt with a non-zero exit
      code; an attempt without an exit code never ran to the end and is not a failure here.
    - Chains come in the order their last attempts were written.
    - A command id used twice, or a record that retries a record written after it, is a ValueError.
    """
    position: dict[str, int] = {}
    for i, record in enumerate(records):
        if record.command_id in position:
            raise ValueError(f"command id {record.command_id!r} is used twice")
        position[record.command_id] = i
    retried: set[str] = set()
    for i, record in enumerate(records):
        parent = record.parent_command_id
        if parent is not None and parent in position:
            if position[parent] >= i:
                raise ValueError(f"{record.command_id!r} retries {parent!r}, which is not written before it")
            retried.add(parent)
    chains = []
    for record in records:
        if record.command_id in retried:
            continue
        path = [record]
        while path[-1].parent_command_id in position:
            path.append(records[position[path[-1].parent_command_id]])
        path.reverse()
        failures = [r.command_id for r in path if r.exit_code is not None and r.exit_code != 0]
        chains.append(
            Chain(
                attempts=tuple(r.command_id for r in path),
                orphaned_from=path[0].parent_command_id,
                exit_code=record.exit_code,
                last_failure=failures[-1] if failures else None,
            )
        )
    return chains
