"""Tests for the trajectory integrity audit (Phase 20, Lesson 15)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as m  # noqa: E402


class TestTrajectoryIntegrity(unittest.TestCase):
    def test_honest_runs_produce_no_critical_findings(self) -> None:
        rng = random.Random(5)
        for idx in range(200):
            t = m.honest_trajectory(idx, rng)
            for structural in (False, True):
                severities = [f.severity for f in m.audit(t, structural)]
                self.assertNotIn("critical", severities, (idx, structural))
            # the structural audit never flags an honest run at all
            self.assertFalse(m.is_flagged(m.structural_findings(t)))

    def test_each_signature_is_caught_by_its_own_rule(self) -> None:
        for sig in m.SIGNATURES:
            rng = random.Random(1)
            t = m.tampered_trajectory(0, sig, False, rng)
            findings = m.rule_findings(t)
            self.assertIn(sig, {f.rule for f in findings}, sig)
            self.assertTrue(m.is_flagged(findings), sig)

    def test_adaptive_adversary_lowers_rule_recall_at_seed_11(self) -> None:
        grid = m.run_grid(400, 0.30, 11)
        static, adaptive = grid[(False, False)], grid[(True, False)]
        self.assertGreaterEqual(static.recall, 0.95)
        self.assertLess(adaptive.recall, static.recall)
        self.assertLess(adaptive.recall, 0.25)

    def test_structural_mode_restores_recall_against_adaptive_adversary(self) -> None:
        grid = m.run_grid(400, 0.30, 11)
        s = grid[(True, True)]
        self.assertGreaterEqual(s.recall, 0.95)
        self.assertGreaterEqual(s.precision, 0.95)
        for sig in m.SIGNATURES:
            self.assertGreaterEqual(s.sig_recall(sig), 0.95, sig)

    def test_invariant_structural_recall_never_below_rule_recall(self) -> None:
        for seed in (1, 2, 3):
            grid = m.run_grid(200, 0.30, seed)
            for adaptive in (False, True):
                self.assertGreaterEqual(grid[(adaptive, True)].recall, grid[(adaptive, False)].recall)

    def test_static_and_adaptive_datasets_share_the_same_partition(self) -> None:
        a = m.generate_dataset(300, 0.30, False, 11)
        b = m.generate_dataset(300, 0.30, True, 11)
        self.assertEqual([(t.tampered, t.signature) for t in a], [(t.tampered, t.signature) for t in b])

    def test_determinism(self) -> None:
        a = m.generate_dataset(120, 0.30, True, 7)
        b = m.generate_dataset(120, 0.30, True, 7)
        self.assertEqual(m.to_jsonl(a), m.to_jsonl(b))
        self.assertEqual(m.headline(m.run_grid(120, 0.30, 7)), m.headline(m.run_grid(120, 0.30, 7)))

    def test_json_lines_round_trip(self) -> None:
        data = m.generate_dataset(50, 0.50, True, 3)
        text = m.to_jsonl(data)
        back = m.from_jsonl(text)
        self.assertEqual(data, back)
        self.assertEqual(m.to_jsonl(back), text)

    def test_special_casing_is_outside_the_integrity_boundary(self) -> None:
        rng = random.Random(2)
        t = m.tampered_trajectory(0, m.OUTSIDE_BOUNDARY, False, rng)
        self.assertEqual(t.harness_result, "pass")
        self.assertFalse(m.is_flagged(m.rule_findings(t)))
        self.assertFalse(m.is_flagged(m.structural_findings(t)))


if __name__ == "__main__":
    unittest.main()
