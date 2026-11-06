"""Discrete-cycle takeoff simulator — stdlib Python, a pedagogical toy.

Software level S (start 1.0) improves once per development cycle. Research input
E = b + S**a grows with S (automation feedback a); each unit of research buys less
as S grows (difficulty S**(1/r)); a ceiling in OOMs damps progress as it nears.
Progress is reported in "years of 2024 progress" (1 OOM) per calendar year, plus a
per-cycle R_AI-style ratio (feedback gain / difficulty growth) after Burtsev 2026.
Usage: python main.py [--r 0.8 1.0 1.2 1.6] [--baseline 1] [--ceiling-ooms 10] [--cycles 40] [--trials 2000] [--seed 20]
See docs/en.md. This is NOT the Forethought or Burtsev model; it is a toy.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Optional

DEFAULT_SEED = 20
OOM_PER_2024_YEAR = 1.0      # 1 "year of 2024 progress" := 1 OOM (effective compute grew ~10x/yr; D&H 2025 convention)
NO_CEILING = math.inf        # the idealized model: damping is exactly 1.0 forever
MAX_EXPONENT = 300.0         # guard for 10**x in float arithmetic
BLOW_UP_RATE = 1e6           # years-in-1 above this is printed as BLOW-UP
CEILING_HIT_FRACTION = 0.9   # "hit the ceiling" = used 90% of the headroom
R_SIGMA_FOR_RANGE = math.log(3.6 / 1.2) / 1.645   # ln-sigma giving 5–95% of 0.4–3.6 around a 1.2 median


@dataclass
class Params:
    r: float = 1.2               # returns to software R&D
    feedback: float = 1.0        # a: research input scales as S**a
    baseline: float = 0.0        # b: non-recursive (human) research input, relative to AI input at S=1
    ceiling_ooms: float = 10.0   # effective limit on software efficiency, OOMs above start
    cycles: int = 40             # development cycles to simulate
    cycle_months: float = 3.0    # wall-clock length of one cycle
    initial_speedup: float = 1.0 # years of 2024 progress per year at S=1 with baseline 0

    @property
    def cycle_years(self) -> float:
        return self.cycle_months / 12.0

    @property
    def k_per_cycle(self) -> float:
        """OOMs of progress in the first cycle when baseline = 0."""
        return self.initial_speedup * OOM_PER_2024_YEAR * self.cycle_years

    @property
    def window_cycles(self) -> int:
        """How many cycles make one calendar year (at least one)."""
        return max(1, round(12.0 / self.cycle_months))

    @property
    def criticality(self) -> float:
        """Asymptotic R_AI = r * a: the structural threshold, independent of S and of b."""
        return self.r * self.feedback


def pow10(x: float) -> float:
    return 10.0 ** min(x, MAX_EXPONENT)


def log_research_input(log_s: float, p: Params) -> float:
    """log10 E(S) with E = b + S**a and S = 10**log_s, computed stably in log space."""
    al = p.feedback * log_s
    if p.baseline <= 0.0:
        return al
    return al + math.log10(1.0 + p.baseline * 10.0 ** max(-al, -MAX_EXPONENT))


def research_input(log_s: float, p: Params) -> float:
    """E(S) = b + S**a. b = 0 is a fully recursive loop (all research input scales with S)."""
    return pow10(log_research_input(log_s, p))


def difficulty(log_s: float, p: Params) -> float:
    """Diminishing returns: the next OOM costs S**(1/r) times as much research as the first."""
    return pow10(log_s / p.r)


def damping(log_s: float, p: Params) -> float:
    """Fraction of headroom left; progress is scaled by it (logistic in log space). 1.0 if no ceiling."""
    if math.isinf(p.ceiling_ooms):
        return 1.0
    return max(0.0, 1.0 - log_s / p.ceiling_ooms)


def step(log_s: float, p: Params, shock: float = 1.0) -> float:
    """OOMs gained in one cycle: k * shock * E(S) / S**(1/r) * damping, never overshooting the ceiling."""
    damp = damping(log_s, p)
    if damp <= 0.0:
        return 0.0
    log_raw = (math.log10(p.k_per_cycle * shock) + log_research_input(log_s, p)
               - log_s / p.r + math.log10(damp))
    return max(0.0, min(pow10(log_raw), p.ceiling_ooms - log_s))


def r_ai_ratio(log_s0: float, log_s1: float, p: Params) -> float:
    """Feedback gain carried into the next cycle divided by growth of difficulty.

    gain       = log10 E(S1) - log10 E(S0)             how much more research the next cycle gets
    difficulty = (L1 - L0)/r + log10(damp0/damp1)      how much harder the next OOM got, ceiling included
    With b = 0 and no ceiling effect this is exactly r * a (Params.criticality).
    """
    d_log = log_s1 - log_s0
    if d_log <= 0.0:
        return 0.0
    gain = log_research_input(log_s1, p) - log_research_input(log_s0, p)
    damp0, damp1 = damping(log_s0, p), damping(log_s1, p)
    if damp1 <= 0.0:
        return 0.0
    diff = d_log / p.r + math.log10(damp0 / damp1)
    return gain / diff if diff > 0 else 0.0


@dataclass
class Trajectory:
    p: Params
    log_s: list[float] = field(default_factory=list)   # len cycles + 1, OOMs above start
    d_log: list[float] = field(default_factory=list)   # len cycles
    rate: list[float] = field(default_factory=list)    # years of 2024 progress per year, per cycle
    r_ai: list[float] = field(default_factory=list)    # per cycle

    @property
    def final_ooms(self) -> float:
        return self.log_s[-1]

    def ooms_at(self, cycle: int) -> float:
        return self.log_s[min(cycle, len(self.log_s) - 1)]

    def rate_doubling_cycle(self) -> Optional[int]:
        return first_cycle(self.rate, lambda x: x >= 2.0 * self.rate[0] - 1e-12)

    def rate_halving_cycle(self) -> Optional[int]:
        return first_cycle(self.rate, lambda x: x <= 0.5 * self.rate[0] + 1e-12)

    def ceiling_cycle(self) -> Optional[int]:
        target = CEILING_HIT_FRACTION * self.p.ceiling_ooms
        return first_cycle(self.log_s[1:], lambda x: x >= target - 1e-12)

    def r_ai_cross_cycle(self) -> Optional[int]:
        return first_cycle(self.r_ai, lambda x: x >= 1.0)

    def r_ai_drop_cycle(self) -> Optional[int]:
        cross = self.r_ai_cross_cycle()
        if cross is None:
            return None
        idx = first_cycle(self.r_ai[cross:], lambda x: x < 1.0)
        return None if idx is None else cross + idx

    def window_years(self, end_cycle: int) -> float:
        """Years of 2024 progress achieved in the calendar year ending at end_cycle."""
        w = self.p.window_cycles
        if end_cycle < w:
            return 0.0
        return sum(self.d_log[end_cycle - w:end_cycle]) / OOM_PER_2024_YEAR

    def max_window_years(self) -> float:
        return max((self.window_years(n) for n in range(1, len(self.d_log) + 1)), default=0.0)

    def years_in_one_cycle(self, threshold: float) -> Optional[int]:
        """First cycle at the end of which the trailing year holds >= threshold years of progress."""
        for n in range(1, len(self.d_log) + 1):
            if self.window_years(n) >= threshold:
                return n
        return None


def first_cycle(values: list[float], pred: Callable[[float], bool]) -> Optional[int]:
    for i, v in enumerate(values):
        if pred(v):
            return i + 1
    return None


def simulate(p: Params, shocks: Optional[list[float]] = None) -> Trajectory:
    """Run the discrete loop. shocks[n] multiplies cycle n's progress (1.0 = no noise)."""
    t = Trajectory(p=p, log_s=[0.0])
    log_s = 0.0
    for n in range(p.cycles):
        d = step(log_s, p, shocks[n] if shocks is not None else 1.0)
        new_log_s = log_s + d
        t.d_log.append(d)
        t.rate.append(d / (p.cycle_years * OOM_PER_2024_YEAR))
        t.r_ai.append(r_ai_ratio(log_s, new_log_s, p))
        log_s = new_log_s
        t.log_s.append(log_s)
    return t


