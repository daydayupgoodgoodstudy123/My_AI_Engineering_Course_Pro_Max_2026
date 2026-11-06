"""Tests for the discrete-cycle takeoff toy (Phase 20, Lesson 02)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import (  # noqa: E402
    BLOW_UP_RATE,
    NO_CEILING,
    OOM_PER_2024_YEAR,
    R_SIGMA_FOR_RANGE,
    Params,
    Trajectory,
    monte_carlo,
    simulate,
    step,
)

IDEAL = dict(ceiling_ooms=NO_CEILING, cycles=40)


class ReturnsTests(unittest.TestCase):
    def test_r_below_one_decelerates(self) -> None:
        t = simulate(Params(r=0.8, **IDEAL))
        self.assertTrue(all(b < a for a, b in zip(t.rate, t.rate[1:])))
        self.assertIsNone(t.rate_doubling_cycle())
        self.assertIsNotNone(t.rate_halving_cycle())

    def test_r_equal_one_is_flat_without_ceiling(self) -> None:
        t = simulate(Params(r=1.0, **IDEAL))
        for x in t.rate:
            self.assertAlmostEqual(x, t.rate[0], places=9)
        self.assertIsNone(t.rate_doubling_cycle())
        self.assertIsNone(t.rate_halving_cycle())

    def test_r_above_one_accelerates_and_blows_up(self) -> None:
        t = simulate(Params(r=1.2, **IDEAL))
        pre = [x for x in t.rate if x < BLOW_UP_RATE]           # before the float guard caps the step
        self.assertGreaterEqual(len(pre), 10)
        self.assertTrue(all(b > a for a, b in zip(pre, pre[1:])))
        self.assertTrue(all(b >= a for a, b in zip(t.rate, t.rate[1:])))
        self.assertIsNotNone(t.rate_doubling_cycle())
        self.assertGreater(t.final_ooms, 100.0)  # finite-time blow-up in the idealized toy


class CeilingTests(unittest.TestCase):
    def test_ceiling_caps_and_lower_ceiling_means_less(self) -> None:
        lo = simulate(Params(r=1.6, ceiling_ooms=10.0))
        hi = simulate(Params(r=1.6, ceiling_ooms=16.0))
        self.assertLessEqual(lo.final_ooms, 10.0 + 1e-9)
        self.assertLessEqual(hi.final_ooms, 16.0 + 1e-9)
        self.assertLess(lo.final_ooms, hi.final_ooms)
        self.assertIsNotNone(lo.ceiling_cycle())
        self.assertTrue(all(b >= a for a, b in zip(lo.log_s, lo.log_s[1:])))
        for log_s in (0.0, 5.0, 9.9):
            self.assertLessEqual(step(log_s, lo.p), 10.0 - log_s + 1e-12)

    def test_ceiling_damps_every_cycle_and_ends_amplification(self) -> None:
        t = simulate(Params(r=1.2, ceiling_ooms=10.0))
        twin = simulate(Params(r=1.2, ceiling_ooms=NO_CEILING))
        for a, b in zip(t.d_log, twin.d_log):
            self.assertLessEqual(a, b + 1e-12)
        self.assertEqual(t.r_ai_cross_cycle(), 1)
        self.assertIsNotNone(t.r_ai_drop_cycle())      # rising difficulty pulls R_AI back below 1
        self.assertIsNone(twin.r_ai_drop_cycle())


class RAITests(unittest.TestCase):
    def test_r_ai_equals_r_times_a_without_baseline_or_ceiling(self) -> None:
        for r, a in [(0.8, 1.0), (1.2, 1.0), (1.2, 0.5), (2.0, 0.7)]:
            t = simulate(Params(r=r, feedback=a, ceiling_ooms=NO_CEILING, cycles=10))
            for x in t.r_ai:
                self.assertAlmostEqual(x, r * a, places=9)

    def test_amplification_before_visible_acceleration(self) -> None:
        t = simulate(Params(r=1.2, baseline=1.0, ceiling_ooms=10.0))
        cross, dbl = t.r_ai_cross_cycle(), t.rate_doubling_cycle()
        self.assertIsNotNone(cross)
        self.assertIsNotNone(dbl)
        self.assertGreater(cross, 1)                    # the human baseline dilutes the feedback at first
        self.assertLess(cross, dbl)                     # R_AI >= 1 long before the rate visibly doubles
        self.assertLess(t.rate[cross - 1], t.rate[0])   # at the crossing the rate is still below its start
        self.assertIsNone(simulate(Params(r=0.8, baseline=1.0, ceiling_ooms=NO_CEILING)).r_ai_cross_cycle())


class WindowTests(unittest.TestCase):
    def test_window_years_counts_the_trailing_year(self) -> None:
        p = Params(cycle_months=3.0, cycles=5)
        t = Trajectory(p=p, log_s=[0, 1, 2, 3, 4, 5], d_log=[1.0] * 5, rate=[4.0] * 5, r_ai=[1.0] * 5)
        self.assertEqual(t.window_years(3), 0.0)
        self.assertAlmostEqual(t.window_years(4), 4.0 / OOM_PER_2024_YEAR)
        self.assertEqual(t.years_in_one_cycle(3.0), 4)
        self.assertAlmostEqual(t.max_window_years(), 4.0 / OOM_PER_2024_YEAR)


class MonteCarloTests(unittest.TestCase):
    def test_deterministic_by_seed(self) -> None:
        p = Params(cycles=20)
        a = monte_carlo(p, 200, 1.2, R_SIGMA_FOR_RANGE, 0.15, (6.0, 16.0), seed=5)
        b = monte_carlo(p, 200, 1.2, R_SIGMA_FOR_RANGE, 0.15, (6.0, 16.0), seed=5)
        c = monte_carlo(p, 200, 1.2, R_SIGMA_FOR_RANGE, 0.15, (6.0, 16.0), seed=6)
        self.assertEqual(a, b)
        self.assertNotEqual(a["median_r_drawn"], c["median_r_drawn"])
        self.assertGreaterEqual(a["p_three"], a["p_ten"])
        self.assertAlmostEqual(a["p_three"], a["n_three"] / 200)

    def test_ceiling_below_ten_forbids_ten_in_one(self) -> None:
        # a year's progress can never exceed the headroom, so 10 years-in-1 needs a ceiling above 10 OOMs
        mc = monte_carlo(Params(cycles=40), 300, 1.2, R_SIGMA_FOR_RANGE, 0.15, (6.0, 8.0), seed=1)
        self.assertEqual(mc["n_ten"], 0)
        self.assertEqual(mc["n_room_gt_10"], 0)
        self.assertLessEqual(mc["median_max_window_years"], 8.0 / OOM_PER_2024_YEAR)


if __name__ == "__main__":
    unittest.main()
