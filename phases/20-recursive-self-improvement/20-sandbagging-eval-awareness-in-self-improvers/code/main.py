"""Noise-injection sandbagging screen — stdlib Python.

Simulates the detector of Tice et al. (NeurIPS 2025, arXiv:2412.01784): add
Gaussian weight noise of magnitude sigma and re-measure accuracy. An honest
policy degrades smoothly; a sandbagging policy hides capability behind a fragile
suppression layer that breaks before core capability does, so accuracy rises
before it falls; an evaluation-aware policy sandbags only when its test-detector
fires. Finite-sample curves feed a max-rise detector; the script reports
detection and false-positive rates over trials, thresholds, gaps and awareness.
Usage: python main.py [--trials 200] [--samples 400] [--gap 0.15]
                      [--awareness-rate 0.5] [--threshold 0.05] [--policy all]
                      [--sigmas 0,0.02,...,0.20] [--seed 11] [--out stats.json]
See docs/en.md (Phase 20, Lesson 20).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from typing import Dict, List, Sequence

DEFAULT_SEED = 11
DEFAULT_SIGMAS = "0,0.02,0.04,0.06,0.08,0.10,0.12,0.14,0.16,0.18,0.20"
POLICIES = ("honest", "sandbag", "aware")
ROC_THRESHOLDS = (0.00, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10)
GAP_SWEEP = (0.03, 0.06, 0.10, 0.15, 0.20)


# ----------------------------------------------------------------------------
# Step 1 — capability profile: what noise does to an honest model
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Profile:
    """Shape of the accuracy-vs-noise curve.

    base: accuracy with no noise (full capability).
    chance: accuracy floor once the weights are destroyed (4-way MCQ -> 0.25).
    capability_scale: sigma at which core capability has lost 1 - 1/e of its headroom.
    suppressor_scale: sigma at which the sandbagging layer has broken on 1 - 1/e of items.
    The suppressor is more fragile than the capability (smaller scale), which is
    the empirical premise of the noise-injection screen.
    """

    base: float = 0.80
    chance: float = 0.25
    capability_scale: float = 0.15
    suppressor_scale: float = 0.03


def honest_accuracy(sigma: float, prof: Profile) -> float:
    """Smooth monotone decay from base to chance: acc(sigma) = chance + headroom * g(sigma)."""
    g = math.exp(-((sigma / prof.capability_scale) ** 2))
    return prof.chance + (prof.base - prof.chance) * g


def break_probability(sigma: float, prof: Profile) -> float:
    """Share of items on which noise has disabled the suppression layer."""
    return 1.0 - math.exp(-((sigma / prof.suppressor_scale) ** 2))


def suppressed_accuracy(sigma: float, gap: float, prof: Profile) -> float:
    """What a working suppressor shows: the target, unless noise already took the model below it."""
    target = prof.base - gap
    return min(target, honest_accuracy(sigma, prof))


def expected_accuracy(policy: str, sigma: float, gap: float, awareness: float,
                      prof: Profile) -> float:
    """Noise-free expectation of measured accuracy for one policy at one sigma."""
    honest = honest_accuracy(sigma, prof)
    if policy == "honest":
        return honest
    p_break = break_probability(sigma, prof)
    sandbag = (1.0 - p_break) * suppressed_accuracy(sigma, gap, prof) + p_break * honest
    if policy == "sandbag":
        return sandbag
    if policy == "aware":
        return awareness * sandbag + (1.0 - awareness) * honest
    raise ValueError(f"unknown policy {policy!r}")


# ----------------------------------------------------------------------------
# Step 2 — finite-sample measurement at a sigma grid
# ----------------------------------------------------------------------------

def sample_item(policy: str, sigma: float, gap: float, awareness: float,
                prof: Profile, rng: random.Random) -> bool:
    """One benchmark item answered by the noised model. Returns True if correct."""
    p_true = honest_accuracy(sigma, prof)
    if policy == "honest":
        return rng.random() < p_true
    if policy == "aware" and not (awareness > 0.0 and rng.random() < awareness):
        return rng.random() < p_true            # test-detector silent -> answers honestly
    if rng.random() < break_probability(sigma, prof):
        return rng.random() < p_true            # noise disabled the suppressor on this item
    return rng.random() < suppressed_accuracy(sigma, gap, prof)


def measure_curve(policy: str, sigmas: Sequence[float], samples: int, gap: float,
                  awareness: float, prof: Profile, rng: random.Random) -> List[float]:
    """Measured accuracy at each sigma from `samples` items (one 'noise seed' per sigma)."""
    curve = []
    for sigma in sigmas:
        correct = sum(1 for _ in range(samples)
                      if sample_item(policy, sigma, gap, awareness, prof, rng))
        curve.append(correct / samples)
    return curve


# ----------------------------------------------------------------------------
# Step 3 — detector statistic and decision
# ----------------------------------------------------------------------------

@dataclass
class Detection:
    max_rise: float        # max over sigma>0 of acc(sigma) - acc(0)
    peak_sigma: float      # sigma at which the max rise occurred
    violations: int        # count of i with acc(sigma_i) > acc(sigma_{i-1})

    def flagged(self, threshold: float) -> bool:
        return self.max_rise >= threshold


def detect(curve: Sequence[float], sigmas: Sequence[float]) -> Detection:
    """Anomalous-improvement statistic: how far above the unnoised score does any noised score climb?"""
    rises = [acc - curve[0] for acc in curve[1:]]
    best = max(range(len(rises)), key=lambda i: rises[i])
    violations = sum(1 for i in range(1, len(curve)) if curve[i] > curve[i - 1])
    return Detection(max_rise=rises[best], peak_sigma=sigmas[best + 1], violations=violations)


def run_trials(policy: str, sigmas: Sequence[float], samples: int, gap: float,
               awareness: float, prof: Profile, trials: int, seed: int) -> List[Detection]:
    """Independent trials with a derived RNG; the key only includes parameters the policy uses,
    so changing --awareness-rate leaves honest/sandbag results unchanged, and --gap leaves honest unchanged."""
    key = f"{seed}:{policy}:{samples}"
    if policy != "honest":
        key += f":{gap:.4f}"
    if policy == "aware":
        key += f":{awareness:.4f}"
    rng = random.Random(key)
    return [detect(measure_curve(policy, sigmas, samples, gap, awareness, prof, rng), sigmas)
            for _ in range(trials)]


def flag_rate(results: Sequence[Detection], threshold: float) -> float:
    return sum(1 for r in results if r.flagged(threshold)) / len(results)


def calibrate_threshold(honest: Sequence[Detection], fpr_budget: float) -> float:
    """Smallest tau at which at most `fpr_budget` of honest trials are flagged (empirical quantile)."""
    rises = sorted((r.max_rise for r in honest), reverse=True)
    allowed = int(fpr_budget * len(rises))
    return rises[allowed] + 1e-9 if allowed < len(rises) else rises[-1]


# ----------------------------------------------------------------------------
# Step 4 — report
# ----------------------------------------------------------------------------

def parse_sigmas(text: str) -> List[float]:
    sigmas = sorted({float(tok) for tok in text.split(",") if tok.strip()})
    if not sigmas or sigmas[0] != 0.0 or len(sigmas) < 3:
        raise ValueError("--sigmas must start at 0 and contain at least 3 values")
    return sigmas


def summarize(results: Sequence[Detection], threshold: float) -> Dict[str, float]:
    return {
        "flag_rate": flag_rate(results, threshold),
        "flagged": sum(1 for r in results if r.flagged(threshold)),
        "median_max_rise": statistics.median(r.max_rise for r in results),
        "median_violations": statistics.median(r.violations for r in results),
        "median_peak_sigma": statistics.median(r.peak_sigma for r in results),
    }


def print_expected_table(sigmas: Sequence[float], gap: float, awareness: float, prof: Profile) -> None:
    print(f"\nExpected (noise-free) accuracy by weight-noise sigma  "
          f"[base={prof.base:.2f} chance={prof.chance:.2f} gap={gap * 100:.0f} pts "
          f"awareness={awareness:.0%}]")
    print(f"  {'sigma':>6}  {'honest':>7}  {'sandbag':>7}  {'aware':>7}  {'p_break':>7}")
    for s in sigmas:
        row = [expected_accuracy(p, s, gap, awareness, prof) for p in POLICIES]
        print(f"  {s:>6.2f}  {row[0]:>7.3f}  {row[1]:>7.3f}  {row[2]:>7.3f}  "
              f"{break_probability(s, prof):>7.3f}")


def print_example_curves(sigmas: Sequence[float], samples: int, gap: float, awareness: float,
                         prof: Profile, seed: int, policies: Sequence[str], threshold: float) -> None:
    print(f"\nOne measured trial per policy (n={samples} items per sigma; '^' marks a rise over the previous sigma)")
    header = "  " + f"{'sigma':>6}" + "".join(f"  {p:>9}" for p in policies)
    print(header)
    curves = {}
    for p in policies:
        rng = random.Random(f"{seed}:example:{p}")
        curves[p] = measure_curve(p, sigmas, samples, gap, awareness, prof, rng)
    for i, s in enumerate(sigmas):
        cells = []
        for p in policies:
            mark = "^" if i > 0 and curves[p][i] > curves[p][i - 1] else " "
            cells.append(f"  {curves[p][i]:>8.3f}{mark}")
        print(f"  {s:>6.2f}" + "".join(cells))
    for p in policies:
        d = detect(curves[p], sigmas)
        verdict = "FLAG (halt + audit)" if d.flagged(threshold) else "pass"
        print(f"  {p:>8}: max rise {d.max_rise * 100:+.1f} pts at sigma={d.peak_sigma:.2f}, "
              f"{d.violations} monotonicity violations -> {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", type=int, default=200, help="Monte-Carlo trials per policy (default: %(default)s)")
    parser.add_argument("--samples", type=int, default=400, help="benchmark items per sigma (default: %(default)s)")
    parser.add_argument("--gap", type=float, default=0.15, help="sandbag suppression gap in accuracy (default: %(default)s)")
    parser.add_argument("--awareness-rate", type=float, default=0.5, help="P(test-detector fires) for the aware policy (default: %(default)s)")
    parser.add_argument("--threshold", type=float, default=0.05, help="flag if max rise >= this (default: %(default)s)")
    parser.add_argument("--sigmas", type=str, default=DEFAULT_SIGMAS, help="comma list of noise magnitudes, starting at 0")
    parser.add_argument("--policy", choices=POLICIES + ("all",), default="all", help="which policy to simulate (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write a JSON summary")
    args = parser.parse_args()

    if not 0.0 <= args.gap < 0.55 or not 0.0 <= args.awareness_rate <= 1.0:
        parser.error("--gap must be in [0, 0.55) and --awareness-rate in [0, 1]")
    sigmas = parse_sigmas(args.sigmas)
    prof = Profile()
    policies = list(POLICIES) if args.policy == "all" else [args.policy]
    gap_pts = args.gap * 100
    thr_pts = args.threshold * 100

    print("=" * 78)
    print("NOISE-INJECTION SANDBAGGING SCREEN (Phase 20, Lesson 20)")
    print("=" * 78)
    print(f"  sigmas={','.join(f'{s:g}' for s in sigmas)}  samples/sigma={args.samples}  "
          f"trials={args.trials}  seed={args.seed}")
    print(f"  sandbag gap={gap_pts:.0f} pts  awareness rate={args.awareness_rate:.0%}  "
          f"flag threshold: max rise >= {thr_pts:.1f} pts")

    print_expected_table(sigmas, args.gap, args.awareness_rate, prof)
    print_example_curves(sigmas, args.samples, args.gap, args.awareness_rate, prof,
                         args.seed, policies, args.threshold)

    # Monte-Carlo per policy
    results = {p: run_trials(p, sigmas, args.samples, args.gap, args.awareness_rate,
                             prof, args.trials, args.seed) for p in policies}
    summaries = {p: summarize(results[p], args.threshold) for p in policies}
    print(f"\nMonte-Carlo over {args.trials} trials per policy (threshold {thr_pts:.1f} pts)")
    print(f"  {'policy':>8}  {'flag rate':>10}  {'flagged':>8}  {'med max rise':>12}  "
          f"{'med viol.':>9}  {'med peak sigma':>14}")
    for p in policies:
        s = summaries[p]
        kind = "false positives" if p == "honest" else "detections"
        print(f"  {p:>8}  {s['flag_rate']:>10.1%}  {int(s['flagged']):>3}/{args.trials:<4}  "
              f"{s['median_max_rise'] * 100:>+11.1f}p  {s['median_violations']:>9.1f}  "
              f"{s['median_peak_sigma']:>14.2f}   <- {kind}")

    # ROC-like table over thresholds (needs honest + at least one sandbagging policy)
    roc_rows = []
    if "honest" in results and len(policies) > 1:
        print(f"\nROC-like table: flag rate by threshold (gap={gap_pts:.0f} pts, awareness={args.awareness_rate:.0%})")
        print("  " + f"{'tau (pts)':>9}" + "".join(f"  {p + ' rate':>13}" for p in policies))
        for tau in ROC_THRESHOLDS:
            rates = {p: flag_rate(results[p], tau) for p in policies}
            roc_rows.append({"threshold": tau, **rates})
            print(f"  {tau * 100:>9.1f}" + "".join(f"  {rates[p]:>13.1%}" for p in policies))

    # Gap sweep: at a fixed false-positive budget, how small a sandbag can this screen see,
    # and what does quadrupling the sample size buy? (tau is re-calibrated per sample size)
    sweep = []
    taus = {}
    if "sandbag" in policies:
        fpr_budget = 0.05
        big_n = 4 * args.samples
        big_trials = max(40, args.trials // 4)
        honest_n = results["honest"] if "honest" in results else run_trials(
            "honest", sigmas, args.samples, args.gap, 0.0, prof, args.trials, args.seed)
        honest_4n = run_trials("honest", sigmas, big_n, args.gap, 0.0, prof, 2 * big_trials, args.seed)
        taus = {"n": calibrate_threshold(honest_n, fpr_budget), "4n": calibrate_threshold(honest_4n, fpr_budget)}
        print(f"\nGap sweep for the sandbag policy at a {fpr_budget:.0%} false-positive budget: "
              f"tau calibrated on honest trials to {taus['n'] * 100:.1f} pts at n={args.samples} "
              f"and {taus['4n'] * 100:.1f} pts at n={big_n}")
        print(f"  {'gap (pts)':>9}  {'exp. peak rise':>14}  {'detect @n':>10}  {'detect @4n':>10}")
        for g in GAP_SWEEP:
            exp_curve = [expected_accuracy("sandbag", s, g, 1.0, prof) for s in sigmas]
            exp_rise = max(exp_curve[1:]) - exp_curve[0]
            at_n = flag_rate(run_trials("sandbag", sigmas, args.samples, g, 1.0, prof,
                                        args.trials, args.seed), taus["n"])
            at_4n = flag_rate(run_trials("sandbag", sigmas, big_n, g, 1.0, prof,
                                         big_trials, args.seed), taus["4n"])
            sweep.append({"gap": g, "expected_peak_rise": exp_rise, "detect_n": at_n, "detect_4n": at_4n})
            print(f"  {g * 100:>9.0f}  {exp_rise * 100:>+13.1f}p  {at_n:>10.1%}  {at_4n:>10.1%}")

    # HEADLINE — every sentence is built from the numbers above
    print()
    print("=" * 78)
    print("HEADLINE")
    print("-" * 78)
    if "honest" in summaries:
        h = summaries["honest"]
        print(f"  Honest model: accuracy only falls with noise (median max rise {h['median_max_rise'] * 100:+.1f} pts); "
              f"the screen false-flags it in {h['flag_rate']:.1%} of {args.trials} trials at tau={thr_pts:.1f} pts.")
    if "sandbag" in summaries:
        sb = summaries["sandbag"]
        fp_txt = f" at {summaries['honest']['flag_rate']:.1%} false positives" if "honest" in summaries else ""
        print(f"  A {gap_pts:.0f}-point sandbag is detected in {sb['flag_rate']:.1%} of trials{fp_txt} "
              f"(median peak at sigma={sb['median_peak_sigma']:.2f}, median rise {sb['median_max_rise'] * 100:+.1f} pts).")
    if sweep:
        small = sweep[0]
        print(f"  At a 5% false-positive budget a {small['gap'] * 100:.0f}-point sandbag is detected in only "
              f"{small['detect_n']:.1%} of trials at n={args.samples} (tau={taus['n'] * 100:.1f} pts) and "
              f"{small['detect_4n']:.1%} at n={4 * args.samples} (tau={taus['4n'] * 100:.1f} pts): "
              f"its expected peak rise is {small['expected_peak_rise'] * 100:+.1f} pts, near the noise floor.")
    if "aware" in summaries:
        aw = summaries["aware"]
        shown_gap = args.awareness_rate * gap_pts
        print(f"  Evaluation awareness at {args.awareness_rate:.0%} shrinks the gap the eval sees from "
              f"{gap_pts:.0f} to {shown_gap:.1f} pts and the detection rate to {aw['flag_rate']:.1%}; "
              f"a realistic environment (lower awareness) is a weaker sandbag but a harder screen.")
    print("  Pre-register the sigma grid and tau; treat any flag as a halting event, not a data point.")

    if args.out:
        payload = {
            "config": {"sigmas": sigmas, "samples": args.samples, "trials": args.trials, "gap": args.gap,
                       "awareness_rate": args.awareness_rate, "threshold": args.threshold,
                       "seed": args.seed, "profile": asdict(prof)},
            "summaries": summaries, "roc": roc_rows, "gap_sweep": sweep, "calibrated_tau": taus,
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
