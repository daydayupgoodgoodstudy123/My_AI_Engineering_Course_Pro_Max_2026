"""Sleep-time consolidation of the archival tier: drop stale and duplicate facts without deleting them."""
from __future__ import annotations

from .archival import Archival


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
    raise NotImplementedError


def facts(archival: Archival) -> dict[str, str]:
    """The current value of every key, taken from its last valid fact (ordered as in consolidate)."""
    raise NotImplementedError
