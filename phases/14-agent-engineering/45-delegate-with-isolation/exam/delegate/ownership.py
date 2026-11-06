"""Nested ownership claims and possible parallel writes."""
from .model import WorkUnit
from .plan import claim_parts
from .support import prerequisite_sets


def audit_ownership(units: list[WorkUnit], changed_paths: list[str]) -> dict:
    """Index nested write claims and return all owners, unowned files and conflicts.

    Inputs have unique ids and a valid DAG. Read-only inspection is not ownership.
    Accumulate every ancestor/exact claim for each file; never hide simultaneous
    owners using longest-prefix selection. An overlapping pair is allowed only
    if either unit transitively depends on the other. Duplicate claims of one
    unit are harmless. owners preserves first input path order, owner ids sort;
    unowned and (file, left id, right id) parallel_conflicts are sorted distinct.
    '.' claims the entire repo; matching uses whole normalized path components.
    """
    raise NotImplementedError