def scenario_summary(t: Trajectory) -> dict:
    p = t.p
    return {
        "r": p.r, "baseline": p.baseline, "ceiling_ooms": p.ceiling_ooms, "criticality": p.criticality,
        "rate_first": t.rate[0], "rate_last": t.rate[-1],
        "rate_peak": max(t.rate), "rate_peak_cycle": t.rate.index(max(t.rate)) + 1,
        "final_ooms": t.final_ooms,
        "rate_doubling_cycle": t.rate_doubling_cycle(), "rate_halving_cycle": t.rate_halving_cycle(),
        "three_in_one_cycle": t.years_in_one_cycle(3.0), "ten_in_one_cycle": t.years_in_one_cycle(10.0),
        "max_window_years": t.max_window_years(), "ceiling_cycle": t.ceiling_cycle(),
        "r_ai_first": t.r_ai[0], "r_ai_cross_cycle": t.r_ai_cross_cycle(), "r_ai_drop_cycle": t.r_ai_drop_cycle(),
    }


def monte_carlo(p: Params, trials: int, r_median: float, r_sigma: float, noise: float,
                ceiling_range: tuple[float, float], seed: int) -> dict:
    """r ~ log-normal(median r_median, ln-sigma r_sigma); ceiling ~ Uniform(range); per-cycle log-normal shocks."""
    rng = random.Random(seed)
    max_years: list[float] = []
    rs: list[float] = []
    three = ten = ten_with_room = room_gt_10 = ceiling_hit = supercritical = 0
    for _ in range(trials):
        r = math.exp(rng.gauss(math.log(r_median), r_sigma))
        ceiling = rng.uniform(*ceiling_range)
        shocks = [math.exp(rng.gauss(0.0, noise)) for _ in range(p.cycles)] if noise > 0 else None
        t = simulate(replace(p, r=r, ceiling_ooms=ceiling), shocks)
        m = t.max_window_years()
        max_years.append(m)
        rs.append(r)
        three += m >= 3.0
        ten += m >= 10.0
        room_gt_10 += ceiling > 10.0
        ten_with_room += (m >= 10.0) and (ceiling > 10.0)
        ceiling_hit += t.ceiling_cycle() is not None
        supercritical += r * p.feedback > 1.0
    rs_sorted = sorted(rs)
    return {
        "trials": trials, "horizon_years": p.cycles * p.cycle_years,
        "r_median_param": r_median, "r_sigma": r_sigma, "ceiling_range": list(ceiling_range),
        "r_5pct": rs_sorted[int(0.05 * trials)], "r_95pct": rs_sorted[min(trials - 1, int(0.95 * trials))],
        "median_r_drawn": statistics.median(rs),
        "p_supercritical": supercritical / trials,
        "n_three": three, "p_three": three / trials,
        "n_ten": ten, "p_ten": ten / trials,
        "p_ten_given_room_gt_10": (ten_with_room / room_gt_10) if room_gt_10 else 0.0,
        "n_room_gt_10": room_gt_10,
        "n_ceiling": ceiling_hit, "p_ceiling": ceiling_hit / trials,
        "median_max_window_years": statistics.median(max_years),
    }


