"""Tests for the time-horizon estimator (Phase 20 · Lesson 13)."""

from __future__ import annotations

import math
import random
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as m  # noqa: E402


class TestLogisticFit(unittest.TestCase):
    def test_clean_fit_recovers_horizon_and_slope(self) -> None:
        tasks = m.generate_tasks(3000, 4.0, m.TRUE_SLOPE, 0.0, random.Random(5))
        fit = m.fit_logistic(tasks)
        self.assertLess(abs(math.log(fit.h50 / 4.0)), math.log(1.15), f"h50={fit.h50:.2f}")
        self.assertLess(abs(fit.slope - m.TRUE_SLOPE), 0.10, f"slope={fit.slope:.2f}")

    def test_fixed_slope_fit_pins_slope_and_orders_horizons(self) -> None:
        tasks = m.generate_tasks(400, 4.0, m.TRUE_SLOPE, 0.0, random.Random(9))
        fit = m.fit_logistic(tasks, fixed_slope=0.6)
        self.assertEqual(fit.slope, 0.6)
        self.assertLess(fit.h80, fit.h50)
        # h80 is the point where the fitted curve predicts 80%
        self.assertAlmostEqual(m.p_success(math.log(fit.h80), fit.log_h50, fit.slope), 0.8, places=9)
        self.assertAlmostEqual(m.horizon_at(fit.log_h50, fit.slope, 0.5), fit.h50, places=9)

    def test_bootstrap_ci_contains_truth_at_seed_11(self) -> None:
        tasks = m.generate_tasks(228, 16.0, m.TRUE_SLOPE, 0.0, random.Random(11))
        h50s, _ = m.bootstrap_horizons(tasks, 60, random.Random(12))
        lo, hi = m.ci(h50s)
        self.assertLessEqual(lo, 16.0)
        self.assertGreaterEqual(hi, 16.0)


class TestFailureModes(unittest.TestCase):
    def test_truncation_biases_suite_bounded_estimate_downward(self) -> None:
        for seed in (11, 3, 7, 23):
            clean = m.generate_tasks(228, 16.0, m.TRUE_SLOPE, 0.0, random.Random(seed))
            iso_trunc = m.isotonic_horizon(m.truncate(clean, 8.0))
            self.assertLessEqual(iso_trunc, 8.0)
            self.assertLess(iso_trunc, 0.75 * 16.0, f"seed {seed}: {iso_trunc:.2f}")

    def test_truncation_widens_logistic_ci(self) -> None:
        clean = m.generate_tasks(228, 16.0, m.TRUE_SLOPE, 0.0, random.Random(11))
        full, _ = m.bootstrap_horizons(clean, 60, random.Random(12))
        trunc, _ = m.bootstrap_horizons(m.truncate(clean, 8.0), 60, random.Random(12))
        width = lambda ci: ci[1] / ci[0]  # noqa: E731
        self.assertGreater(width(m.ci(trunc)), width(m.ci(full)))

    def test_time_noise_attenuates_slope(self) -> None:
        slopes = []
        for seed in range(100, 110):
            noisy = m.generate_tasks(228, 16.0, m.TRUE_SLOPE, 0.85, random.Random(seed))
            slopes.append(m.fit_logistic(noisy).slope)
        self.assertLess(statistics.median(slopes), m.TRUE_SLOPE)

    def test_isotonic_horizon_is_bounded_and_finds_a_clean_step(self) -> None:
        rng = random.Random(1)
        times = [math.exp(rng.uniform(math.log(m.MIN_TASK_HOURS), math.log(m.POP_MAX_HOURS))) for _ in range(300)]
        all_ok = [m.Task(t, t, True) for t in times]
        none_ok = [m.Task(t, t, False) for t in times]
        step = [m.Task(t, t, t < 2.0) for t in times]
        self.assertEqual(m.isotonic_horizon(all_ok), max(times))
        self.assertEqual(m.isotonic_horizon(none_ok), min(times))
        self.assertLess(abs(math.log(m.isotonic_horizon(step) / 2.0)), math.log(1.2))


class TestTrend(unittest.TestCase):
    def test_doubling_fit_recovers_exact_exponential(self) -> None:
        dates, horizons = m.synthetic_release_series(210.0, random.Random(0), noise=0.0)
        days, r2 = m.fit_doubling_time(dates, horizons)
        self.assertAlmostEqual(days, 210.0, places=6)
        self.assertAlmostEqual(r2, 1.0, places=9)

    def test_determinism(self) -> None:
        a = m.generate_tasks(50, 8.0, m.TRUE_SLOPE, 0.3, random.Random(42))
        b = m.generate_tasks(50, 8.0, m.TRUE_SLOPE, 0.3, random.Random(42))
        self.assertEqual(a, b)
        self.assertEqual(m.fit_logistic(a), m.fit_logistic(b))


if __name__ == "__main__":
    unittest.main()
