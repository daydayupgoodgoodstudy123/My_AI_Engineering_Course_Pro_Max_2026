"""Determine completion from fresh evidence, prerequisites and approvals."""
from .model import WorkItem, Event
from .plan import execution_waves
from .support import ancestors, latest_records


def resume_state(items: list[WorkItem], events: list[Event]) -> dict:
    """Return sorted complete/ready ids, next id (or None), and blocked reasons.

    Inputs are a validated acyclic plan and valid events. Use latest_records.
    A done receipt counts only after the exact successful proof, which must be
    later than the last artifact change of this item AND all prerequisite
    ancestors. Prerequisites must themselves be complete. Irreversible work
    needs an approved event before its done receipt and before it is ready.
    Blocked reasons, in priority order: dependencies, approval, fresh proof.
    A locally fresh item with incomplete deps is still incomplete. Ready items
    are incomplete items whose direct deps are complete and approval is present.
    """
    records = latest_records(items, events)
    by_id = {item.id: item for item in items}
    complete = set()
    for wave in execution_waves(items):
        for item_id in wave:
            item = by_id[item_id]
            record = records[item_id]
            proof = record["proof"]
            frontier = max(records[node]["change"] for node in ancestors(items, item_id) | {item_id})
            fresh = proof is not None and proof[1] == item.proof and proof[2] == 0 and proof[0] > frontier and record["done"] > proof[0]
            approved = not item.irreversible or 0 <= record["approved"] < record["done"]
            if fresh and approved and set(item.depends_on) <= complete:
                complete.add(item_id)
    ready = []
    blocked = {}
    for item in items:
        if item.id in complete:
            continue
        if not set(item.depends_on) <= complete:
            blocked[item.id] = "dependencies"
        elif item.irreversible and records[item.id]["approved"] < 0:
            blocked[item.id] = "approval"
        else:
            ready.append(item.id)
            blocked[item.id] = "fresh proof"
    ready.sort()
    return {"complete": sorted(complete), "ready": ready, "next": ready[0] if ready else None, "blocked": blocked}
