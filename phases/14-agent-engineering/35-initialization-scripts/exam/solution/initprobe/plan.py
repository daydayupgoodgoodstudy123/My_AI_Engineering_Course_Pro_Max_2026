"""Run the probes in dependency order and decide whether the agent may launch."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .probes import SEVERITIES, Probe, Result
from .report import InitReport
from .runner import _timed, fingerprint


class ProbeConfigError(ValueError):
    """The probe set itself is broken. Nothing runs, and the pre-task hook exits 2."""


async def run_init(probes: list[Probe], manifest: str, now: float) -> InitReport:
    """Run the init probes in dependency order and decide whether the agent may launch.

    Before anything runs, the probe set is checked: names are unique, every severity is
    block, warn or info, every name in needs is a listed probe, and needs never loop back.
    If any of that is wrong, ProbeConfigError is raised and no probe runs.

    A probe starts as soon as every probe it needs has finished; probes that wait on nothing
    run at the same time. A probe whose needs did not all pass or warn never runs: its result
    is "skip" with duration 0 and the detail "needs <names>", naming the failed probes behind
    it (directly, or through other skipped probes), each once, in the order the probes are
    listed.

    blocking lists the block-severity probes that failed or were skipped: init cannot vouch
    for a check it did not run. warnings lists every other probe that did not simply pass,
    except info-severity probes, which only appear in the results. Both follow the order of
    `probes`, and exit_code is 1 when anything is blocking, else 0.

    The report is stamped with `now` and fingerprint(manifest, probes), and its results follow
    the order of `probes`. So two runs over the same workbench give the same report apart from
    the timestamp and the durations, however differently their probes happen to finish.
    """
    results: list[Result | None] = [None] * len(probes)
    async for index, result in settle(probes):
        results[index] = result
    blocking, warnings = verdict(probes, results)
    return InitReport(
        now, fingerprint(manifest, probes), results, blocking, warnings, 1 if blocking else 0
    )


def check_probes(probes: list[Probe]) -> None:
    """Raise ProbeConfigError when the probe set cannot be run as written."""
    by_name: dict[str, Probe] = {}
    for probe in probes:
        if probe.name in by_name:
            raise ProbeConfigError(f"two probes are named {probe.name}")
        if probe.severity not in SEVERITIES:
            raise ProbeConfigError(
                f"{probe.name} has severity {probe.severity!r}; use block, warn or info"
            )
        by_name[probe.name] = probe
    for probe in probes:
        for need in probe.needs:
            if need not in by_name:
                raise ProbeConfigError(f"{probe.name} needs {need}, which is not a listed probe")
    done: set[str] = set()

    def visit(name: str, path: list[str]) -> None:
        if name in done:
            return
        if name in path:
            loop = path[path.index(name):] + [name]
            raise ProbeConfigError("needs go round in a loop: " + " -> ".join(loop))
        for need in by_name[name].needs:
            visit(need, path + [name])
        done.add(name)

    for probe in probes:
        visit(probe.name, [])


async def settle(probes: list[Probe]) -> AsyncIterator[tuple[int, Result]]:
    """Run the probes and yield (position in probes, result) as each one settles."""
    check_probes(probes)
    position = {probe.name: i for i, probe in enumerate(probes)}
    loop = asyncio.get_running_loop()
    settled = {probe.name: loop.create_future() for probe in probes}
    queue: asyncio.Queue[tuple[int, Result]] = asyncio.Queue()

    async def one(index: int, probe: Probe) -> None:
        behind: set[str] = set()  # the failed probes that keep this one from running
        for need in probe.needs:
            result, causes = await settled[need]
            if result.status == "fail":
                behind.add(need)
            elif result.status == "skip":
                behind |= causes
        if behind:
            names = sorted(behind, key=position.__getitem__)
            result = Result(probe.name, "skip", "needs " + ", ".join(names))
        else:
            result = await _timed(probe)
        settled[probe.name].set_result((result, frozenset(behind)))
        queue.put_nowait((index, result))

    tasks = [asyncio.create_task(one(i, probe)) for i, probe in enumerate(probes)]
    try:
        for _ in probes:
            yield await queue.get()
    finally:
        for task in tasks:
            task.cancel()


def verdict(probes: list[Probe], results: list[Result]) -> tuple[list[str], list[str]]:
    """(blocking, warnings) for a finished run, in the order the probes are listed."""
    blocking: list[str] = []
    warnings: list[str] = []
    for probe, result in zip(probes, results):
        if probe.severity == "block" and result.status in ("fail", "skip"):
            blocking.append(probe.name)
        elif probe.severity != "info" and result.status != "pass":
            warnings.append(probe.name)
    return blocking, warnings
