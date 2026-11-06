"""Model-collapse simulator — stdlib Python.

A heavy-tailed truth (Zipf over V categories) is estimated from n samples,
resampled and refit for G generations under three regimes — replace,
accumulate, mix-real — while entropy, tail mass, extinctions, total variation
and a pass@k-style diversity score are tracked; theory checks (extinction
probability, Miller–Madow entropy drop) and a Gaussian late-collapse variant.
Usage: python main.py [--generations 20] [--samples 2000] [--vocab 200]
       [--regime all|replace|accumulate|mix] [--real-fraction 0.2] [--seed 11]
See docs/en.md (Phase 20, Lesson 16).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from typing import Sequence

DEFAULT_SEED = 11
LN2 = math.log(2.0)
REGIMES = ("replace", "accumulate", "mix")


@dataclass(frozen=True)
class Config:
    vocab: int = 200
    samples: int = 2000
    generations: int = 20
    zipf: float = 1.1
    real_fraction: float = 0.2
    tail_rank: int = 100
    k: int = 100
    smoothing: float = 0.0
    trials: int = 200
    cont_samples: int = 25
    seed: int = DEFAULT_SEED


@dataclass
class GenerationStats:
    generation: int
    entropy: float
    tail_mass: float
    tail_alive: int
    extinct: int
    tv: float
    distinct_k: float


# --------------------------------------------------------------------------
# Truth, sampling, fitting
# --------------------------------------------------------------------------

def zipf_distribution(vocab: int, exponent: float) -> list[float]:
    """p_rank ∝ 1 / rank**exponent, ranks 1..vocab (index 0 is the head)."""
    weights = [1.0 / (rank ** exponent) for rank in range(1, vocab + 1)]
    total = sum(weights)
    return [w / total for w in weights]


def sample_counts(probs: Sequence[float], n: int, rng: random.Random) -> list[int]:
    """Draw n i.i.d. categories from probs; return the count vector (a 'training set')."""
    counts = [0] * len(probs)
    if n <= 0:
        return counts
    cum = list(itertools.accumulate(probs))
    for idx in rng.choices(range(len(probs)), cum_weights=cum, k=n):
        counts[idx] += 1
    return counts


def fit(counts: Sequence[int], smoothing: float = 0.0) -> list[float]:
    """The 'model': empirical distribution with optional additive smoothing."""
    total = sum(counts) + smoothing * len(counts)
    return [(c + smoothing) / total for c in counts]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def entropy_bits(probs: Sequence[float]) -> float:
    return -sum(p * math.log2(p) for p in probs if p > 0.0)


def tail_mass(probs: Sequence[float], tail_rank: int) -> float:
    """Probability mass on categories whose truth-rank is below tail_rank (rarer)."""
    return sum(probs[tail_rank:])


def extinct_count(counts: Sequence[int]) -> int:
    return sum(1 for c in counts if c == 0)


def tail_alive(counts: Sequence[int], tail_rank: int) -> int:
    """How many tail categories (truth-rank beyond tail_rank) still have at least one sample."""
    return sum(1 for c in counts[tail_rank:] if c > 0)


def total_variation(p: Sequence[float], q: Sequence[float]) -> float:
    return 0.5 * sum(abs(a - b) for a, b in zip(p, q))


def expected_distinct(probs: Sequence[float], k: int) -> float:
    """pass@k-style diversity: expected number of distinct categories in k draws.

    P[category i appears at least once in k draws] = 1 - (1 - p_i)^k, the same
    algebra as pass@k = 1 - (1 - p)^k; summing over categories gives the
    expected distinct count."""
    return sum(1.0 - (1.0 - p) ** k for p in probs)


def measure(generation: int, model: Sequence[float], data: Sequence[int],
            truth: Sequence[float], cfg: Config) -> GenerationStats:
    return GenerationStats(
        generation=generation,
        entropy=entropy_bits(model),
        tail_mass=tail_mass(model, cfg.tail_rank),
        tail_alive=tail_alive(data, cfg.tail_rank),
        extinct=extinct_count(data),
        tv=total_variation(model, truth),
        distinct_k=expected_distinct(model, cfg.k),
    )


# --------------------------------------------------------------------------
# The recursive loop
# --------------------------------------------------------------------------

def run_regime(regime: str, truth: Sequence[float], cfg: Config,
               gen0_counts: Sequence[int], rng: random.Random) -> list[GenerationStats]:
    """Resample → refit for cfg.generations under one regime.

    replace     : each generation fits only on n fresh samples from the previous model
    accumulate  : each generation fits on real gen-0 data + every synthetic generation so far
    mix         : each generation fits on ρ·n fresh REAL samples + (1-ρ)·n synthetic samples
    """
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}")
    pool = list(gen0_counts)
    model = fit(pool, cfg.smoothing)
    history = [measure(0, model, pool, truth, cfg)]
    n_real = round(cfg.real_fraction * cfg.samples)
    for g in range(1, cfg.generations + 1):
        if regime == "replace":
            data = sample_counts(model, cfg.samples, rng)
        elif regime == "accumulate":
            new = sample_counts(model, cfg.samples, rng)
            pool = [a + b for a, b in zip(pool, new)]
            data = pool
        else:  # mix
            real = sample_counts(truth, n_real, rng)
            synthetic = sample_counts(model, cfg.samples - n_real, rng)
            data = [a + b for a, b in zip(real, synthetic)]
        model = fit(data, cfg.smoothing)
        history.append(measure(g, model, data, truth, cfg))
    return history


def run_all(cfg: Config, regimes: Sequence[str]) -> dict[str, list[GenerationStats]]:
    """Every regime starts from the SAME generation-0 model (same seed, same real sample)."""
    truth = zipf_distribution(cfg.vocab, cfg.zipf)
    gen0 = sample_counts(truth, cfg.samples, random.Random(cfg.seed))
    out: dict[str, list[GenerationStats]] = {}
    for regime in regimes:
        rng = random.Random(cfg.seed * 1000 + REGIMES.index(regime) + 1)
        out[regime] = run_regime(regime, truth, cfg, gen0, rng)
    return out


# --------------------------------------------------------------------------
# Theory: finite-sample resampling (Wright–Fisher-like)
# --------------------------------------------------------------------------

def extinction_probability(p: float, n: int) -> float:
    """Exact P[a category with probability p gets zero draws in n samples] = (1-p)^n ≈ e^{-np}."""
    return (1.0 - p) ** n


def expected_extinct_after_one_generation(truth: Sequence[float], n: int) -> float:
    return sum(extinction_probability(p, n) for p in truth)


def miller_madow_drop_bits(k_alive: int, n: int) -> float:
    """First-order expected entropy loss from one resample-and-refit step.

    E[H(p_hat)] ≈ H(p) − (K−1)/(2n) nats for K categories with n·p_i ≫ 1
    (the Miller–Madow bias of the plug-in entropy estimator), converted to bits."""
    return (k_alive - 1) / (2.0 * n * LN2)


def theory_checks(cfg: Config) -> dict[str, float]:
    truth = zipf_distribution(cfg.vocab, cfg.zipf)
    rng = random.Random(cfg.seed + 7)
    rarest_p = truth[-1]
    rarest_extinct = 0
    extinct_counts: list[int] = []
    drops: list[float] = []
    mm_estimates: list[float] = []
    for _ in range(cfg.trials):
        gen0 = sample_counts(truth, cfg.samples, rng)
        if gen0[-1] == 0:
            rarest_extinct += 1
        extinct_counts.append(extinct_count(gen0))
        model0 = fit(gen0)
        k_alive = cfg.vocab - extinct_count(gen0)
        mm_estimates.append(miller_madow_drop_bits(k_alive, cfg.samples))
        gen1 = sample_counts(model0, cfg.samples, rng)
        drops.append(entropy_bits(model0) - entropy_bits(fit(gen1)))
    return {
        "rarest_p": rarest_p,
        "rarest_np": rarest_p * cfg.samples,
        "rarest_theory_exact": extinction_probability(rarest_p, cfg.samples),
        "rarest_theory_exp": math.exp(-cfg.samples * rarest_p),
        "rarest_simulated": rarest_extinct / cfg.trials,
        "rarest_simulated_count": rarest_extinct,
        "expected_extinct_theory": expected_extinct_after_one_generation(truth, cfg.samples),
        "expected_extinct_simulated": statistics.fmean(extinct_counts),
        "mm_drop_bits": statistics.fmean(mm_estimates),
        "simulated_drop_bits": statistics.fmean(drops),
        "simulated_drop_median": statistics.median(drops),
    }


# --------------------------------------------------------------------------
# Continuous variant: Gaussian, variance shrinks (late collapse)
# --------------------------------------------------------------------------

def gaussian_chain(n: int, generations: int, rng: random.Random) -> list[float]:
    """Fit N(mu, sd) by sample mean / unbiased sd, resample n, repeat. Returns sd per generation.

    The unbiased variance makes E[var_{g+1} | var_g] = var_g (a martingale), yet the
    chain converges to zero variance almost surely — the mean is preserved, the
    distribution still collapses."""
    mu, sd = 0.0, 1.0
    out = [sd]
    for _ in range(generations):
        xs = [rng.gauss(mu, sd) for _ in range(n)]
        mu = statistics.fmean(xs)
        sd = statistics.stdev(xs)
        out.append(sd)
    return out


def continuous_summary(cfg: Config) -> list[dict[str, float]]:
    rng = random.Random(cfg.seed + 13)
    chains = [gaussian_chain(cfg.cont_samples, cfg.generations, rng) for _ in range(cfg.trials)]
    rows: list[dict[str, float]] = []
    for g in range(cfg.generations + 1):
        sds = [c[g] for c in chains]
        deciles = statistics.quantiles(sds, n=10)
        rows.append({
            "generation": g,
            "median_sd": statistics.median(sds),
            "p10_sd": deciles[0],
            "p90_sd": deciles[-1],
            "mean_var": statistics.fmean(s * s for s in sds),
            "frac_sd_below_half": sum(1 for s in sds if s < 0.5) / len(sds),
        })
    return rows


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def regime_label(regime: str, cfg: Config) -> str:
    return f"mix rho={cfg.real_fraction:.2f}" if regime == "mix" else regime


def print_regime_table(regime: str, hist: list[GenerationStats], truth_h: float,
                       truth_tail: float, cfg: Config) -> None:
    desc = {
        "replace": "each generation refits on n fresh samples from the previous model",
        "accumulate": "each generation refits on gen-0 real data + all synthetic generations",
        "mix": f"each generation refits on {cfg.real_fraction:.0%} fresh real + "
               f"{1 - cfg.real_fraction:.0%} synthetic samples",
    }[regime]
    print(f"\n[regime: {regime_label(regime, cfg)}]  {desc}")
    n_tail = cfg.vocab - cfg.tail_rank
    print(f"  {'gen':>4}  {'H(bits)':>8}  {'H lost':>7}  {'tail mass':>9}  {'tail alive':>10}  "
          f"{'extinct':>7}  {'TV':>6}  {'distinct@' + str(cfg.k):>12}")
    step = max(1, cfg.generations // 10)
    for s in hist:
        if s.generation == 0 or s.generation == cfg.generations or s.generation % step == 0:
            print(f"  {s.generation:>4}  {s.entropy:>8.3f}  {(truth_h - s.entropy) / truth_h:>7.1%}  "
                  f"{s.tail_mass:>9.3f}  {s.tail_alive:>4}/{n_tail:<5}  {s.extinct:>7}  "
                  f"{s.tv:>6.3f}  {s.distinct_k:>12.1f}")


def headline_lines(results: dict[str, list[GenerationStats]], truth: Sequence[float],
                   cfg: Config, theory: dict[str, float], cont: list[dict[str, float]]) -> list[str]:
    truth_h = entropy_bits(truth)
    truth_tail = tail_mass(truth, cfg.tail_rank)
    g = cfg.generations
    lines: list[str] = []
    for regime, hist in results.items():
        last = hist[-1]
        lines.append(
            f"{regime_label(regime, cfg)}: by generation {g} lost {(truth_h - last.entropy) / truth_h:.1%} "
            f"of entropy and {last.extinct} of {cfg.vocab} categories; tail mass {last.tail_mass:.3f} "
            f"(truth {truth_tail:.3f}) now carried by {last.tail_alive} of {cfg.vocab - cfg.tail_rank} tail "
            f"categories; TV to truth {last.tv:.3f}; expected distinct in {cfg.k} draws "
            f"{last.distinct_k:.1f} (truth {expected_distinct(truth, cfg.k):.1f})."
        )
    if "replace" in results and "accumulate" in results:
        r, a = results["replace"][-1], results["accumulate"][-1]
        lines.append(
            f"accumulate vs replace at generation {g}: TV {a.tv:.3f} vs {r.tv:.3f} "
            f"({'accumulate' if a.tv < r.tv else 'replace'} closer to truth), "
            f"extinct {a.extinct} vs {r.extinct}."
        )
    lines.append(
        f"theory: the rarest category (p={theory['rarest_p']:.5f}, n*p={theory['rarest_np']:.2f}) "
        f"dies in one resample with probability {theory['rarest_theory_exact']:.3f} "
        f"(e^-np={theory['rarest_theory_exp']:.3f}); simulated {theory['rarest_simulated']:.3f} "
        f"over {cfg.trials} trials; expected extinct after one resample {theory['expected_extinct_theory']:.1f} "
        f"vs simulated {theory['expected_extinct_simulated']:.1f}."
    )
    lines.append(
        f"entropy drop per resample (replace, gen 0->1): Miller-Madow first-order "
        f"{theory['mm_drop_bits']:.4f} bits vs simulated mean {theory['simulated_drop_bits']:.4f} bits "
        f"(ratio {theory['simulated_drop_bits'] / theory['mm_drop_bits']:.2f})."
    )
    last = cont[-1]
    lines.append(
        f"continuous: with n={cfg.cont_samples} Gaussian samples per generation, median sd fell to "
        f"{last['median_sd']:.2f} of truth by generation {g} while the mean variance was "
        f"{last['mean_var']:.2f} (its expectation is exactly 1.00 at every generation: a martingale); "
        f"{last['frac_sd_below_half']:.1%} of {cfg.trials} chains have sd below 0.5."
    )
    return lines


def build_report(cfg: Config, regimes: Sequence[str]) -> dict:
    truth = zipf_distribution(cfg.vocab, cfg.zipf)
    results = run_all(cfg, regimes)
    theory = theory_checks(cfg)
    cont = continuous_summary(cfg)
    return {
        "config": asdict(cfg),
        "truth": {"entropy": entropy_bits(truth), "tail_mass": tail_mass(truth, cfg.tail_rank),
                  "distinct_k": expected_distinct(truth, cfg.k)},
        "regimes": {r: [asdict(s) for s in h] for r, h in results.items()},
        "theory": theory,
        "continuous": cont,
        "headline": headline_lines(results, truth, cfg, theory, cont),
    }


def print_report(cfg: Config, regimes: Sequence[str]) -> dict:
    truth = zipf_distribution(cfg.vocab, cfg.zipf)
    truth_h = entropy_bits(truth)
    truth_tail = tail_mass(truth, cfg.tail_rank)
    report = build_report(cfg, regimes)
    results = {r: [GenerationStats(**s) for s in h] for r, h in report["regimes"].items()}

    print("=" * 78)
    print("MODEL COLLAPSE: RECURSIVE TRAINING ON YOUR OWN OUTPUT (Phase 20, Lesson 16)")
    print("=" * 78)
    print(f"truth: Zipf(s={cfg.zipf:.2f}) over V={cfg.vocab} categories | H={truth_h:.3f} bits | "
          f"tail mass (rank>{cfg.tail_rank})={truth_tail:.3f} | E[distinct@{cfg.k}]="
          f"{expected_distinct(truth, cfg.k):.1f}")
    print(f"loop:  n={cfg.samples} samples/generation | G={cfg.generations} generations | "
          f"smoothing={cfg.smoothing} | seed={cfg.seed}")
    print(f"gen 0 is the same for every regime: one real sample of n={cfg.samples} "
          f"({results[regimes[0]][0].extinct} categories already missing).")

    for regime in regimes:
        print_regime_table(regime, results[regime], truth_h, truth_tail, cfg)

    print(f"\nCOMPARISON at generation {cfg.generations} (same seed, same gen-0 model)")
    n_tail = cfg.vocab - cfg.tail_rank
    print(f"  {'regime':<14}  {'H(bits)':>8}  {'H lost':>7}  {'extinct':>7}  {'tail mass':>9}  {'tail alive':>10}  "
          f"{'TV':>6}  {'distinct@' + str(cfg.k):>12}")
    print(f"  {'truth':<14}  {truth_h:>8.3f}  {0.0:>7.1%}  {0:>7}  {truth_tail:>9.3f}  {n_tail:>4}/{n_tail:<5}  "
          f"{0.0:>6.3f}  {expected_distinct(truth, cfg.k):>12.1f}")
    for regime in regimes:
        s = results[regime][-1]
        print(f"  {regime_label(regime, cfg):<14}  {s.entropy:>8.3f}  {(truth_h - s.entropy) / truth_h:>7.1%}  "
              f"{s.extinct:>7}  {s.tail_mass:>9.3f}  {s.tail_alive:>4}/{n_tail:<5}  {s.tv:>6.3f}  "
              f"{s.distinct_k:>12.1f}")

    th = report["theory"]
    print(f"\nTHEORY CHECKS ({cfg.trials} independent trials)")
    print(f"  extinction of the rarest category (p={th['rarest_p']:.5f}, n*p={th['rarest_np']:.2f}) in one resample:")
    print(f"    exact (1-p)^n = {th['rarest_theory_exact']:.3f}   e^(-np) = {th['rarest_theory_exp']:.3f}   "
          f"simulated = {th['rarest_simulated']:.3f} ({th['rarest_simulated_count']}/{cfg.trials})")
    print(f"  expected categories extinct after one resample: theory sum(1-p_i)^n = "
          f"{th['expected_extinct_theory']:.1f}   simulated mean = {th['expected_extinct_simulated']:.1f}")
    print(f"  entropy drop gen 0 -> 1 under replace: Miller-Madow (K_alive-1)/(2n ln2) = "
          f"{th['mm_drop_bits']:.4f} bits   simulated mean = {th['simulated_drop_bits']:.4f} bits "
          f"(median {th['simulated_drop_median']:.4f})")

    cont = report["continuous"]
    print(f"\nCONTINUOUS VARIANT (late collapse): truth N(0,1), n={cfg.cont_samples} per generation, "
          f"{cfg.trials} chains")
    print(f"  {'gen':>4}  {'median sd':>9}  {'p10 sd':>7}  {'p90 sd':>7}  {'mean var':>8}  {'sd<0.5':>7}")
    step = max(1, cfg.generations // 5)
    for row in cont:
        g = int(row["generation"])
        if g == 0 or g == cfg.generations or g % step == 0:
            print(f"  {g:>4}  {row['median_sd']:>9.3f}  {row['p10_sd']:>7.3f}  {row['p90_sd']:>7.3f}  "
                  f"{row['mean_var']:>8.3f}  {row['frac_sd_below_half']:>7.1%}")

    print()
    print("=" * 78)
    print("HEADLINE")
    print("-" * 78)
    for line in report["headline"]:
        print(f"  {line}")
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generations", type=int, default=20, help="recursive generations G (default: %(default)s)")
    parser.add_argument("--samples", type=int, default=2000, help="samples n per generation (default: %(default)s)")
    parser.add_argument("--vocab", type=int, default=200, help="number of categories V (default: %(default)s)")
    parser.add_argument("--zipf", type=float, default=1.1, help="Zipf exponent of the truth (default: %(default)s)")
    parser.add_argument("--regime", choices=REGIMES + ("all",), default="all",
                        help="which training regime(s) to run (default: %(default)s)")
    parser.add_argument("--real-fraction", type=float, default=0.2,
                        help="fraction rho of fresh real data per generation in the mix regime (default: %(default)s)")
    parser.add_argument("--tail-rank", type=int, default=100,
                        help="categories with truth-rank beyond this count as the tail (default: %(default)s)")
    parser.add_argument("--k", type=int, default=100, help="draws for the pass@k-style distinct count (default: %(default)s)")
    parser.add_argument("--smoothing", type=float, default=0.0,
                        help="additive smoothing of the fitted model (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=200,
                        help="Monte-Carlo trials for theory checks and the continuous variant (default: %(default)s)")
    parser.add_argument("--cont-samples", type=int, default=25,
                        help="samples per generation in the Gaussian variant (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write the full report as JSON")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> Config:
    if not 0.0 <= args.real_fraction <= 1.0:
        raise SystemExit("--real-fraction must be in [0, 1]")
    if args.vocab < 2 or args.samples < 1 or args.generations < 1 or args.trials < 2:
        raise SystemExit("--vocab >= 2, --samples >= 1, --generations >= 1, --trials >= 2 required")
    return Config(vocab=args.vocab, samples=args.samples, generations=args.generations, zipf=args.zipf,
                  real_fraction=args.real_fraction, tail_rank=min(args.tail_rank, args.vocab - 1), k=args.k,
                  smoothing=args.smoothing, trials=args.trials, cont_samples=max(3, args.cont_samples),
                  seed=args.seed)


def main() -> None:
    args = parse_args()
    cfg = config_from_args(args)
    regimes = list(REGIMES) if args.regime == "all" else [args.regime]
    report = print_report(cfg, regimes)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\n  report written to {args.out}")


if __name__ == "__main__":
    main()
