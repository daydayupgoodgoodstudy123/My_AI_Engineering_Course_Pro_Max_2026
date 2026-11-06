"""Deterministic tests for the objective-drift simulator (Phase 20 · Lesson 17)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as m  # noqa: E402

FAST = m.Config(edits=120, trials=6, probe_size=16)


class VectorHelpers(unittest.TestCase):
    def test_project_to_cone_geometry(self) -> None:
        rng = random.Random(0)
        anchor = m.random_unit(rng, 16)
        outside = m.state_at_cosine(anchor, 0.5, rng)
        projected = m.project_to_cone(outside, anchor, 0.9)
        self.assertAlmostEqual(m.dot(projected, projected), 1.0, places=9)
        self.assertAlmostEqual(m.dot(projected, anchor), 0.9, places=9)
        inside = m.state_at_cosine(anchor, 0.95, rng)
        self.assertEqual(m.project_to_cone(inside, anchor, 0.9), inside)

    def test_probe_threshold_calibration(self) -> None:
        self.assertAlmostEqual(m.probe_pass_threshold(1.0, 0.0), 0.0)
        self.assertAlmostEqual(m.probe_pass_threshold(0.9, 0.0), m.chord(0.9))
        self.assertGreater(m.probe_pass_threshold(0.9, 0.3), m.chord(0.9))
        self.assertAlmostEqual(m.chord(-1.0), 2.0)


class GateBehaviour(unittest.TestCase):
    def test_ungated_drift_grows_with_edits(self) -> None:
        short = m.simulate("none", FAST.replace(edits=40))
        long = m.simulate("none", FAST.replace(edits=160))
        self.assertGreater(long.drift_deg_median, short.drift_deg_median)
        self.assertLess(long.final_cos_median, short.final_cos_median)

    def test_random_walk_exponent_near_half(self) -> None:
        # seed 11, bias 0: RMS drift angle should scale like sqrt(n)
        s = m.simulate("none", m.Config(seed=11, bias=0.0))
        self.assertAlmostEqual(s.exponent, 0.5, delta=0.08)

    def test_hard_gate_holds_threshold(self) -> None:
        s = m.simulate("hard", FAST)
        self.assertGreaterEqual(s.min_cos_overall, FAST.threshold - 1e-12)
        self.assertGreater(s.rejected, 0)
        self.assertEqual(s.below_threshold_states, 0)

    def test_projection_never_rejects_but_bounds(self) -> None:
        s = m.simulate("project", FAST)
        self.assertEqual(s.rejected, 0)
        self.assertGreaterEqual(s.min_cos_overall, FAST.threshold - 1e-9)
        self.assertGreater(s.projected, 0)

    def test_rejections_rise_with_bias(self) -> None:
        unbiased = m.simulate("hard", FAST.replace(bias=0.0))
        biased = m.simulate("hard", FAST.replace(bias=0.01))
        self.assertGreater(biased.rejected_rate, unbiased.rejected_rate)

    def test_gated_drift_never_exceeds_ungated(self) -> None:
        none = m.simulate("none", FAST)
        hard = m.simulate("hard", FAST)
        self.assertLessEqual(hard.drift_deg_median, none.drift_deg_median)
        self.assertGreaterEqual(hard.min_cos_overall, none.min_cos_overall)

    def test_probe_resolution_improves_with_size(self) -> None:
        rows = m.probe_resolution(FAST, (4, 64), samples=200)
        self.assertGreater(rows[0]["miss_rate"], rows[1]["miss_rate"])
        self.assertGreaterEqual(rows[0]["false_alarm_rate"], rows[1]["false_alarm_rate"])

    def test_determinism(self) -> None:
        first = m.simulate("hard", FAST)
        second = m.simulate("hard", FAST)
        self.assertEqual(first.to_json(), second.to_json())


if __name__ == "__main__":
    unittest.main()
