"""Evaluator-integrity simulator: Goodhart inside an improvement loop (stdlib only).

A population hill-climbs on an evaluator score. Each candidate has a latent true
quality q (pass rate on unseen items) and a set of memorised items on which the
evaluator always reports a pass, so the measured score is inflated exactly where
the loop has leaked its own test items. Regimes: static (same items every cycle),
rotating (fresh held-out items every k cycles), anchor (rotating selection set plus
a fixed anchor set that is measured but never selected on). Per cycle: measured,
true, gap, saturation flag, anchor drift and a consecutive-exceedance halting rule.
Usage: python main.py [--cycles 30] [--regime all] [--rotate-every 5] [--leak-rate 0.05]
       [--halt-gap 0.15] [--halt-patience 3] [--trials 20] [--seed 11]
See docs/en.md (Phase 20, Lesson 14).
"""

from __future__ import annotations

import argparse
import random
import statistics
from dataclasses import dataclass, field
from typing import Sequence

DEFAULT_SEED = 11
Q_MAX = 0.90              # ceiling on true quality: no candidate can exceed it
MAX_SCORE = 1.0           # the evaluator reports a pass rate in [0, 1]
SAT_FRACTION = 0.95       # saturation flag when measured >= 0.95 * MAX_SCORE
ANCHOR_BASE = 1_000_000   # anchor item ids live here so they never collide with selection ids
REGIMES = ("static", "rotating", "anchor")


# ----------------------------------------------------------------------------
# data model
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """A candidate system: latent true quality plus the eval items it has memorised."""

    quality: float
    memo: frozenset[int] = frozenset()


@dataclass
class LoopConfig:
    cycles: int = 30
    regime: str = "static"
    rotate_every: int = 5       # rotating/anchor: fresh selection items every k cycles (<=0: never)
    pool_blocks: int = 0        # >0: rotation wraps around this many blocks (items come back)
    leak_rate: float = 0.05     # per visible item, per child: probability it gets memorised
    halt_gap: float = 0.15      # halting rule threshold on the observable gap
    halt_patience: int = 3      # consecutive cycles above halt_gap before halting
    pop_size: int = 24
    survivors: int = 6
    eval_items: int = 40        # size of the selection set
    anchor_items: int = 40      # size of the anchor set (anchor regime only)
    mutation_sd: float = 0.015  # sd of the per-child change in true quality
    eval_noise: float = 0.0     # sd of Gaussian noise added to every reported score
    q0: float = 0.50            # initial true quality


@dataclass
class CycleRecord:
    cycle: int
    measured: float             # best candidate's score on the selection set (what the loop optimises)
    true: float                 # the same candidate's latent quality
    gap: float                  # measured - true  (oracle: the simulator knows q, an operator does not)
    saturated: bool             # measured >= SAT_FRACTION * MAX_SCORE
    memo_frac: float            # share of the current selection set the best candidate has memorised
    anchor: float | None = None  # anchor-set score of the best candidate (anchor regime)
    drift: float | None = None   # measured - anchor: the operator-observable estimate of the gap


@dataclass
class LoopResult:
    regime: str
    records: list[CycleRecord]
    oracle_halt: int | None       # first cycle the rule fires on the true gap (not observable)
    observed_halt: int | None     # first cycle the rule fires on anchor drift (anchor regime only)
    final_population: list[Candidate] = field(default_factory=list)

    @property
    def max_gap(self) -> float:
        return max(r.gap for r in self.records)

    @property
    def first_saturated(self) -> int | None:
        for r in self.records:
            if r.saturated:
                return r.cycle
        return None

    @property
    def final(self) -> CycleRecord:
        return self.records[-1]


# ----------------------------------------------------------------------------
# mechanism
# ----------------------------------------------------------------------------


def clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def expected_pass_rate(cand: Candidate, items: Sequence[int]) -> float:
    """Pass rate the evaluator reports: 1 on memorised items, q on everything else."""
    hits = sum(1 for i in items if i in cand.memo)
    if hits == 0:
        return cand.quality          # nothing leaked: the evaluator measures q exactly
    n = len(items)
    return (hits + cand.quality * (n - hits)) / n


def measured_score(cand: Candidate, items: Sequence[int], rng: random.Random,
                   noise: float = 0.0) -> float:
    score = expected_pass_rate(cand, items)
    if noise > 0.0:
        score += rng.gauss(0.0, noise)
    return clamp(score, 0.0, MAX_SCORE)


def selection_items(cfg: LoopConfig, cycle_index: int) -> list[int]:
    """Item ids used for selection at a 0-based cycle index."""
    if cfg.regime == "static" or cfg.rotate_every <= 0:
        block = 0
    else:
        block = cycle_index // cfg.rotate_every
        if cfg.pool_blocks > 0:
            block %= cfg.pool_blocks
    start = block * cfg.eval_items
    return list(range(start, start + cfg.eval_items))


