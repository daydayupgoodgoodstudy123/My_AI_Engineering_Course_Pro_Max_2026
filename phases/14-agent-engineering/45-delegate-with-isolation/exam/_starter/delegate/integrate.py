"""Read handoff evidence, then plan a bounded integration."""
from .model import WorkUnit, Handoff, Proof
from .plan import owns
from .support import safe_waves


def review_handoff(unit: WorkUnit, handoff: Handoff) -> str | None:
    """Return identity, scope, proof, or None, in this priority order.

    Read-only units cannot change files. Other changed files must belong under a
    claimed component prefix. Proof must match the exact assigned command, exit
    zero and include nonblank captured output. claimed_passed is never evidence.
    """
    raise NotImplementedError


def integrate(units: list[WorkUnit], handoffs: list[Handoff], final_changed: list[str],
              gate: Proof, expected_gate: str) -> dict:
    """Plan merges in dependency-wave/id order; do not execute a real merge or gate.

    Inputs have unique ids, known deps, no cycles and at most one handoff per id.
    Validate each material handoff before checking cross-unit file collisions.
    A path changed by two otherwise valid handoffs creates a decision listing
    both/all units; none of them may merge. Rejected prerequisites block their
    downstream units. Missing handoffs are rejected. Final diff must equal the
    union of planned merge files; diff_mismatch is the sorted symmetric difference.
    The full gate needs exact expected command, exit zero and nonblank output.
    Return status, merge_order, rejected reasons, decisions, diff_mismatch, gate_ok.
    """
    raise NotImplementedError
