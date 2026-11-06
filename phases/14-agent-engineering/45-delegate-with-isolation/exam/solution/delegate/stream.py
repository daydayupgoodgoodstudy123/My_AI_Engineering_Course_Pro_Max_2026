"""Private NDJSON integration receipts with an online dependency barrier."""
from collections.abc import AsyncIterator
import json
from .model import WorkUnit, Handoff
from .integrate import review_handoff


def _line(unit: str, reason: str | None) -> str:
    return json.dumps({"unit": unit, "status": "accepted" if reason is None else "rejected", "reason": reason}, sort_keys=True) + "\n"


async def handoff_lines(units: list[WorkUnit], incoming: AsyncIterator[Handoff]) -> AsyncIterator[str]:
    """Emit one private NDJSON verdict per worker; do not prefetch future receipts.

    Inputs are acyclic unique-id units with disjoint write ownership and at most
    one receipt per id. Hold a receipt until all its prerequisites have verdicts.
    Rejected prerequisites cause dependency rejection; otherwise review material
    proof/scope. After one receipt arrives, emit all newly resolved verdicts in
    sorted waves before pulling another receipt. Unknown ids are rejected at once.
    At end-of-stream reject unsubmitted known ids as missing, then resolve held
    dependants. Output codes are exercise data, not Lamport or an agent protocol.
    """
    by_id = {unit.id: unit for unit in units}
    pending = {}
    verdicts = {}
    def flush():
        lines = []
        while True:
            ready = sorted(name for name in pending if set(by_id[name].depends_on) <= verdicts.keys())
            if not ready:
                return lines
            for name in ready:
                handoff = pending.pop(name)
                reason = "dependency" if any(verdicts[dep] is not None for dep in by_id[name].depends_on) else review_handoff(by_id[name], handoff)
                verdicts[name] = reason
                lines.append(_line(name, reason))
    async for handoff in incoming:
        if handoff.unit not in by_id:
            yield _line(handoff.unit, "unknown")
            continue
        pending[handoff.unit] = handoff
        for line in flush():
            yield line
    for name in sorted(by_id.keys() - verdicts.keys() - pending.keys()):
        verdicts[name] = "missing"
        yield _line(name, "missing")
    for line in flush():
        yield line
