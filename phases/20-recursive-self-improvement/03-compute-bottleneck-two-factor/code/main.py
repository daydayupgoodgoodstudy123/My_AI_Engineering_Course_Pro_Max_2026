"""Research-pipeline speedup simulator: Amdahl's law plus a GPU queue (stdlib only).

An AI R&D cycle is split into five stages (ideation, coding, experiment compute,
evaluation, decision). AI labour speeds up the labour stages by a factor k, but the
experiment-compute stage can only shrink by a compute-growth factor g, so the total
speedup saturates at g / f_compute (Amdahl's law). A closed queue of N agent copies
sharing C GPUs then shows why extra copies stop adding useful experiments per cycle.
Usage: python3 main.py [--scenario software-only|compute-growth|both] [--automation 30]
       [--compute-growth 4] [--compute-fraction 0.40] [--agents 128] [--gpus 8]
       [--cycles 50] [--jitter 0.0] [--seed 7] [--human-decision]
See docs/en.md (Phase 20, Lesson 03: Compute Bottlenecks).
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import math
import random
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Sequence

DEFAULT_SEED = 7
SWEEP = (1, 2, 5, 10, 30, 100, 300, 1000)
LABOUR = "labour"
COMPUTE = "compute"
SUBMIT, FINISH = 0, 1


# --------------------------------------------------------------------------- stages


@dataclass(frozen=True)
class Stage:
    """One stage of the research cycle: its share of baseline wall-clock and its kind."""

    name: str
    fraction: float
    kind: str  # LABOUR (AI copies can speed it up) or COMPUTE (needs GPUs)


BASE_STAGES: tuple[Stage, ...] = (
    Stage("ideation", 0.15, LABOUR),
    Stage("coding", 0.25, LABOUR),
    Stage("experiment-compute", 0.40, COMPUTE),
    Stage("evaluation", 0.15, LABOUR),
    Stage("decision", 0.05, LABOUR),
)


def build_stages(compute_fraction: float = 0.40) -> tuple[Stage, ...]:
    """Rescale the labour stages so the compute stage takes `compute_fraction` of a cycle."""
    if not 0.0 < compute_fraction < 1.0:
        raise ValueError("compute_fraction must be strictly between 0 and 1")
    base_labour = sum(s.fraction for s in BASE_STAGES if s.kind == LABOUR)
    scale = (1.0 - compute_fraction) / base_labour
    out = []
    for s in BASE_STAGES:
        frac = compute_fraction if s.kind == COMPUTE else s.fraction * scale
        out.append(Stage(s.name, frac, s.kind))
    return tuple(out)


def multipliers_for(
    stages: Sequence[Stage], labour_k: float, compute_g: float, human_decision: bool = False
) -> dict[str, float]:
    """Per-stage speedup multipliers: k for labour stages, g for compute, 1 if humans still decide."""
    out: dict[str, float] = {}
    for s in stages:
        if s.kind == COMPUTE:
            out[s.name] = compute_g
        elif human_decision and s.name == "decision":
            out[s.name] = 1.0
        else:
            out[s.name] = labour_k
    return out


def cycle_time(stages: Sequence[Stage], mult: dict[str, float]) -> float:
    """Wall-clock of one research cycle in baseline-cycle units: sum of f_i / m_i."""
    return sum(s.fraction / mult[s.name] for s in stages)


def amdahl_speedup(stages: Sequence[Stage], mult: dict[str, float]) -> float:
    """Amdahl's law: total speedup = 1 / sum(f_i / m_i)."""
    return 1.0 / cycle_time(stages, mult)


def asymptote(stages: Sequence[Stage], mult: dict[str, float], accelerated: Iterable[str]) -> float:
    """Speedup when every stage in `accelerated` goes to zero time: 1 / sum over fixed stages of f_i / m_i."""
    acc = set(accelerated)
    fixed = sum(s.fraction / mult[s.name] for s in stages if s.name not in acc)
    return math.inf if fixed == 0 else 1.0 / fixed


