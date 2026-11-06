"""Deterministic tests for the evaluator-integrity simulator (Phase 20, Lesson 14)."""

from __future__ import annotations

import random
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as m  # noqa: E402


class TestEvaluatorIntegrity(unittest.TestCase):
    def test_gap_is_zero_without_leakage(self) -> None:
        for regime in m.REGIMES:
            res = m.run_loop(m.LoopConfig(regime=regime, leak_rate=0.0), seed=11)
            self.assertTrue(all(r.gap == 0.0 for r in res.records), regime)
            self.assertTrue(all(r.memo_frac == 0.0 for r in res.records), regime)
            self.assertIsNone(res.oracle_halt, regime)
            self.assertIsNone(res.observed_halt, regime)

    def test_static_gap_grows_in_expectation_at_seed_11(self) -> None:
        res = m.run_loop(m.LoopConfig(regime="static"), seed=11)
        gaps = [r.gap for r in res.records]
        windows = [statistics.mean(gaps[i:i + 5]) for i in range(0, 20, 5)]
        self.assertEqual(windows, sorted(windows))
        self.assertLess(windows[0], windows[-1])
        # elitism + noise-free scores: the best measured score can never decrease
        measured = [r.measured for r in res.records]
        self.assertEqual(measured, sorted(measured))
        self.assertGreater(gaps[-1], 0.2)
        self.assertIsNotNone(res.oracle_halt)

    def test_rotating_gap_smaller_than_static(self) -> None:
        for seed in (11, 3, 7):
            static = m.run_loop(m.LoopConfig(regime="static"), seed)
            rotating = m.run_loop(m.LoopConfig(regime="rotating"), seed)
            self.assertLess(rotating.max_gap, static.max_gap, seed)
            self.assertLess(statistics.mean(r.gap for r in rotating.records),
                            statistics.mean(r.gap for r in static.records), seed)
            self.assertGreaterEqual(rotating.final.true, static.final.true, seed)

    def test_anchor_drift_computed_correctly(self) -> None:
        cfg = m.LoopConfig(regime="anchor")
        items = m.selection_items(cfg, 0)
        anchors = m.anchor_items(cfg)
        rng = random.Random(0)
        cand = m.Candidate(0.5, frozenset(items[:10]))
        measured = m.measured_score(cand, items, rng)
        self.assertAlmostEqual(measured, (10 + 0.5 * 30) / 40)
        anchor = m.measured_score(cand, anchors, rng)
        self.assertAlmostEqual(anchor, 0.5)
        self.assertAlmostEqual(m.anchor_drift(measured, anchor), measured - cand.quality)
        # a leaked anchor under-reports the gap
        leaky = m.Candidate(0.5, frozenset(items[:10]) | frozenset(anchors[:20]))
        leaky_drift = m.anchor_drift(m.measured_score(leaky, items, rng),
                                     m.measured_score(leaky, anchors, rng))
        self.assertLess(leaky_drift, measured - 0.5)
        # in a run with no eval noise, drift equals the oracle gap and anchors are never memorised
        res = m.run_loop(cfg, 11)
        for r in res.records:
            self.assertIsNotNone(r.drift)
            self.assertAlmostEqual(r.drift, r.gap)
        for c in res.final_population:
            self.assertFalse(c.memo & frozenset(anchors))

    def test_halting_rule_fires_after_exact_consecutive_exceedances(self) -> None:
        series = [0.2, 0.2, 0.1, 0.2, 0.2, 0.2, 0.2]
        self.assertEqual(m.halt_cycle(series, 0.15, 3), 6)
        self.assertEqual(m.halt_cycle(series, 0.15, 2), 2)
        self.assertEqual(m.halt_cycle(series, 0.15, 4), 7)
        self.assertIsNone(m.halt_cycle(series, 0.15, 5))
        self.assertIsNone(m.halt_cycle([0.15, 0.15, 0.15], 0.15, 1))  # strict >
        self.assertEqual(m.halt_cycle([0.0, 0.3], 0.15, 1), 2)
        self.assertEqual(m.halt_cycle([0.3, 0.3], 0.15, 2, first_cycle=10), 11)

    def test_determinism(self) -> None:
        a = m.run_loop(m.LoopConfig(regime="anchor"), 11)
        b = m.run_loop(m.LoopConfig(regime="anchor"), 11)
        self.assertEqual(a.records, b.records)
        self.assertEqual(a.oracle_halt, b.oracle_halt)
        c = m.run_loop(m.LoopConfig(regime="anchor"), 12)
        self.assertNotEqual(a.records, c.records)

    def test_selection_items_rotation_and_wrap(self) -> None:
        static = m.LoopConfig(regime="static")
        self.assertEqual(m.selection_items(static, 0), m.selection_items(static, 29))
        rot = m.LoopConfig(regime="rotating", rotate_every=5)
        self.assertEqual(m.selection_items(rot, 0), m.selection_items(rot, 4))
        self.assertTrue(set(m.selection_items(rot, 0)).isdisjoint(m.selection_items(rot, 5)))
        self.assertTrue(set(m.selection_items(rot, 0)).isdisjoint(m.anchor_items(rot)))
        wrap = m.LoopConfig(regime="rotating", rotate_every=5, pool_blocks=2)
        self.assertEqual(m.selection_items(wrap, 0), m.selection_items(wrap, 10))
        self.assertNotEqual(m.selection_items(wrap, 0), m.selection_items(wrap, 5))

    def test_anchor_over_static_set_makes_the_halt_observable(self) -> None:
        anchored = m.run_loop(m.LoopConfig(regime="anchor", rotate_every=0), 11)
        static = m.run_loop(m.LoopConfig(regime="static"), 11)
        self.assertIsNotNone(anchored.observed_halt)
        self.assertEqual(anchored.observed_halt, static.oracle_halt)
        self.assertEqual([r.measured for r in anchored.records],
                         [r.measured for r in static.records])


if __name__ == "__main__":
    unittest.main()
