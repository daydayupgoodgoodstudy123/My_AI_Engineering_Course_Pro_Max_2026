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
    if handoff.unit != unit.id:
        return "identity"
    if (unit.read_only and handoff.changed) or any(not any(owns(claim, path) for claim in unit.paths) for path in handoff.changed):
        return "scope"
    if handoff.proof.command != unit.proof or handoff.proof.exit_code != 0 or not handoff.proof.output.strip():
        return "proof"
    return None


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
    by_id = {unit.id: unit for unit in units}
    receipts = {handoff.unit: handoff for handoff in handoffs}
    rejected = {name: "unknown" for name in receipts if name not in by_id}
    valid = {}
    for unit in units:
        handoff = receipts.get(unit.id)
        reason = "missing" if handoff is None else review_handoff(unit, handoff)
        if reason is not None:
            rejected[unit.id] = reason
        else:
            valid[unit.id] = handoff
    writers = {}
    for name, handoff in valid.items():
        for path in set(handoff.changed):
            writers.setdefault(path, set()).add(name)
    decisions = []
    for path, names in sorted(writers.items()):
        if len(names) > 1:
            decisions.append({"path": path, "units": sorted(names)})
            rejected.update({name: "decision" for name in names})
    order = []
    waves, _ = safe_waves(units)
    for wave in waves:
        for name in wave:
            if name in rejected:
                continue
            if not set(by_id[name].depends_on) <= set(order):
                rejected[name] = "dependency"
            else:
                order.append(name)
    expected = {path for name in order for path in receipts[name].changed}
    mismatch = sorted(set(final_changed) ^ expected)
    gate_ok = gate.command == expected_gate and gate.exit_code == 0 and bool(gate.output.strip())
    return {"status": "ready" if not rejected and not mismatch and gate_ok else "blocked",
            "merge_order": order, "rejected": rejected, "decisions": decisions,
            "diff_mismatch": mismatch, "gate_ok": gate_ok}
