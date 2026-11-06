"""Graph partitions and event-record helpers for the plan service."""
from .model import WorkItem, Event


def _components(items: list[WorkItem]) -> list[frozenset[str]]:
    """Partition known vertices into strongly connected components, without recursion.

    Unknown dependency names are not vertices. Every known vertex occurs in exactly one
    component, including an isolated vertex. This helper is provided for graph consumers.
    """
    nodes = {item.id for item in items}
    edges = {item.id: set(item.depends_on) & nodes for item in items}
    reverse = {node: set() for node in nodes}
    for node, deps in edges.items():
        for dep in deps:
            reverse[dep].add(node)
    visited = set()
    finished = []
    for root in sorted(nodes):
        if root in visited:
            continue
        stack = [(root, False)]
        while stack:
            node, closing = stack.pop()
            if closing:
                finished.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((dep, False) for dep in edges[node] if dep not in visited)
    assigned = set()
    components = []
    for root in reversed(finished):
        if root in assigned:
            continue
        component = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node in assigned:
                continue
            assigned.add(node)
            component.add(node)
            stack.extend(reverse[node] - assigned)
        components.append(frozenset(component))
    return components


def cycle_members(items: list[WorkItem]) -> list[str]:
    """Return precisely the vertices on directed cycles, ignoring unknown references.

    The result is sorted and contains each member once. Downstream vertices that cannot
    reach themselves are not cycle members. Long plans do not depend on recursion depth.
    """
    self_edges = {item.id for item in items if item.id in item.depends_on}
    cyclic = set()
    for component in _components(items):
        if len(component) > 1 or not component.isdisjoint(self_edges):
            cyclic.update(component)
    return sorted(cyclic)


def ancestors(items: list[WorkItem], item_id: str) -> set[str]:
    """Return prerequisite ancestors for a known, validated acyclic plan."""
    lookup = {item.id: item for item in items}
    seen = set()
    stack = list(lookup[item_id].depends_on)
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(lookup[node].depends_on)
    return seen


def latest_records(items: list[WorkItem], events: list[Event]) -> dict:
    """Scan valid events once; use latest proof/done and the first approval.

    All event item ids are known. Supported kinds: item_started, artifact_changed,
    proof_ran, item_done, approved. Missing positions are -1. Proof receipts retain
    exact command and exit code; approvals only grant, never revoke. This
    helper does not decide completion.
    """
    records = {item.id: {"change": -1, "proof": None, "done": -1, "approved": -1} for item in items}
    for index, event in enumerate(events):
        row = records[event.item]
        if event.kind == "artifact_changed":
            row["change"] = index
        elif event.kind == "proof_ran":
            row["proof"] = (index, event.proof, event.exit_code)
        elif event.kind == "item_done":
            row["done"] = index
        elif event.kind == "approved" and row["approved"] < 0:
            row["approved"] = index
    return records
