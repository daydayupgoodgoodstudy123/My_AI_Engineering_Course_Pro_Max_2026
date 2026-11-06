"""Time-horizon estimator — stdlib Python.

Simulates a METR-style measurement: tasks with human completion times from
1 minute to 32 hours, an agent whose success probability follows a latent
logistic in log(time) with a true 50% horizon h, and the analysis pipeline
(maximum-likelihood logistic fit, 50%/80% horizons, bootstrap CIs). It then
shows three failure modes of the measurement — suite truncation, noisy human
times, and fit choice — and extrapolates a doubling trend from a model series.
Usage: python main.py [--tasks N] [--true-horizon H] [--max-task-hours M]
                      [--bootstrap B] [--time-noise S] [--seed K]
See docs/en.md (Phase 20 · Lesson 13).
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from dataclasses import dataclass

DEFAULT_SEED = 11
MIN_TASK_HOURS = 1.0 / 60.0  # one minute
POP_MAX_HOURS = 32.0  # the longest task the suite could contain
TRUE_SLOPE = 0.6  # latent logistic slope per natural-log hour
SEARCH_MAX_HOURS = 1024.0  # the fitter may extrapolate this far
WORK_MONTH_HOURS = 167.0  # 40 h/week x 4.33 weeks
REPLICATES = 20  # replicate noisy suites in section C
GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


@dataclass(frozen=True)
class Task:
    """One task: true human time, the time the suite recorded, and the outcome."""

    true_hours: float
    recorded_hours: float
    success: bool

    @property
    def log_hours(self) -> float:
        return math.log(self.recorded_hours)


@dataclass(frozen=True)
class Fit:
    """A fitted curve P(success) = sigmoid(slope * (log h50 - log t))."""

    log_h50: float
    slope: float
    log_likelihood: float

    @property
    def h50(self) -> float:
        return math.exp(self.log_h50)

    @property
    def h80(self) -> float:
        # P = 0.8  <=>  slope * (log h50 - log t) = logit(0.8) = ln 4
        return math.exp(self.log_h50 - math.log(4.0) / self.slope)


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def p_success(log_hours: float, log_h50: float, slope: float) -> float:
    """Latent model: longer tasks fail more often; h50 is the 50% point."""
    return sigmoid(slope * (log_h50 - log_hours))


def horizon_at(log_h50: float, slope: float, p: float) -> float:
    """Task length (hours) at which the curve predicts success probability p."""
    return math.exp(log_h50 - math.log(p / (1.0 - p)) / slope)


def generate_tasks(n: int, true_horizon: float, slope: float,
                   time_noise: float, rng: random.Random) -> list[Task]:
    """Tasks log-uniform in [1 min, 32 h]; recorded times carry log-normal noise."""
    lo, hi = math.log(MIN_TASK_HOURS), math.log(POP_MAX_HOURS)
    log_h50 = math.log(true_horizon)
    tasks: list[Task] = []
    for _ in range(n):
        log_t = rng.uniform(lo, hi)
        ok = rng.random() < p_success(log_t, log_h50, slope)
        jitter = rng.gauss(0.0, time_noise) if time_noise > 0 else 0.0
        tasks.append(Task(math.exp(log_t), math.exp(log_t + jitter), ok))
    return tasks


def truncate(tasks: list[Task], max_hours: float) -> list[Task]:
    """Drop tasks whose recorded human time exceeds the suite's ceiling."""
    return [t for t in tasks if t.recorded_hours <= max_hours]


def log_likelihood(log_hours: list[float], outcomes: list[bool],
                   log_h50: float, slope: float) -> float:
    ll = 0.0
    for lt, ok in zip(log_hours, outcomes):
        p = min(max(p_success(lt, log_h50, slope), 1e-9), 1.0 - 1e-9)
        ll += math.log(p) if ok else math.log(1.0 - p)
    return ll


