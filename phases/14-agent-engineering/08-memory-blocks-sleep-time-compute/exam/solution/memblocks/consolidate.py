"""Sleep-time consolidation of the archival tier: drop stale and duplicate facts without deleting them."""
from __future__ import annotations

import re

from .archival import Archival, ArchivalRecord

FACT = re.compile(r"([a-z0-9_]+)=(.*?)(?:\s*\([^()]*\))?")
WORD = re.compile(r"[a-z0-9]+")


def consolidate(archival: Archival) -> list[tuple[str, str]]:
    """One consolidation pass. The sleep-time agent finds what is stale by itself.

    A record is a fact when it reads key=value: the key is lowercase letters, digits and
    underscores, and the value is the rest without a trailing note in parentheses, so
    "city=Lisbon (updated from Berlin)" is the fact city=Lisbon. Any other record is free text.

    Only valid records take part, ordered by at and then by insertion order.
    - Facts: the last fact of each key stays valid. Every earlier fact of that key is
      invalidated with the reason "superseded by <rid of the last one>".
    - Free text: a record whose words overlap those of an earlier free-text record that is
      still valid by more than 90% is invalidated with the reason "duplicate of <rid of the
      first such record>". The overlap is the Jaccard similarity of the two sets of words,
      where words are the runs of letters and digits, lowercased.

    Nothing is deleted. Returns (rid, reason) for every record this pass invalidated, in
    insertion order.
    """
    ordered = _in_time_order(archival)
    last = _last_facts(ordered)
    reasons: dict[str, str] = {}
    kept: list[tuple[str, set[str]]] = []
    for record in ordered:
        fact = parse_fact(record.text)
        if fact is not None:
            winner = last[fact[0]]
            if winner is not record:
                reasons[record.rid] = f"superseded by {winner.rid}"
            continue
        words = set(WORD.findall(record.text.lower()))
        for rid, earlier in kept:
            union = words | earlier
            if union and len(words & earlier) / len(union) > 0.9:
                reasons[record.rid] = f"duplicate of {rid}"
                break
        else:
            kept.append((record.rid, words))
    changes = []
    for record in archival.all_records():
        if record.rid in reasons:
            archival.invalidate(record.rid, reasons[record.rid])
            changes.append((record.rid, reasons[record.rid]))
    return changes


def facts(archival: Archival) -> dict[str, str]:
    """The current value of every key, taken from its last valid fact (ordered as in consolidate)."""
    last = _last_facts(_in_time_order(archival))
    return {key: parse_fact(record.text)[1] for key, record in sorted(last.items())}


def parse_fact(text: str) -> tuple[str, str] | None:
    match = FACT.fullmatch(text.strip())
    if match is None or not match.group(2):
        return None
    return match.group(1), match.group(2)


def _in_time_order(archival: Archival) -> list[ArchivalRecord]:
    valid = archival.valid_records()  # insertion order; sorted() is stable
    return sorted(valid, key=lambda record: record.at)


def _last_facts(ordered: list[ArchivalRecord]) -> dict[str, ArchivalRecord]:
    last: dict[str, ArchivalRecord] = {}
    for record in ordered:
        fact = parse_fact(record.text)
        if fact is not None:
            last[fact[0]] = record
    return last
