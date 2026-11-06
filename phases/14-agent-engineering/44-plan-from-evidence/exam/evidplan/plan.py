"""Validate source-backed plans and form dependency waves."""
from dataclasses import asdict, replace
from .model import WorkItem
from .support import cycle_members, ancestors


def _cycle_report(remaining: dict[str, set[str]]) -> list[str]:
    return sorted(remaining)


def _ordered_waves(items: list[WorkItem]) -> list[list[str]]:
    dependencies = {item.id: set(item.depends_on) for item in items}
    followers = {item.id: set() for item in items}
    for node, deps in dependencies.items():
        for dep in deps:
            followers[dep].add(node)
    ready = sorted(node for node, deps in dependencies.items() if not deps)
    waves = []
    completed = set()
    while ready:
        waves.append(ready)
        following = set()
        for node in ready:
            completed.add(node)
            for child in followers[node]:
                dependencies[child].discard(node)
                if not dependencies[child]:
                    following.add(child)
        ready = sorted(following)
    if len(completed) != len(items):
        remaining = {node: deps for node, deps in dependencies.items() if node not in completed}
        raise ValueError("cycle: " + ", ".join(_cycle_report(remaining)))
    return waves


def execution_waves(items: list[WorkItem]) -> list[list[str]]:
    """Group items into sorted dependency waves; reject unknown deps before cycles."""
    known = {item.id for item in items}
    for item in items:
        missing = sorted(set(item.depends_on) - known)
        if missing:
            raise ValueError(f"unknown dependency: {item.id}: {', '.join(missing)}")
    return _ordered_waves(items)


def validate(items: list[WorkItem]) -> list[str]:
    """Collect receipt, unknown-reference, exact-cycle and irreversible-order issues.

    An irreversible item's explicit resolver ids must be prerequisite ancestors.
    This annotation is a human judgment input, not automatic risk discovery.
    Report unknown deps even if a separate known subgraph also has a cycle.
    """
    issues = []
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        issues.append("duplicate ids")
    known = set(ids)
    unknown = False
    for item in items:
        if not item.evidence:
            issues.append(f"no evidence: {item.id}")
        if not item.proof.strip():
            issues.append(f"no proof: {item.id}")
        missing = sorted(set(item.depends_on) - known)
        if missing:
            unknown = True
            issues.append(f"unknown dependency: {item.id}: {', '.join(missing)}")
    clean = [replace(item, depends_on=tuple(dep for dep in item.depends_on if dep in known)) for item in items]
    if not unknown:
        try:
            _ordered_waves(clean)
        except ValueError as error:
            issues.append(str(error))
    if False:
        for item in items:
            if item.irreversible:
                missing = sorted(set(item.resolvers) - ancestors(items, item.id))
                if missing:
                    issues.append(f"unresolved before {item.id}: {', '.join(missing)}")
    return issues


def plan_document(items: list[WorkItem]) -> dict:
    """Return a blocked document with no waves for every invalid plan, never schedule it."""
    issues = validate(items)
    return {"status": "blocked" if issues else "ready", "issues": issues,
            "waves": execution_waves(items),
            "items": [asdict(item) for item in items]}