def _golden_max(f, lo: float, hi: float, tol: float) -> tuple[float, float]:
    """Golden-section search for the maximum of a unimodal function on [lo, hi]."""
    a, b = lo, hi
    c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    fc, fd = f(c), f(d)
    while b - a > tol:
        if fc < fd:
            a, c, fc = c, d, fd
            d = a + GOLDEN * (b - a)
            fd = f(d)
        else:
            b, d, fd = d, c, fc
            c = b - GOLDEN * (b - a)
            fc = f(c)
    x = (a + b) / 2.0
    return x, f(x)


def fit_logistic(tasks: list[Task], fixed_slope: float | None = None) -> Fit:
    """Maximum likelihood by profile likelihood (no numpy).

    For a fixed slope the log-likelihood is concave in log h50, so a 1-D golden
    search finds the profile maximum. With a free slope we search a geometric
    slope grid, then refine the best slope by a second golden search.
    fixed_slope mimics METR-style shared-slope fitting; None is the free fit.
    """
    log_hours = [t.log_hours for t in tasks]
    outcomes = [t.success for t in tasks]
    lo, hi = math.log(MIN_TASK_HOURS), math.log(SEARCH_MAX_HOURS)

    def profile(slope: float) -> tuple[float, float]:
        return _golden_max(lambda lh: log_likelihood(log_hours, outcomes, lh, slope), lo, hi, 1e-3)

    if fixed_slope is not None:
        lh, ll = profile(fixed_slope)
        return Fit(lh, fixed_slope, ll)

    grid = [0.1 * 1.3 ** k for k in range(14)]  # 0.10 .. 3.0 per ln-hour
    best_slope, best_ll = grid[0], -math.inf
    for s in grid:
        _, ll = profile(s)
        if ll > best_ll:
            best_slope, best_ll = s, ll
    s_lo, s_hi = best_slope / 1.3, best_slope * 1.3
    log_slope, _ = _golden_max(lambda ls: profile(math.exp(ls))[1], math.log(s_lo), math.log(s_hi), 5e-3)
    slope = math.exp(log_slope)
    lh, ll = profile(slope)
    return Fit(lh, slope, ll)


def isotonic_horizon(tasks: list[Task], target: float = 0.5) -> float:
    """Suite-bounded non-parametric estimator (METR's isotonic alternative).

    Fit a non-increasing step function of success vs log time by the pool-
    adjacent-violators algorithm, then return the task length where it first
    drops below `target` (geometric mean of the two tasks at that boundary).
    If the curve never drops below target the longest task in the suite is
    returned, so the estimate can never exceed the suite's ceiling.
    """
    ordered = sorted(tasks, key=lambda t: t.recorded_hours)
    # pools: [sum, count, first_index, last_index]; enforce non-increasing means
    pools: list[list[float]] = []
    for i, t in enumerate(ordered):
        pools.append([float(t.success), 1.0, i, i])
        while len(pools) > 1 and pools[-2][0] / pools[-2][1] < pools[-1][0] / pools[-1][1]:
            b = pools.pop()
            a = pools[-1]
            a[0] += b[0]
            a[1] += b[1]
            a[3] = b[3]
    for k, pool in enumerate(pools):
        if pool[0] / pool[1] < target:
            if k == 0:
                return ordered[0].recorded_hours
            left = ordered[int(pools[k - 1][3])].recorded_hours
            right = ordered[int(pool[2])].recorded_hours
            return math.sqrt(left * right)
    return ordered[-1].recorded_hours


def bootstrap_horizons(tasks: list[Task], resamples: int, rng: random.Random,
                       fixed_slope: float | None = None) -> tuple[list[float], list[float]]:
    """Resample tasks with replacement; return sorted lists of h50 and h80 estimates."""
    h50s, h80s = [], []
    n = len(tasks)
    for _ in range(resamples):
        sample = [tasks[rng.randrange(n)] for _ in range(n)]
        f = fit_logistic(sample, fixed_slope)
        h50s.append(f.h50)
        h80s.append(f.h80)
    return sorted(h50s), sorted(h80s)


def percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return math.nan
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def ci(sorted_vals: list[float]) -> tuple[float, float]:
    return percentile(sorted_vals, 0.025), percentile(sorted_vals, 0.975)


