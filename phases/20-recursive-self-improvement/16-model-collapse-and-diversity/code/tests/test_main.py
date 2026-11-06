"""Deterministic tests for the model-collapse simulator (stdlib unittest).

Run from code/:  python3 -m unittest discover tests -v
"""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as mc  # noqa: E402


SMALL = mc.Config(vocab=50, samples=400, generations=8, trials=20, cont_samples=10, seed=11)


class TruthAndMetricsTests(unittest.TestCase):
    def test_zipf_is_a_normalised_decreasing_distribution(self) -> None:
        probs = mc.zipf_distribution(200, 1.1)
        self.assertAlmostEqual(sum(probs), 1.0, places=12)
        self.assertTrue(all(a > b for a, b in zip(probs, probs[1:])))
        self.assertAlmostEqual(probs[0] / probs[1], 2 ** 1.1, places=9)

    def test_entropy_tv_and_distinct_have_the_textbook_values(self) -> None:
        uniform = [0.25] * 4
        self.assertAlmostEqual(mc.entropy_bits(uniform), 2.0, places=12)
        self.assertAlmostEqual(mc.entropy_bits([1.0, 0.0, 0.0]), 0.0, places=12)
        self.assertAlmostEqual(mc.total_variation(uniform, uniform), 0.0, places=12)
        self.assertAlmostEqual(mc.total_variation([1.0, 0.0], [0.0, 1.0]), 1.0, places=12)
        # pass@k algebra: a single certain category gives exactly one distinct outcome,
        # four equiprobable categories in 2 draws give 4 * (1 - 0.75^2) = 1.75
        self.assertAlmostEqual(mc.expected_distinct([1.0, 0.0], 5), 1.0, places=12)
        self.assertAlmostEqual(mc.expected_distinct(uniform, 2), 1.75, places=12)
        self.assertLessEqual(mc.expected_distinct(mc.zipf_distribution(200, 1.1), 100), 100.0)

    def test_fit_without_smoothing_keeps_zero_counts_at_zero(self) -> None:
        model = mc.fit([3, 0, 1])
        self.assertEqual(model, [0.75, 0.0, 0.25])
        smoothed = mc.fit([3, 0, 1], smoothing=1.0)
        self.assertGreater(smoothed[1], 0.0)
        self.assertAlmostEqual(sum(smoothed), 1.0, places=12)


class RecursiveLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = mc.Config()  # defaults, seed 11
        self.truth = mc.zipf_distribution(self.cfg.vocab, self.cfg.zipf)
        self.results = mc.run_all(self.cfg, list(mc.REGIMES))

    def test_replace_loses_entropy_and_never_resurrects_a_category(self) -> None:
        hist = self.results["replace"]
        self.assertLess(hist[-1].entropy, hist[0].entropy)
        self.assertLess(hist[-1].entropy, mc.entropy_bits(self.truth))
        extinct = [s.extinct for s in hist]
        self.assertEqual(extinct, sorted(extinct), "extinction is absorbing under replace")
        self.assertGreater(extinct[-1], extinct[0])

    def test_accumulate_is_closer_to_truth_than_replace(self) -> None:
        replace, accumulate = self.results["replace"][-1], self.results["accumulate"][-1]
        self.assertLess(accumulate.tv, replace.tv)
        self.assertGreater(accumulate.entropy, replace.entropy)
        self.assertLessEqual(accumulate.extinct, replace.extinct)
        # the real gen-0 sample never leaves the pool, so nothing present at gen 0 can go extinct
        self.assertEqual(accumulate.extinct, self.results["accumulate"][0].extinct)

    def test_mix_with_all_real_data_reproduces_truth_within_sampling_noise(self) -> None:
        cfg = mc.Config(real_fraction=1.0)
        hist = mc.run_all(cfg, ["mix"])["mix"]
        truth_h = mc.entropy_bits(self.truth)
        for stats in hist:
            self.assertLess(stats.tv, 0.15)
            self.assertLess(abs(stats.entropy - truth_h), 0.25)
        self.assertLess(abs(hist[-1].entropy - hist[0].entropy), 0.2)

    def test_single_regime_run_matches_the_all_regimes_run(self) -> None:
        solo = mc.run_all(self.cfg, ["accumulate"])["accumulate"]
        self.assertEqual(solo, self.results["accumulate"])


class TheoryTests(unittest.TestCase):
    def test_extinction_probability_matches_monte_carlo(self) -> None:
        p, n, trials = 0.001, 1000, 2000
        theory = mc.extinction_probability(p, n)
        self.assertAlmostEqual(theory, math.exp(-n * p), places=3)
        rng = random.Random(5)
        probs = [1.0 - p, p]
        dead = sum(1 for _ in range(trials) if mc.sample_counts(probs, n, rng)[1] == 0)
        self.assertLess(abs(dead / trials - theory), 0.04)

    def test_miller_madow_drop_scales_with_categories_and_samples(self) -> None:
        self.assertAlmostEqual(mc.miller_madow_drop_bits(1, 1000), 0.0, places=12)
        self.assertAlmostEqual(mc.miller_madow_drop_bits(201, 2000) / mc.miller_madow_drop_bits(101, 2000), 2.0, places=9)
        self.assertAlmostEqual(mc.miller_madow_drop_bits(101, 1000) / mc.miller_madow_drop_bits(101, 4000), 4.0, places=9)
        checks = mc.theory_checks(SMALL)
        self.assertLess(abs(checks["expected_extinct_theory"] - checks["expected_extinct_simulated"]), 3.0)
        self.assertGreater(checks["simulated_drop_bits"], 0.0)

    def test_gaussian_chain_shape_and_report_determinism(self) -> None:
        chain = mc.gaussian_chain(10, 6, random.Random(1))
        self.assertEqual(len(chain), 7)
        self.assertTrue(all(sd > 0.0 for sd in chain))
        a = mc.build_report(SMALL, list(mc.REGIMES))
        b = mc.build_report(SMALL, list(mc.REGIMES))
        self.assertEqual(a, b)
        c = mc.build_report(mc.Config(**{**SMALL.__dict__, "seed": 12}), list(mc.REGIMES))
        self.assertNotEqual(a["regimes"], c["regimes"])


if __name__ == "__main__":
    unittest.main()