def anchor_items(cfg: LoopConfig) -> list[int]:
    return list(range(ANCHOR_BASE, ANCHOR_BASE + cfg.anchor_items))


def mutate(parent: Candidate, visible: Sequence[int], cfg: LoopConfig,
           rng: random.Random) -> Candidate:
    """Child = parent with a small change in true quality plus leakage from visible items."""
    q = clamp(parent.quality + rng.gauss(0.0, cfg.mutation_sd), 0.0, Q_MAX)
    leaked = {i for i in visible if i not in parent.memo and rng.random() < cfg.leak_rate}
    return Candidate(q, parent.memo | frozenset(leaked))


def halt_cycle(series: Sequence[float], threshold: float, patience: int,
               first_cycle: int = 1) -> int | None:
    """Cycle number at which `series` has exceeded `threshold` for `patience` consecutive entries."""
    run = 0
    for idx, value in enumerate(series):
        run = run + 1 if value > threshold else 0
        if run >= patience:
            return first_cycle + idx
    return None


def anchor_drift(measured: float, anchor_score: float) -> float:
    """Operator-observable gap: selection score minus the never-selected-on anchor score."""
    return measured - anchor_score


def run_loop(cfg: LoopConfig, seed: int = DEFAULT_SEED) -> LoopResult:
    rng = random.Random(seed)
    pop = [Candidate(clamp(cfg.q0 + rng.gauss(0.0, cfg.mutation_sd), 0.0, Q_MAX))
           for _ in range(cfg.pop_size)]
    anchors = anchor_items(cfg)
    records: list[CycleRecord] = []
    for cycle in range(1, cfg.cycles + 1):
        items = selection_items(cfg, cycle - 1)
        scored = [(measured_score(c, items, rng, cfg.eval_noise), c) for c in pop]
        scored.sort(key=lambda t: -t[0])          # stable: ties keep population order
        best_score, best = scored[0]
        rec = CycleRecord(
            cycle=cycle,
            measured=best_score,
            true=best.quality,
            gap=best_score - best.quality,
            saturated=best_score >= SAT_FRACTION * MAX_SCORE,
            memo_frac=sum(1 for i in items if i in best.memo) / len(items),
        )
        if cfg.regime == "anchor":
            rec.anchor = measured_score(best, anchors, rng, cfg.eval_noise)
            rec.drift = anchor_drift(best_score, rec.anchor)
        records.append(rec)
        parents = [c for _, c in scored[:cfg.survivors]]
        children = [mutate(parents[i % cfg.survivors], items, cfg, rng)
                    for i in range(cfg.pop_size - cfg.survivors)]
        pop = parents + children                  # (mu + lambda): survivors carry over unchanged
    oracle = halt_cycle([r.gap for r in records], cfg.halt_gap, cfg.halt_patience)
    observed = None
    if cfg.regime == "anchor":
        observed = halt_cycle([r.drift or 0.0 for r in records], cfg.halt_gap, cfg.halt_patience)
    return LoopResult(cfg.regime, records, oracle, observed, pop)


# ----------------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------------

REGIME_BLURB = {
    "static": "same {n} items every cycle; per-item results visible to the optimiser",
    "rotating": "fresh held-out block of {n} items every {k} cycles; old items never return",
    "anchor": "{sel} + {a} anchor items measured but never selected on",
}


def describe(cfg: LoopConfig) -> str:
    rotates = cfg.regime != "static" and cfg.rotate_every > 0
    sel = (f"selection set rotates every {cfg.rotate_every} cycles" if rotates
           else f"selection set fixed ({cfg.eval_items} items)")
    text = REGIME_BLURB[cfg.regime].format(n=cfg.eval_items, k=cfg.rotate_every,
                                           a=cfg.anchor_items, sel=sel)
    if rotates and cfg.pool_blocks > 0:
        text += f"; rotation wraps after {cfg.pool_blocks} blocks"
    return text


