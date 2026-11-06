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
    tree = {"owners": set(), "children": {}}
    for unit in units:
        if unit.read_only:
            continue
        for path in unit.paths:
            node = tree
            for part in claim_parts(path):
                node = node["children"].setdefault(part, {"owners": set(), "children": {}})
            node["owners"].add(unit.id)
    prerequisites = prerequisite_sets(units)
    owners = {}
    conflicts = set()
    for path in dict.fromkeys(changed_paths):
        node = tree
        names = set(node["owners"])
        for part in claim_parts(path):
            node = node["children"].get(part)
            if node is None:
                break
            names.update(node["owners"])
        owners[path] = sorted(names)
        ranked = sorted(names)
        for index, left in enumerate(ranked):
            for right in ranked[index+1:]:
                if left not in prerequisites[right] and right not in prerequisites[left]:
                    conflicts.add((path, left, right))
    return {"owners": owners, "unowned": sorted(path for path, names in owners.items() if not names), "parallel_conflicts": sorted(conflicts)}