def fmt_cycle(c: Optional[int]) -> str:
    return "never" if c is None else f"c{c}"


def fmt_rate(x: float) -> str:
    return "BLOW-UP" if x > BLOW_UP_RATE else f"{x:.2f}"


def fmt_ooms(x: float) -> str:
    return "BLOW-UP" if x > BLOW_UP_RATE else f"{x:.2f}"


def print_scenario(t: Trajectory, twin: Trajectory) -> None:
    p = t.p
    print(f"\n  r = {p.r:.2f}   a = {p.feedback:.2f}   b = {p.baseline:.1f}   r*a = {p.criticality:.2f}"
          f"   ceiling = {p.ceiling_ooms:.0f} OOMs   cycle = {p.cycle_months:.0f} months")
    print(f"  {'cycle':>5}  {'OOMs':>7}  {'yrs/yr':>7}  {'no-ceiling':>10}  {'R_AI':>6}  {'damp':>5}")
    stride = max(1, p.cycles // 8)
    for n in range(1, p.cycles + 1):
        if n == 1 or n == p.cycles or n % stride == 0:
            print(f"  {n:>5}  {fmt_ooms(t.log_s[n]):>7}  {fmt_rate(t.rate[n-1]):>7}  {fmt_rate(twin.rate[n-1]):>10}"
                  f"  {t.r_ai[n-1]:>6.2f}  {damping(t.log_s[n-1], p):>5.2f}")
    s = scenario_summary(t)
    print(f"  -> rate {s['rate_first']:.2f} -> {fmt_rate(s['rate_last'])} yrs/yr (peak {fmt_rate(s['rate_peak'])} at c{s['rate_peak_cycle']});"
          f" doubles {fmt_cycle(s['rate_doubling_cycle'])}; halves {fmt_cycle(s['rate_halving_cycle'])};"
          f" no-ceiling twin: doubles {fmt_cycle(twin.rate_doubling_cycle())}, 3-in-1 {fmt_cycle(twin.years_in_one_cycle(3.0))}")
    print(f"  -> 3 years-in-1 {fmt_cycle(s['three_in_one_cycle'])}; 10 years-in-1 {fmt_cycle(s['ten_in_one_cycle'])};"
          f" ceiling (90%) {fmt_cycle(s['ceiling_cycle'])}; R_AI>=1 from {fmt_cycle(s['r_ai_cross_cycle'])},"
          f" back <1 {fmt_cycle(s['r_ai_drop_cycle'])}")


def run_scenarios(base: Params, rs: list[float]) -> list[dict]:
    print("\n" + "=" * 78)
    print("A. RETURNS TO SOFTWARE R&D — scenarios without noise (no-ceiling twin alongside)")
    print("=" * 78)
    out = []
    for r in rs:
        t = simulate(replace(base, r=r))
        twin = simulate(replace(base, r=r, ceiling_ooms=NO_CEILING))
        print_scenario(t, twin)
        s = scenario_summary(t)
        s["twin_rate_doubling_cycle"] = twin.rate_doubling_cycle()
        s["twin_three_in_one_cycle"] = twin.years_in_one_cycle(3.0)
        s["twin_rate_last"] = twin.rate[-1]
        out.append(s)
    return out


def run_baseline_contrast(base: Params, baselines: list[float]) -> list[dict]:
    print("\n" + "=" * 78)
    print(f"B. BASELINE PRODUCTIVITY vs CRITICALITY — r = {base.r:.2f}, a = {base.feedback:.2f}, b varied")
    print("=" * 78)
    print(f"  {'b':>4}  {'rate c1':>7}  {'OOMs@c8':>7}  {'OOMs@end':>8}  {'R_AI c1':>7}  {'R_AI>=1':>7}"
          f"  {'rate@cross':>10}  {'doubles':>7}  {'3-in-1':>6}  {'lag':>4}")
    out = []
    for b in baselines:
        t = simulate(replace(base, baseline=b))
        s = scenario_summary(t)
        cross, dbl = s["r_ai_cross_cycle"], s["rate_doubling_cycle"]
        rate_at_cross = t.rate[cross - 1] / t.rate[0] if cross else float("nan")
        lag = (dbl - cross) if (cross and dbl) else None
        print(f"  {b:>4.1f}  {t.rate[0]:>7.2f}  {t.ooms_at(8):>7.2f}  {t.final_ooms:>8.2f}  {t.r_ai[0]:>7.2f}"
              f"  {fmt_cycle(cross):>7}  {rate_at_cross:>9.2f}x  {fmt_cycle(dbl):>7}  {fmt_cycle(s['three_in_one_cycle']):>6}"
              f"  {('-' if lag is None else str(lag)):>4}")
        s.update({"rate_at_cross_vs_first": rate_at_cross, "lag_cycles": lag, "ooms_at_8": t.ooms_at(8)})
        out.append(s)
    print("  (rate@cross = progress rate when R_AI first reaches 1, relative to cycle 1;"
          " lag = cycles from R_AI>=1 to the visible rate doubling)")
    return out


def run_cycle_contrast(base: Params, months_list: list[float]) -> list[dict]:
    print("\n" + "=" * 78)
    print(f"C. CYCLE DURATION AS THE CLOCK — r = {base.r:.2f}, same yearly start, same {base.cycles * base.cycle_years:.0f}-year horizon")
    print("=" * 78)
    horizon_years = base.cycles * base.cycle_years
    print(f"  {'months':>6}  {'cycles':>6}  {'OOMs@end':>8}  {'3-in-1 (yr)':>11}  {'ceiling (yr)':>12}")
    out = []
    for m in months_list:
        cycles = max(1, round(horizon_years * 12.0 / m))
        t = simulate(replace(base, cycle_months=m, cycles=cycles))
        c3, cc = t.years_in_one_cycle(3.0), t.ceiling_cycle()
        yr3 = None if c3 is None else c3 * m / 12.0
        yrc = None if cc is None else cc * m / 12.0
        print(f"  {m:>6.0f}  {cycles:>6}  {t.final_ooms:>8.2f}  {('never' if yr3 is None else f'{yr3:.1f}'):>11}"
              f"  {('never' if yrc is None else f'{yrc:.1f}'):>12}")
        out.append({"cycle_months": m, "cycles": cycles, "final_ooms": t.final_ooms,
                    "three_in_one_year": yr3, "ceiling_year": yrc})
    return out


def print_monte_carlo(mc: dict) -> None:
    lo, hi = mc["ceiling_range"]
    print("\n" + "=" * 78)
    print("D. MONTE-CARLO — log-normal r, uniform ceiling, per-cycle noise")
    print("=" * 78)
    print(f"  trials {mc['trials']}, horizon {mc['horizon_years']:.1f} years, r median {mc['r_median_param']:.2f}"
          f" (drawn 5–95%: {mc['r_5pct']:.2f}–{mc['r_95pct']:.2f}), ceiling U({lo:.0f}, {hi:.0f}) OOMs")
    print(f"  P(r*a > 1: loop supercritical)          {mc['p_supercritical']:.1%}")
    print(f"  P(>3 years-in-1 within horizon)         {mc['p_three']:.1%}  ({mc['n_three']}/{mc['trials']})")
    print(f"  P(>10 years-in-1 within horizon)        {mc['p_ten']:.1%}  ({mc['n_ten']}/{mc['trials']})")
    print(f"  P(>10 years-in-1 | ceiling > 10 OOMs)   {mc['p_ten_given_room_gt_10']:.1%}  (of {mc['n_room_gt_10']} such trials)")
    print(f"  P(reach 90% of ceiling within horizon)  {mc['p_ceiling']:.1%}  ({mc['n_ceiling']}/{mc['trials']})")
    print(f"  median best-year progress               {mc['median_max_window_years']:.2f} years-in-1")


def headline(scen: list[dict], contrast: list[dict], cyc: list[dict], mc: dict, p: Params) -> list[str]:
    lines = []
    for s in sorted(scen, key=lambda s: s["r"]):
        c = s["criticality"]
        if c < 1.0 - 1e-9:
            verdict = (f"subcritical (r*a={c:.2f}): rate {s['rate_first']:.2f} -> {s['rate_last']:.2f} yrs/yr even without a"
                       f" ceiling ({fmt_rate(s['twin_rate_last'])}); halves {fmt_cycle(s['rate_halving_cycle'])}")
        elif abs(c - 1.0) <= 1e-9 and math.isinf(s["ceiling_ooms"]):
            verdict = f"knife edge (r*a=1): with no ceiling the rate stays at {s['rate_last']:.2f} yrs/yr for all {p.cycles} cycles"
        elif abs(c - 1.0) <= 1e-9:
            verdict = (f"knife edge (r*a=1): no-ceiling twin stays at {s['twin_rate_last']:.2f} yrs/yr; with a"
                       f" {s['ceiling_ooms']:.0f}-OOM ceiling the rate drifts to {s['rate_last']:.2f}")
        else:
            verdict = (f"supercritical (r*a={c:.2f}): doubles {fmt_cycle(s['rate_doubling_cycle'])}, 3-in-1"
                       f" {fmt_cycle(s['three_in_one_cycle'])}, peak {fmt_rate(s['rate_peak'])} yrs/yr, ceiling {fmt_cycle(s['ceiling_cycle'])};"
                       f" no-ceiling twin 3-in-1 {fmt_cycle(s['twin_three_in_one_cycle'])}")
        lines.append(f"r={s['r']:.1f} {verdict}.")
    lo, hi = mc["ceiling_range"]
    lines.append(f"Monte-Carlo ({mc['trials']} trials, {mc['horizon_years']:.0f}-yr horizon, ceiling U({lo:.0f},{hi:.0f})):"
                 f" P(>3 years-in-1)={mc['p_three']:.1%}, P(>10 years-in-1)={mc['p_ten']:.1%}"
                 f" ({mc['p_ten_given_room_gt_10']:.1%} when the ceiling is >10 OOMs away), P(r*a>1)={mc['p_supercritical']:.1%}.")
    with_b = [c for c in contrast if c["baseline"] > 0 and c["r_ai_cross_cycle"] and c["rate_doubling_cycle"]]
    if with_b:
        c = with_b[0]
        lines.append(f"Baseline b={c['baseline']:.0f}: R_AI crosses 1 at {fmt_cycle(c['r_ai_cross_cycle'])} while the rate is"
                     f" {c['rate_at_cross_vs_first']:.2f}x its start; the visible doubling comes {c['lag_cycles']} cycles later.")
    b0 = [c for c in contrast if c["baseline"] == 0]
    bmax = max(contrast, key=lambda c: c["baseline"])
    if b0 and bmax["baseline"] > 0:
        lines.append(f"Baseline raises OOMs at c8 from {b0[0]['ooms_at_8']:.2f} (b=0) to {bmax['ooms_at_8']:.2f} (b={bmax['baseline']:.0f})"
                     f" while asymptotic R_AI stays r*a={p.criticality:.2f}: productivity sets speed, structure sets criticality.")
    with_ceiling = [c for c in cyc if c["ceiling_year"] is not None]
    if len(with_ceiling) >= 2:
        fast = min(with_ceiling, key=lambda c: c["cycle_months"])
        slow = max(with_ceiling, key=lambda c: c["cycle_months"])
        f3 = "never" if fast["three_in_one_year"] is None else f"{fast['three_in_one_year']:.1f} yr"
        s3 = "never" if slow["three_in_one_year"] is None else f"{slow['three_in_one_year']:.1f} yr"
        lines.append(f"Cycle length {fast['cycle_months']:.0f} vs {slow['cycle_months']:.0f} months at the same yearly start:"
                     f" 3-in-1 at {f3} vs {s3}, ceiling at {fast['ceiling_year']:.1f} vs {slow['ceiling_year']:.1f} years"
                     f" — the cycle is the clock.")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--r", type=float, nargs="+", default=[0.8, 1.0, 1.2, 1.6],
                        help="returns-to-software-R&D scenarios (default: %(default)s)")
    parser.add_argument("--feedback", type=float, default=1.0, help="automation feedback exponent a (default: %(default)s)")
    parser.add_argument("--baseline", type=float, default=0.0,
                        help="non-recursive research input b, relative to AI input at S=1 (default: %(default)s)")
    parser.add_argument("--ceiling-ooms", type=float, default=10.0, help="headroom to effective limits for sections A-C, OOMs (default: %(default)s)")
    parser.add_argument("--ceiling-range", type=float, nargs=2, default=[6.0, 16.0], metavar=("LO", "HI"),
                        help="Monte-Carlo ceiling drawn uniformly from this range, OOMs (default: %(default)s)")
    parser.add_argument("--cycles", type=int, default=40, help="development cycles (default: %(default)s)")
    parser.add_argument("--cycle-months", type=float, default=3.0, help="months per cycle (default: %(default)s)")
    parser.add_argument("--initial-speedup", type=float, default=1.0,
                        help="years of 2024 progress per year at S=1 with baseline 0 (default: %(default)s)")
    parser.add_argument("--r-median", type=float, default=1.2, help="Monte-Carlo log-normal median of r (default: %(default)s)")
    parser.add_argument("--r-sigma", type=float, default=R_SIGMA_FOR_RANGE,
                        help="Monte-Carlo ln-sigma of r (default %(default).3f gives 5-95%% of 0.4-3.6)")
    parser.add_argument("--noise", type=float, default=0.15, help="per-cycle log-normal sigma on progress (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=2000, help="Monte-Carlo trials (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write a JSON summary")
    args = parser.parse_args()
    if args.ceiling_ooms <= 0 or min(args.ceiling_range) <= 0 or math.isinf(min(args.ceiling_range)):
        parser.error("ceilings must be positive and the Monte-Carlo range finite (use --ceiling-ooms inf for the idealized model)")
    if args.initial_speedup <= 0 or args.cycles < 1 or args.trials < 1 or args.r_median <= 0 or min(args.r) <= 0:
        parser.error("--initial-speedup, --r, --r-median must be > 0; --cycles and --trials must be >= 1")

    base = Params(r=args.r_median, feedback=args.feedback, baseline=args.baseline, ceiling_ooms=args.ceiling_ooms,
                  cycles=args.cycles, cycle_months=args.cycle_months, initial_speedup=args.initial_speedup)

    print("=" * 78)
    print("THE MATH OF TAKEOFF — discrete-cycle toy (Phase 20, Lesson 02)")
    print("=" * 78)
    print(f"  1 year of 2024 progress := {OOM_PER_2024_YEAR:.0f} OOM of software efficiency;"
          f" start at {base.initial_speedup:.1f} yrs/yr; {base.cycles} cycles x {base.cycle_months:.0f} months"
          f" = {base.cycles * base.cycle_years:.1f} years")
    print("  per cycle: dlog10 S = k * (b + S^a) / S^(1/r) * (1 - OOMs/ceiling)      [toy — not Forethought's or Burtsev's model]")

    scen = run_scenarios(base, args.r)
    contrast = run_baseline_contrast(base, [0.0, 1.0, 3.0])
    cyc = run_cycle_contrast(base, [1.0, 3.0, 12.0])
    mc = monte_carlo(base, args.trials, args.r_median, args.r_sigma, args.noise, tuple(args.ceiling_range), args.seed)
    print_monte_carlo(mc)

    print("\n" + "=" * 78)
    print("HEADLINE (generated from the numbers above)")
    print("-" * 78)
    for line in headline(scen, contrast, cyc, mc, base):
        print("  " + line)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"params": asdict(base), "scenarios": scen, "baseline_contrast": contrast,
                       "cycle_contrast": cyc, "monte_carlo": mc}, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