def k_for_fraction_of_asymptote(
    stages: Sequence[Stage], mult: dict[str, float], accelerated: Iterable[str], frac: float
) -> float:
    """Labour multiplier needed to reach `frac` of the asymptote (fixed stages keep their multipliers)."""
    acc = set(accelerated)
    fixed = sum(s.fraction / mult[s.name] for s in stages if s.name not in acc)
    labour = sum(s.fraction for s in stages if s.name in acc)
    return labour / (fixed * (1.0 / frac - 1.0))


def labour_stage_names(stages: Sequence[Stage], human_decision: bool = False) -> list[str]:
    names = [s.name for s in stages if s.kind == LABOUR]
    if human_decision:
        names = [n for n in names if n != "decision"]
    return names


# ---------------------------------------------------------------------------- queue


@dataclass
class QueueResult:
    agents: int
    gpus: int
    horizon: float
    submitted: int
    completed: int
    queued: int
    running: int
    throughput: float  # completed experiments per baseline cycle
    utilization: float  # busy GPU-time / (gpus * horizon)
    mean_wait: float  # cycles an experiment sat in the queue before a GPU was free
    mean_cycle_time: float  # cycles between one agent's successive completed experiments


def simulate_queue(
    agents: int,
    gpus: int,
    stages: Sequence[Stage],
    labour_k: float,
    compute_g: float,
    horizon: float,
    jitter: float = 0.0,
    seed: int = DEFAULT_SEED,
    human_decision: bool = False,
) -> QueueResult:
    """Closed queue: each agent thinks (labour), submits one experiment, waits for a GPU, reads the result, repeats.

    Time unit = one baseline (human, un-automated) research cycle. Experiment duration is
    f_compute / g, optionally lognormal-jittered (mean preserved) with the given seed.
    """
    if agents < 1 or gpus < 1:
        raise ValueError("agents and gpus must be >= 1")
    rng = random.Random(seed)
    mult = multipliers_for(stages, labour_k, compute_g, human_decision)
    labour_time = sum(s.fraction / mult[s.name] for s in stages if s.kind == LABOUR)
    exp_base = sum(s.fraction / mult[s.name] for s in stages if s.kind == COMPUTE)

    def experiment_duration() -> float:
        if jitter <= 0.0:
            return exp_base
        return exp_base * math.exp(rng.gauss(0.0, jitter) - 0.5 * jitter * jitter)

    seq = itertools.count()
    events: list[tuple[float, int, int, int]] = []
    for a in range(agents):
        heapq.heappush(events, (labour_time, next(seq), SUBMIT, a))
    free = gpus
    waiting: deque[tuple[int, float]] = deque()
    submitted = completed = 0
    waits: list[float] = []
    busy = 0.0
    last_finish: dict[int, float] = {}
    cycle_times: list[float] = []

    def start(agent: int, submit_time: float, now: float) -> None:
        nonlocal free, busy
        free -= 1
        dur = experiment_duration()
        waits.append(now - submit_time)
        busy += max(0.0, min(now + dur, horizon) - now)
        heapq.heappush(events, (now + dur, next(seq), FINISH, agent))

    while events and events[0][0] <= horizon:
        now, _, kind, agent = heapq.heappop(events)
        if kind == SUBMIT:
            submitted += 1
            if free > 0:
                start(agent, now, now)
            else:
                waiting.append((agent, now))
        else:
            completed += 1
            free += 1
            if agent in last_finish:
                cycle_times.append(now - last_finish[agent])
            last_finish[agent] = now
            heapq.heappush(events, (now + labour_time, next(seq), SUBMIT, agent))
            if waiting:
                nxt, t_sub = waiting.popleft()
                start(nxt, t_sub, now)

    return QueueResult(
        agents=agents,
        gpus=gpus,
        horizon=horizon,
        submitted=submitted,
        completed=completed,
        queued=len(waiting),
        running=gpus - free,
        throughput=completed / horizon,
        utilization=busy / (gpus * horizon),
        mean_wait=statistics.fmean(waits) if waits else 0.0,
        mean_cycle_time=statistics.fmean(cycle_times) if cycle_times else math.nan,
    )


def agent_sweep(max_agents: int) -> list[int]:
    """1, 2, 4, ... up to max_agents (max_agents itself always included)."""
    out = []
    n = 1
    while n < max_agents:
        out.append(n)
        n *= 2
    out.append(max_agents)
    return out