def fit_doubling_time(dates_years: list[float], horizons_hours: list[float]) -> tuple[float, float]:
    """Least-squares line of log2(horizon) vs date -> (doubling time in days, r^2)."""
    n = len(dates_years)
    xs, ys = dates_years, [math.log2(h) for h in horizons_hours]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx  # doublings per year
    intercept = my - slope * mx
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return 365.25 / slope, r2


def synthetic_release_series(true_doubling_days: float, rng: random.Random,
                             start_hours: float = 2.0 / 60.0, points: int = 13,
                             noise: float = 0.35) -> tuple[list[float], list[float]]:
    """Half-yearly releases from mid-2019; horizon doubles every true_doubling_days,
    each measurement carrying multiplicative log-normal noise (CI-like scatter)."""
    dates = [2019.5 + 0.5 * k for k in range(points)]
    horizons = []
    for d in dates:
        exact = start_hours * 2.0 ** ((d - dates[0]) * 365.25 / true_doubling_days)
        horizons.append(exact * math.exp(rng.gauss(0.0, noise)) if noise > 0 else exact)
    return dates, horizons


def fmt_hours(h: float) -> str:
    if h != h or h <= 0:  # nan or non-positive
        return "    n/a   "
    if h < 1.0:
        return f"{h * 60:7.1f} min"
    return f"{h:7.2f} h  "


def describe_suite(tasks: list[Task]) -> str:
    n_ok = sum(t.success for t in tasks)
    longest = max(t.recorded_hours for t in tasks)
    return (f"{len(tasks):>4} tasks, {n_ok:>4} solved ({n_ok / len(tasks):.1%}), "
            f"longest recorded {longest:6.2f} h")


