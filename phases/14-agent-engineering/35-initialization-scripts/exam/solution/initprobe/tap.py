"""Report an init run as TAP while it runs."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .plan import ProbeConfigError, check_probes, settle, verdict
from .probes import Probe, Result


async def stream_tap(probes: list[Probe]) -> AsyncIterator[str]:
    """Run the probes as run_init does, and report each one as a TAP line the moment it settles.

    A probe's test number is its position in `probes` (1-based), fixed before anything runs, so
    lines come in the order probes finish and a reader still knows which probe each one is:

        ok 2 - runtime # pass 3ms python 3.12
        not ok 4 - dependencies # fail 12ms missing: pyyaml
        ok 6 - state_freshness # warn 0ms no state file yet
        ok 1 - test_command # SKIP needs dependencies

    A probe that ran is "ok" unless its status is fail, and its comment gives the status, the
    duration and the detail. A skipped probe is "ok ... # SKIP <reason>", sent as soon as the
    probes it needs have settled. A detail is escaped so that every probe stays on one line:
    first each backslash is written as \\\\, then each line feed as \\n and each carriage
    return as \\r. Every other character, tabs and "#" included, is left as it is. After the
    last probe come the plan line "1..N" and the verdict, "# ready" or
    "# refuse to launch: <blocking probes>".

    If the probe set is broken (see run_init), the whole stream is one line,
    "Bail out! <what is wrong>", and nothing runs. Every item is one line ending in "\\n".
    """
    try:
        check_probes(probes)
    except ProbeConfigError as exc:
        yield f"Bail out! {_escape(str(exc))}\n"
        return
    results: list[Result | None] = [None] * len(probes)
    async for index, result in settle(probes):
        results[index] = result
        yield _test_line(index + 1, result)
    yield f"1..{len(probes)}\n"
    blocking, _ = verdict(probes, results)
    yield f"# refuse to launch: {', '.join(blocking)}\n" if blocking else "# ready\n"


def _test_line(number: int, result: Result) -> str:
    if result.status == "skip":
        return f"ok {number} - {result.name} # SKIP {_escape(result.detail)}\n"
    ok = "not ok" if result.status == "fail" else "ok"
    return (
        f"{ok} {number} - {result.name} # {result.status} {result.duration_ms}ms "
        f"{_escape(result.detail)}\n"
    )


def _escape(detail: str) -> str:
    return detail.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
