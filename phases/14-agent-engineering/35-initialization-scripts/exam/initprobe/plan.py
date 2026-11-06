"""Run the probes in dependency order and decide whether the agent may launch."""
from __future__ import annotations

from .probes import Probe
from .report import InitReport


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
    raise NotImplementedError
