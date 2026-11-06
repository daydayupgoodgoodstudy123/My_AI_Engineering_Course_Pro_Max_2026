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
    raise NotImplementedError