def report_fit(label: str, fit: Fit, h50_ci: tuple[float, float] | None = None,
               h80_ci: tuple[float, float] | None = None) -> None:
    line = f"  {label:<32} h50={fmt_hours(fit.h50)}  h80={fmt_hours(fit.h80)}  slope={fit.slope:5.2f}"
    if h50_ci and h80_ci:
        line += (f"  h50 CI [{fmt_hours(h50_ci[0]).strip()}, {fmt_hours(h50_ci[1]).strip()}]"
                 f"  h80 CI [{fmt_hours(h80_ci[0]).strip()}, {fmt_hours(h80_ci[1]).strip()}]")
    print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", type=int, default=228,
                        help="number of tasks in the full suite (default: %(default)s)")
    parser.add_argument("--true-horizon", type=float, default=16.0,
                        help="latent 50%% horizon in hours (default: %(default)s)")
    parser.add_argument("--max-task-hours", type=float, default=8.0,
                        help="ceiling of the truncated suite in the contrast run (default: %(default)s)")
    parser.add_argument("--bootstrap", type=int, default=120,
                        help="bootstrap resamples per suite (default: %(default)s)")
    parser.add_argument("--time-noise", type=float, default=0.85,
                        help="log-normal sigma on recorded human times (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="RNG seed (default: %(default)s)")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    true_h80 = horizon_at(math.log(args.true_horizon), TRUE_SLOPE, 0.8)

    print("=" * 100)
    print("TIME-HORIZON ESTIMATOR (Phase 20, Lesson 13)")
    print("=" * 100)
    print(f"  latent model: P(success) = sigmoid({TRUE_SLOPE} * (log h50 - log t)),"
          f"  true h50 = {args.true_horizon:.2f} h, true h80 = {true_h80:.2f} h")
    print(f"  suite: {args.tasks} tasks, log-uniform in [1 min, {POP_MAX_HOURS:.0f} h];  seed {args.seed}")

    # ---- A. clean measurement on the full suite -------------------------------
    clean = generate_tasks(args.tasks, args.true_horizon, TRUE_SLOPE, 0.0, rng)
    fit_a = fit_logistic(clean)
    b50, b80 = bootstrap_horizons(clean, args.bootstrap, random.Random(args.seed + 1))
    ci50_a, ci80_a = ci(b50), ci(b80)
    iso_a = isotonic_horizon(clean)
    print("\nA. Clean suite (exact human times, full 1 min .. 32 h range)")
    print("  " + describe_suite(clean))
    report_fit("free-slope MLE", fit_a, ci50_a, ci80_a)
    n_long = sum(1 for t in clean if t.recorded_hours > fit_a.h50)
    tail = sorted(clean, key=lambda t: t.recorded_hours)[-20:]
    tail_rate = sum(t.success for t in tail) / len(tail)
    print(f"  {'isotonic (PAVA) h50':<32} h50={fmt_hours(iso_a)}  (bounded by the suite)")
    print(f"  {'identifiability':<32} {n_long} tasks ({n_long / len(clean):.1%}) longer than fitted h50; "
          f"success on the 20 longest tasks {tail_rate:.1%}")
    width50_a, width80_a = ci50_a[1] / ci50_a[0], ci80_a[1] / ci80_a[0]
    print(f"  {'95% CI width (upper/lower)':<32} h50 x{width50_a:4.1f}   h80 x{width80_a:4.1f}"
          f"   ({args.bootstrap} resamples)")

    # ---- B. truncation: drop tasks above the suite ceiling ---------------------
    trunc = truncate(clean, args.max_task_hours)
    fit_b = fit_logistic(trunc)
    fit_b_fixed = fit_logistic(trunc, fixed_slope=TRUE_SLOPE)
    t50, t80 = bootstrap_horizons(trunc, args.bootstrap, random.Random(args.seed + 1))
    ci50_b, ci80_b = ci(t50), ci(t80)
    iso_b = isotonic_horizon(trunc)
    print(f"\nB. Truncated suite (same tasks, drop those longer than {args.max_task_hours:.0f} h)")
    print("  " + describe_suite(trunc))
    report_fit("free-slope MLE", fit_b, ci50_b, ci80_b)
    report_fit(f"fixed-slope MLE (slope={TRUE_SLOPE})", fit_b_fixed)
    print(f"  {'isotonic (PAVA) h50':<32} h50={fmt_hours(iso_b)}  (cannot exceed {args.max_task_hours:.0f} h)")
    width50_b = ci50_b[1] / ci50_b[0]
    print(f"  {'95% CI width (upper/lower)':<32} h50 x{width50_b:4.1f}   h80 x{ci80_b[1] / ci80_b[0]:4.1f}")
    bias_iso = iso_b / args.true_horizon - 1.0

    # ---- C. noisy human times ---------------------------------------------------
    noisy = generate_tasks(args.tasks, args.true_horizon, TRUE_SLOPE, args.time_noise,
                           random.Random(args.seed + 2))
    fit_c = fit_logistic(noisy)
    fit_c_fixed = fit_logistic(noisy, fixed_slope=TRUE_SLOPE)
    within3 = sum(1 for t in noisy if abs(math.log(t.recorded_hours / t.true_hours)) <= math.log(3.0))
    print(f"\nC. Noisy human times (log-normal sigma={args.time_noise}; "
          f"{within3 / len(noisy):.1%} of recorded times within 3x of truth)")
    print("  " + describe_suite(noisy))
    report_fit("free-slope MLE", fit_c)
    report_fit(f"fixed-slope MLE (slope={TRUE_SLOPE})", fit_c_fixed)
    slope_shrink = fit_c.slope / TRUE_SLOPE - 1.0
    rep_slopes, rep_h50 = [], []
    for k in range(REPLICATES):
        rep = generate_tasks(args.tasks, args.true_horizon, TRUE_SLOPE, args.time_noise,
                             random.Random(args.seed + 100 + k))
        f = fit_logistic(rep)
        rep_slopes.append(f.slope)
        rep_h50.append(f.h50)
    med_slope, med_h50 = statistics.median(rep_slopes), statistics.median(rep_h50)
    n_over = sum(1 for h in rep_h50 if h > args.true_horizon)
    print(f"  {f'{REPLICATES} replicate noisy suites':<32} median slope {med_slope:4.2f} (true {TRUE_SLOPE}),"
          f"  median h50 {med_h50:5.2f} h (true {args.true_horizon:.2f}),"
          f"  h50 above truth in {n_over}/{REPLICATES} ({n_over / REPLICATES:.1%})")

    # ---- D. fit choice on the same clean data ----------------------------------
    fit_d_true = fit_logistic(clean, fixed_slope=TRUE_SLOPE)
    fit_d_shallow = fit_logistic(clean, fixed_slope=TRUE_SLOPE * 0.5)
    fit_d_steep = fit_logistic(clean, fixed_slope=TRUE_SLOPE * 2.0)
    print("\nD. Fit choice on the clean suite (same data, different modelling assumptions)")
    report_fit("free slope", fit_a)
    report_fit(f"fixed slope = {TRUE_SLOPE} (true)", fit_d_true)
    report_fit(f"fixed slope = {TRUE_SLOPE * 0.5:.2f} (too shallow)", fit_d_shallow)
    report_fit(f"fixed slope = {TRUE_SLOPE * 2.0:.2f} (too steep)", fit_d_steep)
    fits_d = [fit_a, fit_d_true, fit_d_shallow, fit_d_steep]
    spread50 = max(f.h50 for f in fits_d) / min(f.h50 for f in fits_d)
    spread80 = max(f.h80 for f in fits_d) / min(f.h80 for f in fits_d)

    # ---- E. doubling trend from a model series ----------------------------------
    true_doubling = 210.0
    dates, horizons = synthetic_release_series(true_doubling, random.Random(args.seed + 3))
    dbl, r2 = fit_doubling_time(dates, horizons)
    dbl_recent, _ = fit_doubling_time(dates[-5:], horizons[-5:])
    print(f"\nE. Doubling trend (synthetic half-yearly releases, true doubling {true_doubling:.0f} days)")
    print(f"  {'date':>8}  {'horizon':>12}")
    for d, h in zip(dates, horizons):
        if abs(d - round(d)) < 1e-9:
            print(f"  {d:8.1f}  {fmt_hours(h):>12}")
    print(f"  all {len(dates)} points:  doubling {dbl:6.1f} days (r^2 {r2:.3f})")
    print(f"  last 5 points:   doubling {dbl_recent:6.1f} days")
    months_to_month_task = math.log2(WORK_MONTH_HOURS / horizons[-1]) * dbl / 30.44

    # ---- HEADLINE ----------------------------------------------------------------
    print("\n" + "=" * 100)
    print("HEADLINE")
    print("-" * 100)
    print(f"  Clean fit: h50 {fit_a.h50:.1f} h vs true {args.true_horizon:.1f} h; "
          f"95% CI spans x{width50_a:.1f} for h50 and x{width80_a:.1f} for h80.")
    print(f"  Truncating at {args.max_task_hours:.0f} h: isotonic h50 goes from {iso_a:.1f} h (full suite) to "
          f"{iso_b:.1f} h ({bias_iso:+.1%} vs true {args.true_horizon:.0f} h); the logistic extrapolates to "
          f"{fit_b.h50:.1f} h but its CI widens from x{width50_a:.1f} to x{width50_b:.1f}.")
    print(f"  Time noise sigma {args.time_noise}: fitted slope {slope_shrink:+.1%}, "
          f"h50 {fit_c.h50:.1f} h (true {args.true_horizon:.1f}); across {REPLICATES} replicates median slope "
          f"{med_slope:.2f}, median h50 {med_h50:.1f} h, above truth {n_over}/{REPLICATES}.")
    print(f"  Same clean data, four slope assumptions: h50 varies x{spread50:.2f}, h80 varies x{spread80:.2f}.")
    print(f"  Doubling fit: {dbl:.0f} days on {len(dates)} points vs {dbl_recent:.0f} on the last 5 "
          f"(true {true_doubling:.0f}); at {dbl:.0f} days a {WORK_MONTH_HOURS:.0f} h task is "
          f"{months_to_month_task:.0f} months out.")


if __name__ == "__main__":
    main()
