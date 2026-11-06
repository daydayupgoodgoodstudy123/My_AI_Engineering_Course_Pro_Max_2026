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
    raise NotImplementedError