def print_regime(result: LoopResult, cfg: LoopConfig) -> None:
    print(f"\nRegime: {result.regime} -- {describe(cfg)}")
    has_anchor = result.regime == "anchor"
    head = f"  {'cycle':>5}  {'measured':>8}  {'true':>6}  {'gap':>7}  {'memo':>5}  {'sat':>3}"
    if has_anchor:
        head += f"  {'anchor':>6}  {'drift':>7}"
    head += "  halt"
    print(head)
    halt = result.observed_halt if has_anchor else result.oracle_halt
    step = max(1, cfg.cycles // 15)
    for r in result.records:
        show = r.cycle == 1 or r.cycle == cfg.cycles or r.cycle % step == 0 or r.cycle == halt
        if not show:
            continue
        line = (f"  {r.cycle:>5}  {r.measured:>8.3f}  {r.true:>6.3f}  {r.gap:>+7.3f}"
                f"  {r.memo_frac:>5.0%}  {'SAT' if r.saturated else '.':>3}")
        if has_anchor:
            line += f"  {r.anchor:>6.3f}  {r.drift:>+7.3f}"
        if halt is not None and r.cycle == halt:
            line += "  HALT"
        elif halt is not None and r.cycle > halt:
            line += "  (past halt)"
        print(line)
    sat = result.first_saturated
    if sat is not None:
        rec = result.records[sat - 1]
        print(f"  -> saturation flag first set at cycle {sat} "
              f"(measured {rec.measured:.3f} while true quality is {rec.true:.3f})")
    else:
        print("  -> saturation flag never set")
    rule = f"gap > {cfg.halt_gap:.2f} for {cfg.halt_patience} consecutive cycles"
    if has_anchor:
        if result.observed_halt is not None:
            print(f"  -> halting rule ({rule}) fires on anchor drift at cycle {result.observed_halt}")
        else:
            print(f"  -> halting rule ({rule}) never fires on anchor drift")
        if result.oracle_halt != result.observed_halt:
            print(f"  -> oracle gap would fire at {result.oracle_halt}: anchor estimate disagrees")
    else:
        if result.oracle_halt is not None:
            print(f"  -> halting rule ({rule}) fires on the ORACLE gap at cycle {result.oracle_halt}")
        else:
            print(f"  -> halting rule ({rule}) never fires on the oracle gap")
        print("     (no anchor: an operator in this regime cannot compute any gap at all)")
    print(f"  -> max gap {result.max_gap:+.3f}; final measured {result.final.measured:.3f}, "
          f"final true {result.final.true:.3f}")


def fmt_opt(value: int | None) -> str:
    return "-" if value is None else str(value)


def monte_carlo(base: LoopConfig, regime: str, seed: int, trials: int) -> dict[str, float | int | None]:
    halts: list[int] = []
    max_gaps: list[float] = []
    finals: list[float] = []
    sats = 0
    for t in range(trials):
        cfg = LoopConfig(**{**base.__dict__, "regime": regime})
        res = run_loop(cfg, seed + 1 + t)
        fired = res.observed_halt if regime == "anchor" else res.oracle_halt
        if fired is not None:
            halts.append(fired)
        if res.first_saturated is not None:
            sats += 1
        max_gaps.append(res.max_gap)
        finals.append(res.final.true)
    return {
        "halt_frac": len(halts) / trials,
        "halt_count": len(halts),
        "halt_median": statistics.median(halts) if halts else None,
        "sat_frac": sats / trials,
        "max_gap_median": statistics.median(max_gaps),
        "final_true_median": statistics.median(finals),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycles", type=int, default=30, help="improvement cycles (default: %(default)s)")
    parser.add_argument("--regime", choices=REGIMES + ("all",), default="all",
                        help="evaluator regime to run (default: %(default)s)")
    parser.add_argument("--rotate-every", type=int, default=5,
                        help="rotating/anchor: fresh items every k cycles; <=0 never (default: %(default)s)")
    parser.add_argument("--pool-blocks", type=int, default=0,
                        help="rotation wraps around this many item blocks; 0 = unlimited (default: %(default)s)")
    parser.add_argument("--leak-rate", type=float, default=0.05,
                        help="per-item memorisation probability per child (default: %(default)s)")
    parser.add_argument("--halt-gap", type=float, default=0.15,
                        help="halting threshold on the observable gap (default: %(default)s)")
    parser.add_argument("--halt-patience", type=int, default=3,
                        help="consecutive exceedances before halting (default: %(default)s)")
    parser.add_argument("--eval-noise", type=float, default=0.0,
                        help="sd of noise on every reported score (default: %(default)s)")
    parser.add_argument("--anchor-items", type=int, default=40,
                        help="anchor set size (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=20,
                        help="Monte-Carlo seeds per regime in the comparison (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    args = parser.parse_args()

    base = LoopConfig(cycles=args.cycles, rotate_every=args.rotate_every, pool_blocks=args.pool_blocks,
                      leak_rate=args.leak_rate, halt_gap=args.halt_gap, halt_patience=args.halt_patience,
                      eval_noise=args.eval_noise, anchor_items=args.anchor_items)
    regimes = list(REGIMES) if args.regime == "all" else [args.regime]

    print("=" * 78)
    print("EVALUATOR INTEGRITY IN AN IMPROVEMENT LOOP (Phase 20, Lesson 14)")
    print("=" * 78)
    print(f"config: cycles={base.cycles} leak_rate={base.leak_rate:.3f} rotate_every={base.rotate_every} "
          f"halt_gap={base.halt_gap:.2f} patience={base.halt_patience} pop={base.pop_size} "
          f"survivors={base.survivors} items={base.eval_items} q_max={Q_MAX:.2f} "
          f"eval_noise={base.eval_noise:.3f} seed={args.seed}")
    print("columns: measured = best candidate's selection score; true = its latent quality; "
          "gap = measured - true;")
    print("         memo = share of the selection set it has memorised; sat = measured >= "
          f"{SAT_FRACTION:.2f} of max")

    results: dict[str, LoopResult] = {}
    for regime in regimes:
        cfg = LoopConfig(**{**base.__dict__, "regime": regime})
        results[regime] = run_loop(cfg, args.seed)
        print_regime(results[regime], cfg)

    print("\n" + "-" * 78)
    print(f"Comparison at seed {args.seed}")
    print(f"  {'regime':<9} {'final meas':>10} {'final true':>10} {'max gap':>8} {'first sat':>9} "
          f"{'oracle halt':>11} {'observed halt':>13}")
    for regime, res in results.items():
        print(f"  {regime:<9} {res.final.measured:>10.3f} {res.final.true:>10.3f} {res.max_gap:>+8.3f} "
              f"{fmt_opt(res.first_saturated):>9} {fmt_opt(res.oracle_halt):>11} "
              f"{fmt_opt(res.observed_halt) if regime == 'anchor' else 'n/a':>13}")

    mc: dict[str, dict[str, float | int | None]] = {}
    if args.trials > 0:
        print(f"\nMonte-Carlo over {args.trials} seeds per regime ({base.cycles} cycles each)")
        print(f"  {'regime':<9} {'halt fired':>18} {'median halt':>11} {'saturated':>9} "
              f"{'median max gap':>14} {'median final true':>17}")
        for regime in regimes:
            m = monte_carlo(base, regime, args.seed, args.trials)
            mc[regime] = m
            label = "oracle" if regime != "anchor" else "anchor"
            fired = f"{m['halt_frac']:.1%} ({m['halt_count']}/{args.trials}, {label})"
            med = "-" if m["halt_median"] is None else f"{m['halt_median']:.1f}"
            print(f"  {regime:<9} {fired:>18} {med:>11} {m['sat_frac']:>9.1%} "
                  f"{m['max_gap_median']:>+14.3f} {m['final_true_median']:>17.3f}")

    print("\n" + "=" * 78)
    print("HEADLINE")
    print("-" * 78)
    if "static" in results:
        s = results["static"]
        peak = max(s.records, key=lambda r: r.gap)
        print(f"  Static evaluator: the measured-true gap reaches {peak.gap:+.3f} by cycle {peak.cycle}; "
              f"the halting rule (gap > {base.halt_gap:.2f} x{base.halt_patience}) "
              + (f"would fire at cycle {s.oracle_halt}, but only an oracle can see that gap."
                 if s.oracle_halt else "never fires."))
        if s.first_saturated:
            rec = s.records[s.first_saturated - 1]
            print(f"  Saturation: measured hits {rec.measured:.3f} at cycle {s.first_saturated} while true "
                  f"quality is {rec.true:.3f}; after saturation the evaluator carries no gradient.")
    if "rotating" in results:
        r = results["rotating"]
        print(f"  Rotating every {base.rotate_every}: max gap {r.max_gap:+.3f}, "
              + (f"halting fires at cycle {r.oracle_halt}." if r.oracle_halt else "halting never fires.")
              + f" Final true quality {r.final.true:.3f}"
              + (f" vs {results['static'].final.true:.3f} static." if "static" in results else "."))
    if "anchor" in results:
        a = results["anchor"]
        diffs = [abs(rec.drift - rec.gap) for rec in a.records if rec.drift is not None]
        print(f"  Anchor+rotating: anchor drift tracks the oracle gap to within {max(diffs):.3f}; "
              f"observable halt at {fmt_opt(a.observed_halt)}, oracle halt at {fmt_opt(a.oracle_halt)}.")
    if mc:
        parts = []
        for regime, m in mc.items():
            parts.append(f"{regime} {m['halt_frac']:.1%} ({m['halt_count']}/{args.trials})")
        print("  Across seeds the halting rule fires in: " + "; ".join(parts) + ".")
    print("  The gap is the health metric: an evaluator the loop can read is an objective, not a measure.")


if __name__ == "__main__":
    main()
