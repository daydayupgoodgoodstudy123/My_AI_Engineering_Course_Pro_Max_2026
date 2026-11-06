"""The eval run as a GitHub Actions log: one folded group per layer, annotations, the verdict."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from .gate import GateReport
from .harness import CATEGORIES
from .store import CaseRecord


def _message(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _property(text: str) -> str:
    return _message(text).replace(":", "%3A").replace(",", "%2C")


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
    category_of = dict(suite)
    if len(category_of) != len(suite) or not set(category_of.values()) <= set(CATEGORIES):
        raise ValueError("suite lists a case twice or uses an unknown category")
    members = {category: [cid for cid, c in suite if c == category] for category in CATEGORIES}
    waiting = {category: len(ids) for category, ids in members.items()}
    queue = [category for category in CATEGORIES if members[category]]
    done: dict[str, CaseRecord] = {}

    def group(category: str) -> list[str]:
        lines = [f"::group::{_message(category)}\n"]
        for cid in members[category]:
            case = done[cid]
            if case.flaky:
                lines.append(f"::warning title={_property(cid)}::{_message(case.reason)}\n")
            elif not case.passed:
                lines.append(f"::error title={_property(cid)}::{_message(case.reason)}\n")
            else:
                lines.append(f"ok {cid} rounds={case.rounds}\n")
        lines.append("::endgroup::\n")
        return lines

    async for record in records:
        if record.cid not in category_of:
            raise ValueError(f"no case {record.cid!r} in the suite")
        if record.cid in done:
            raise ValueError(f"case {record.cid!r} finished twice")
        done[record.cid] = record
        waiting[category_of[record.cid]] -= 1
        while queue and waiting[queue[0]] == 0:
            for line in group(queue.pop(0)):
                yield line
    missing = [cid for cid, _ in suite if cid not in done]
    if missing:
        raise ValueError(f"no result for {missing}")
    report = decide(tuple(done[cid] for cid, _ in suite))
    if report.allowed:
        yield "::notice title=eval gate::ALLOW\n"
    else:
        verdict = "\n".join(("BLOCK",) + report.reasons)
        yield f"::error title=eval gate::{_message(verdict)}\n"
