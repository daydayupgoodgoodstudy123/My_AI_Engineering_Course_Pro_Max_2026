"""The eval run as a GitHub Actions log: one folded group per layer, annotations, the verdict."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from .gate import GateReport
from .harness import CATEGORIES
from .store import CaseRecord


async def workflow_log(
    suite: list[tuple[str, str]],
    records: AsyncIterator[CaseRecord],
    decide: Callable[[tuple[CaseRecord, ...]], GateReport],
) -> AsyncIterator[str]:
    """Write an eval run as GitHub Actions workflow commands while the cases finish.

    suite lists (case id, category) in suite order; records yields one CaseRecord per case, in
    the order the cases finish. Yield the log one line at a time, each line ending in "\\n".

    Each category with cases gets one group, in CATEGORIES order:
        ::group::<category>
        one line per case, in suite order:
            ::warning title=<case id>::<reason>    a flaky case
            ::error title=<case id>::<reason>      any other failure
            ok <case id> rounds=<rounds>           any other pass
        ::endgroup::
    A group goes out as soon as all of its cases have finished and every group before it is
    out. The last line is the verdict from decide(records in suite order):
        ::notice title=eval gate::ALLOW
        ::error title=eval gate::BLOCK, then one reason per line of the message
    In a message write % as %25, CR as %0D and LF as %0A, so every command stays on one line. In a
    property value (title=...) also write : as %3A and , as %2C.

    A suite that lists a case twice or uses an unknown category, a record for a case the suite
    does not list, a second record for a case, and records that end before every case has
    finished raise ValueError.
    """
    raise NotImplementedError
