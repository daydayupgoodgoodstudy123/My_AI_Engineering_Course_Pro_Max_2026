"""Split proof obligations without weakening plan prerequisites."""
from dataclasses import replace
from .model import WorkItem
from .support import ancestors


def split_proofs(items: list[WorkItem], proofs: dict[str, tuple[str, ...]]) -> list[WorkItem]:
    """Replace an item with multiple proof obligations by id::1, id::2, etc.

    A single proof keeps its id and uses the supplied replacement command.
    Multi-proof children run independently after
    every expanded original prerequisite; each child preserves evidence, change,
    irreversible/resolvers, and gets exactly one proof. Every downstream dep and
    resolver reference expands to ALL replacement ids, retaining input order and
    removing repeated ids. Reject zero proofs and generated-id collisions with
    ValueError. Output item order follows input, then proof tuple order.
    """
    raise NotImplementedError


def unresolved_irreversibles(items: list[WorkItem]) -> dict[str, list[str]]:
    """For a valid DAG return missing resolver prerequisites for each unsafe item.

    All dependencies and resolver ids name items. Resolver inclusion means a
    transitive prerequisite, not domination of every diagram path. Omit safe and
    reversible items; item keys follow input order, missing ids are sorted.
    """
    raise NotImplementedError