def pool_ceiling(gpus: int, stages: Sequence[Stage], compute_g: float) -> float:
    """Max experiments per baseline cycle the GPU pool can finish: gpus / (f_compute / g)."""
    exp_time = sum(s.fraction / compute_g for s in stages if s.kind == COMPUTE)
    return gpus / exp_time


def saturation_point(rows: Sequence[QueueResult], tol: float = 0.05) -> int | None:
    """Smallest agent count in the sweep beyond which the next step adds < tol relative throughput."""
    for prev, nxt in zip(rows, rows[1:]):
        if prev.throughput > 0 and (nxt.throughput - prev.throughput) / prev.throughput < tol:
            return prev.agents
    return None


# ------------------------------------------------------------------------- reporting


def print_stage_table(stages: Sequence[Stage], sw: dict[str, float], both: dict[str, float], g: float) -> None:
    print(f"\n  {'stage':<20} {'fraction':>9} {'kind':>8} {'software-only':>14} {'with compute x' + format(g, 'g'):>18}")
    for s in stages:
        print(f"  {s.name:<20} {s.fraction:>9.1%} {s.kind:>8} {sw[s.name]:>13.0f}x {both[s.name]:>17.0f}x")
    f_c = sum(s.fraction for s in stages if s.kind == COMPUTE)
    f_l = 1.0 - f_c
    print(f"  labour share f_labour = {f_l:.1%}   compute share f_compute = {f_c:.1%}")


def print_amdahl_table(stages: Sequence[Stage], scenario: str, g: float, human_decision: bool) -> dict[str, float]:
    """Print the speedup sweep and return the asymptotes used in the headline."""
    acc = labour_stage_names(stages, human_decision)
    out: dict[str, float] = {}
    print("\n" + "-" * 78)
    if scenario == "compute-growth":
        print("AMDAHL SWEEP: compute grows by g, labour stays human (k = 1)")
        print(f"  {'g':>6} {'cycle time':>11} {'speedup':>9}")
        for gg in SWEEP:
            mult = multipliers_for(stages, 1.0, float(gg), human_decision)
            print(f"  {gg:>6}x {cycle_time(stages, mult):>10.3f} {amdahl_speedup(stages, mult):>8.2f}x")
        asym = asymptote(stages, multipliers_for(stages, 1.0, 1.0, human_decision), ["experiment-compute"])
        out["compute-only"] = asym
        print(f"  asymptote (g -> inf) = 1 / f_labour = {asym:.2f}x")
        return out

    sw_asym = asymptote(stages, multipliers_for(stages, 1.0, 1.0, human_decision), acc)
    out["software-only"] = sw_asym
    if scenario == "software-only":
        print("AMDAHL SWEEP: labour stages automated by k, experiment compute fixed (g = 1)")
        print(f"  {'k':>6} {'cycle time':>11} {'speedup':>9} {'of asymptote':>13}")
        for k in SWEEP:
            mult = multipliers_for(stages, float(k), 1.0, human_decision)
            sp = amdahl_speedup(stages, mult)
            print(f"  {k:>6}x {cycle_time(stages, mult):>10.3f} {sp:>8.2f}x {sp / sw_asym:>12.1%}")
        print(f"  asymptote (k -> inf) = {sw_asym:.2f}x")
        return out

    both_asym = asymptote(stages, multipliers_for(stages, 1.0, g, human_decision), acc)
    comp_only = amdahl_speedup(stages, multipliers_for(stages, 1.0, g, human_decision))
    out["both"] = both_asym
    out["compute-only-at-g"] = comp_only
    print(f"AMDAHL SWEEP: labour automated by k; experiment compute fixed (g = 1) vs grown {g:g}x")
    print(f"  {'k':>6} {'software-only':>14} {'of asym.':>9} {'compute x' + format(g, 'g') + ' only':>18} {'both':>9} {'of asym.':>9}")
    for k in SWEEP:
        sw = amdahl_speedup(stages, multipliers_for(stages, float(k), 1.0, human_decision))
        bo = amdahl_speedup(stages, multipliers_for(stages, float(k), g, human_decision))
        print(f"  {k:>6}x {sw:>13.2f}x {sw / sw_asym:>8.1%} {comp_only:>17.2f}x {bo:>8.2f}x {bo / both_asym:>8.1%}")
    print(f"  asymptotes: software-only {sw_asym:.2f}x   both (k -> inf, g = {g:g}) {both_asym:.2f}x")
    return out


