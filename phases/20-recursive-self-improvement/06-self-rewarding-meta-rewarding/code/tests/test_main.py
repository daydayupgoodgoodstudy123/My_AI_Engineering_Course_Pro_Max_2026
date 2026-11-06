"""Deterministic tests for the actor/judge co-training simulator (Phase 20 · Lesson 06)."""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


class CoreFunctions(unittest.TestCase):
    def test_update_is_distribution_and_moves_toward_winner(self) -> None:
        probs = main.uniform_probs()
        wins = [10, 2, 2, 2, 2, 2]
        losses = [0, 4, 4, 4, 4, 4]
        shown = [10, 6, 6, 6, 6, 6]
        new = main.dpo_like_update(probs, wins, losses, shown, lr=0.6)
        self.assertAlmostEqual(sum(new), 1.0, places=9)
        self.assertTrue(all(p >= 0 for p in new))
        self.assertGreater(new[0], probs[0])
        self.assertTrue(all(new[k] < probs[k] for k in range(1, main.K)))

    def test_audit_estimator_recovers_length_bias(self) -> None:
        rng = random.Random(123)
        audit = main.make_audit_set(400, rng, label_noise=0.0)
        judge = main.Judge(length_bias=0.6, noise=0.0)
        beta_hat, agree, count, n_pairs = main.audit_judge(judge, audit, rng)
        self.assertAlmostEqual(beta_hat, 0.6, delta=0.02)
        self.assertEqual(n_pairs, 200)
        self.assertEqual(count, round(agree * n_pairs))
        unbiased = main.Judge(length_bias=0.0, noise=0.0)
        _, agree_clean, _, _ = main.audit_judge(unbiased, audit, rng)
        self.assertEqual(agree_clean, 1.0)

    def test_entropy_bits_bounds(self) -> None:
        self.assertEqual(main.entropy_bits([0, 0, 0]), 0.0)
        self.assertEqual(main.entropy_bits([5, 0, 0]), 0.0)
        self.assertAlmostEqual(main.entropy_bits([1] * main.K), math.log2(main.K), places=9)


class RegimeInvariants(unittest.TestCase):
    def test_zero_length_bias_both_regimes_raise_true_quality(self) -> None:
        cfg = main.Config(iterations=12, length_bias=0.0)
        for regime in ("frozen", "meta"):
            hist = main.run_regime(regime, cfg, seed=main.DEFAULT_SEED)
            self.assertGreater(hist[-1].true_quality, hist[0].true_quality + 0.05, regime)
            self.assertLess(hist[-1].mean_length, hist[0].mean_length, regime)

    def test_strong_bias_frozen_judge_stalls_quality_while_length_grows(self) -> None:
        cfg = main.Config(iterations=12, length_bias=0.8)
        hist = main.run_regime("frozen", cfg, seed=main.DEFAULT_SEED)
        self.assertLessEqual(hist[-1].true_quality, hist[0].true_quality + 0.01)
        self.assertGreater(hist[-1].mean_length, hist[0].mean_length * 1.3)
        self.assertGreater(hist[-1].inflation, hist[0].inflation)

    def test_meta_regime_beats_frozen_at_same_seed(self) -> None:
        cfg = main.Config()
        for seed in (main.DEFAULT_SEED, 3, 11):
            frozen = main.run_regime("frozen", cfg, seed=seed)
            meta = main.run_regime("meta", cfg, seed=seed)
            self.assertGreater(meta[-1].true_quality, frozen[-1].true_quality, seed)
            self.assertLess(abs(meta[-1].length_bias), abs(frozen[-1].length_bias), seed)

    def test_determinism_same_seed_same_history(self) -> None:
        cfg = main.Config()
        a = main.run_regime("meta", cfg, seed=5)
        b = main.run_regime("meta", cfg, seed=5)
        self.assertEqual(a, b)
        c = main.run_regime("meta", cfg, seed=6)
        self.assertNotEqual(a, c)

    def test_agreement_and_entropy_metrics_are_bounded(self) -> None:
        cfg = main.Config(iterations=6, pairs=50, audit_size=10)
        for regime in ("frozen", "meta"):
            for h in main.run_regime(regime, cfg, seed=2):
                self.assertTrue(0.0 <= h.agree_train <= 1.0)
                self.assertTrue(0.0 <= h.agree_audit <= 1.0)
                self.assertTrue(0.0 <= h.win_entropy <= math.log2(main.K) + 1e-9)
                self.assertAlmostEqual(sum(h.probs), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
