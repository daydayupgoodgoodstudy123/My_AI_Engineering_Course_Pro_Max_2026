"""Deterministic tests for the generate -> filter -> train simulator (Phase 20, Lesson 05)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def run(kind: str, seed: int = 20, iterations: int = 6, samples: int = 2000, **kw) -> main.LoopResult:
    spec_kwargs = {k: v for k, v in kw.items() if k in ("fp_rate", "fn_rate", "fp_bias", "tau", "conf_signal")}
    loop_kwargs = {k: v for k, v in kw.items() if k in ("temperature", "human_mix")}
    spec = main.FilterSpec(kind, **spec_kwargs)
    return main.run_loop(spec, iterations, samples, seed, **loop_kwargs)


class TaskFamilyTests(unittest.TestCase):
    def test_strategy_validity_matches_puzzle_family(self) -> None:
        """A cleanly executed shortcut is right on ~40% of puzzles, the general method on ~90%."""
        rng = random.Random(1)
        n = 20_000
        b_right = a_right = 0
        for _ in range(n):
            pz = main.make_puzzle(rng)
            b_right += (sum(pz.numbers) % 10) == pz.answer()   # the shortcut ignores the clause
            a_right += not pz.obscure                          # the method only fails on obscure clauses
        self.assertAlmostEqual(b_right / n, main.strategy_validity("B"), delta=0.02)
        self.assertAlmostEqual(a_right / n, main.strategy_validity("A"), delta=0.02)
        self.assertAlmostEqual(main.strategy_validity("A"), 0.9, places=9)
        self.assertAlmostEqual(main.strategy_validity("B"), 0.4, places=9)


class LoopBehaviourTests(unittest.TestCase):
    def test_oracle_filter_improves_accuracy_and_removes_shortcut(self) -> None:
        res = run("oracle")
        self.assertGreater(res.last.accuracy, res.first.accuracy + 0.25)
        self.assertLess(res.last.share_b, 0.05)
        self.assertGreater(res.last.skill_a, 0.95)
        self.assertEqual(res.mean_wrong_share(), 0.0)
        # saturation: an answer-match filter cannot push past the general method's validity
        self.assertLessEqual(res.last.accuracy, main.strategy_validity("A") + 0.03)

    def test_noisy_filter_is_slower_and_contaminated_at_fixed_seed(self) -> None:
        oracle = run("oracle", iterations=3)
        noisy = run("noisy", iterations=3, fp_rate=0.3, fn_rate=0.1)
        self.assertLess(noisy.last.accuracy, oracle.last.accuracy)
        self.assertGreater(noisy.last.share_b, oracle.last.share_b)
        self.assertGreater(noisy.mean_wrong_share(), 0.08)

    def test_fp_rate_above_tpr_reverses_the_loop(self) -> None:
        """A symmetric filter with FP > TPR is anti-informative: the shortcut grows, accuracy falls."""
        res = run("noisy", iterations=8, fp_rate=0.95, fn_rate=0.1)
        self.assertGreater(res.last.share_b, res.first.share_b)
        self.assertLess(res.last.accuracy, res.first.accuracy)

    def test_self_assessment_with_weak_confidence_degenerates(self) -> None:
        res = run("self", tau=0.6, conf_signal=0.0)
        self.assertGreater(res.last.share_b, 0.9)
        self.assertLess(res.last.accuracy, res.first.accuracy - 0.1)
        self.assertGreater(res.mean_wrong_share(), 0.4)

    def test_strong_confidence_signal_rescues_self_assessment(self) -> None:
        kappa = main.conf_signal_threshold(0.6)
        self.assertIsNotNone(kappa)
        res = run("self", tau=0.6, conf_signal=kappa + 0.15)
        self.assertLess(res.last.share_b, 0.1)
        self.assertGreater(res.last.accuracy, res.first.accuracy + 0.2)


class AnalyticConditionTests(unittest.TestCase):
    def test_growth_condition_thresholds(self) -> None:
        c_a = main.expected_correctness("A", main.INITIAL_SKILL)
        c_b = main.expected_correctness("B", main.INITIAL_SKILL)
        pw_b = main.INITIAL_SKILL * (1 - main.strategy_validity("B"))
        informative = main.FilterSpec("noisy", fp_rate=0.3, fn_rate=0.1)
        anti = main.FilterSpec("noisy", fp_rate=0.95, fn_rate=0.1)
        self.assertFalse(main.shortcut_grows(informative.analytic_acceptance("A", c_a, 0.0),
                                             informative.analytic_acceptance("B", c_b, pw_b)))
        self.assertTrue(main.shortcut_grows(anti.analytic_acceptance("A", c_a, 0.0),
                                            anti.analytic_acceptance("B", c_b, pw_b)))
        # closed form: b* = (TPR - q)(c_A - c_B) / pw_B = 0.6 * 0.4 / 0.48
        self.assertAlmostEqual(main.fp_bias_threshold(0.3, 0.1), 0.5, places=9)
        at_threshold = main.FilterSpec("noisy", fp_rate=0.3, fn_rate=0.1, fp_bias=0.5)
        self.assertAlmostEqual(at_threshold.analytic_acceptance("A", c_a, 0.0),
                               at_threshold.analytic_acceptance("B", c_b, pw_b), places=9)

    def test_analytic_sign_matches_simulation_on_default_filters(self) -> None:
        total_ok = total = 0
        for kind, kw in (("oracle", {}), ("noisy", {"fp_rate": 0.3, "fn_rate": 0.1}),
                         ("self", {"tau": 0.6, "conf_signal": 0.03})):
            ok, n = run(kind, iterations=8, **kw).sign_matches()
            total_ok += ok
            total += n
        self.assertGreaterEqual(total, 20)
        self.assertEqual(total_ok, total)

    def test_temperature_fixed_point_matches_simulation(self) -> None:
        a_a = main.expected_correctness("A", 1.0)
        a_b = main.expected_correctness("B", 1.0)
        predicted = main.temperature_fixed_point(a_a, a_b, 1.5)
        self.assertIsNotNone(predicted)
        res = run("oracle", iterations=12, temperature=1.5)
        self.assertAlmostEqual(res.last.share_b, predicted, delta=0.04)
        self.assertIsNone(main.temperature_fixed_point(a_a, a_b, 1.0))


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_records(self) -> None:
        first = run("noisy", seed=5, iterations=4, fp_rate=0.3, fn_rate=0.1)
        second = run("noisy", seed=5, iterations=4, fp_rate=0.3, fn_rate=0.1)
        self.assertEqual(first.records, second.records)
        other = run("noisy", seed=6, iterations=4, fp_rate=0.3, fn_rate=0.1)
        self.assertNotEqual(first.records, other.records)

    def test_entropy_and_shares_stay_in_bounds(self) -> None:
        for kind in ("oracle", "noisy", "self"):
            for r in run(kind, iterations=5).records:
                self.assertGreaterEqual(r.entropy_bits, 0.0)
                self.assertLessEqual(r.entropy_bits, 1.0 + 1e-9)
                self.assertTrue(0.0 <= r.share_b <= 1.0)
                self.assertTrue(0.0 <= r.wrong_accepted_share <= 1.0)


if __name__ == "__main__":
    unittest.main()