def print_queue_table(label: str, rows: Sequence[QueueResult], ceiling: float, knee: float) -> None:
    print(f"\n  {label}")
    print(f"  {'agents':>7} {'submitted':>10} {'completed':>10} {'queued':>7} {'exp/cycle':>10} {'util':>7} {'mean wait':>10} {'cycle time':>11}")
    for r in rows:
        ct = f"{r.mean_cycle_time:>10.2f}" if not math.isnan(r.mean_cycle_time) else f"{'n/a':>10}"
        print(
            f"  {r.agents:>7} {r.submitted:>10} {r.completed:>10} {r.queued:>7} "
            f"{r.throughput:>10.2f} {r.utilization:>7.1%} {r.mean_wait:>10.2f} {ct}"
        )
    print(f"  pool ceiling = {ceiling:.2f} exp/cycle; analytic knee = {knee:.1f} agents (ceiling x single-agent cycle time)")


def run_queue_block(
    label: str,
    stages: Sequence[Stage],
    k: float,
    g: float,
    args: argparse.Namespace,
) -> tuple[list[QueueResult], float, float]:
    rows = [
        simulate_queue(n, args.gpus, stages, k, g, float(args.cycles), args.jitter, args.seed, args.human_decision)
        for n in agent_sweep(args.agents)
    ]
    ceiling = pool_ceiling(args.gpus, stages, g)
    knee = ceiling * cycle_time(stages, multipliers_for(stages, k, g, args.human_decision))
    print_queue_table(label, rows, ceiling, knee)
    return rows, ceiling, knee


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=["software-only", "compute-growth", "both"], default="both",
                        help="which factor moves: labour only, compute only, or both (default: %(default)s)")
    parser.add_argument("--automation", type=float, default=30.0,
                        help="labour speedup k used in the queue model (default: %(default)s, AI 2027's SC)")
    parser.add_argument("--compute-growth", type=float, default=4.0,
                        help="compute-stage multiplier g for the compute-growth/both scenarios (default: %(default)s)")
    parser.add_argument("--compute-fraction", type=float, default=0.40,
                        help="share of a baseline cycle spent waiting on experiment compute (default: %(default)s)")
    parser.add_argument("--agents", type=int, default=128, help="largest agent count in the sweep (default: %(default)s)")
    parser.add_argument("--gpus", type=int, default=8, help="GPU pool capacity: concurrent experiments (default: %(default)s)")
    parser.add_argument("--cycles", type=int, default=50, help="simulation horizon in baseline cycles (default: %(default)s)")
    parser.add_argument("--jitter", type=float, default=0.0,
                        help="lognormal sigma on experiment durations; 0 = deterministic (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed for jittered durations (default: %(default)s)")
    parser.add_argument("--human-decision", action="store_true", help="keep the decision stage at human speed (1x)")
    args = parser.parse_args()
    if args.automation < 1 or args.compute_growth < 1:
        parser.error("--automation and --compute-growth must be >= 1")
    if args.cycles < 1:
        parser.error("--cycles must be >= 1")

    stages = build_stages(args.compute_fraction)
    k, g = args.automation, args.compute_growth
    sw_mult = multipliers_for(stages, k, 1.0, args.human_decision)
    both_mult = multipliers_for(stages, k, g, args.human_decision)

    print("=" * 78)
    print("RESEARCH-PIPELINE SPEEDUP: AMDAHL'S LAW + A GPU QUEUE (Phase 20, Lesson 03)")
    print("=" * 78)
    print(f"  scenario={args.scenario}  k={k:g}  g={g:g}  gpus={args.gpus}  horizon={args.cycles} cycles"
          f"  jitter={args.jitter:g}  seed={args.seed}  human_decision={args.human_decision}")
    print_stage_table(stages, sw_mult, both_mult, g)

    asyms = print_amdahl_table(stages, args.scenario, g, args.human_decision)

    print("\n" + "-" * 78)
    print(f"GPU QUEUE: N agent copies share {args.gpus} GPUs; each thinks, submits one experiment, waits, repeats")
    blocks: dict[str, tuple[list[QueueResult], float, float]] = {}
    if args.scenario in ("software-only", "both"):
        blocks["software-only"] = run_queue_block(
            f"software-only: labour {k:g}x, compute fixed (experiment = {stages[2].fraction:.2f} cycles)", stages, k, 1.0, args)
    if args.scenario == "compute-growth":
        blocks["compute-growth"] = run_queue_block(
            f"compute-growth: labour human (1x), compute {g:g}x (experiment = {stages[2].fraction / g:.3f} cycles)", stages, 1.0, g, args)
    if args.scenario == "both":
        blocks["both"] = run_queue_block(
            f"both: labour {k:g}x, compute {g:g}x (experiment = {stages[2].fraction / g:.3f} cycles)", stages, k, g, args)

    # ----------------------------------------------------------------- headline
    f_c = sum(s.fraction for s in stages if s.kind == COMPUTE)
    print("\n" + "=" * 78)
    print("HEADLINE (every number below is computed from the inputs above)")
    print("-" * 78)
    acc = labour_stage_names(stages, args.human_decision)
    if "software-only" in asyms:
        sw_asym = asyms["software-only"]
        sp_k = amdahl_speedup(stages, sw_mult)
        sp_1000 = amdahl_speedup(stages, multipliers_for(stages, 1000.0, 1.0, args.human_decision))
        k95 = k_for_fraction_of_asymptote(stages, multipliers_for(stages, 1.0, 1.0, args.human_decision), acc, 0.95)
        fixed_txt = f"1 / f_compute = 1 / {f_c:.2f}" if not args.human_decision else f"1 / (f_compute + f_decision)"
        print(f"  Software-only ceiling: with compute fixed, no amount of AI labour beats {sw_asym:.2f}x ({fixed_txt}).")
        print(f"  At k = {k:g}x the pipeline runs {sp_k:.2f}x faster ({sp_k / sw_asym:.1%} of the ceiling); at k = 1000x only {sp_1000:.2f}x.")
        print(f"  95% of the ceiling is reached at k = {k95:.1f}x; everything past that is spent waiting on experiments.")
    if "compute-only" in asyms:
        print(f"  Compute-only ceiling: with human labour fixed, no amount of compute beats {asyms['compute-only']:.2f}x (1 / f_labour).")
    if "both" in asyms:
        both_asym = asyms["both"]
        sp_both = amdahl_speedup(stages, both_mult)
        print(f"  Growing compute {g:g}x lifts the ceiling to {both_asym:.2f}x (= g / f_compute); at k = {k:g}x that gives {sp_both:.2f}x,"
              f" i.e. {sp_both / amdahl_speedup(stages, sw_mult):.2f}x more than software alone.")
    for name, (rows, ceiling, knee) in blocks.items():
        last, first = rows[-1], rows[0]
        sat = saturation_point(rows)
        sat_txt = f"doubling past {sat} agents adds < 5% throughput" if sat else "no saturation inside the sweep"
        print(f"  Queue [{name}]: {args.gpus} GPUs cap useful experiments at {ceiling:.2f}/cycle; {sat_txt} (analytic knee {knee:.1f}).")
        print(f"    1 agent: {first.throughput:.2f} exp/cycle, wait {first.mean_wait:.2f};"
              f" {last.agents} agents: {last.throughput:.2f} exp/cycle, wait {last.mean_wait:.2f} cycles,"
              f" per-agent cycle time {first.mean_cycle_time:.2f} -> {last.mean_cycle_time:.2f} cycles"
              f" ({last.mean_cycle_time / first.mean_cycle_time:.1f}x slower per copy).")
    if args.jitter > 0:
        print(f"  Jitter sigma = {args.jitter:g} (seed {args.seed}): the ceiling above is a mean; variance adds queueing even below the knee.")
    print("=" * 78)


if __name__ == "__main__":
    main()
