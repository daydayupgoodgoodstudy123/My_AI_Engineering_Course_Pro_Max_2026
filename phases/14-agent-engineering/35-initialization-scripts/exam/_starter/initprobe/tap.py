"""Report an init run as TAP while it runs."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .probes import Probe


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
    raise NotImplementedError
