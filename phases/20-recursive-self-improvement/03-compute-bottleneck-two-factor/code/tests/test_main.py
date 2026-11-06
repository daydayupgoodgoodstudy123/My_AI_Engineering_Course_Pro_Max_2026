"""Tests for the research-pipeline speedup simulator (Phase 20, Lesson 03)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import (  # noqa: E402
    COMPUTE,
    LABOUR,
    SWEEP,
    agent_sweep,
    amdahl_speedup,
    asymptote,
    build_stages,
    cycle_time,
    k_for_fraction_of_asymptote,
    labour_stage_names,
    multipliers_for,
    pool_ceiling,
    saturation_point,
    simulate_queue,
)


class StageTests(unittest.TestCase):
    def test_fractions_sum_to_one_for_any_compute_share(self) -> None:
        for f_c in (0.40, 0.20, 0.75):
            stages = build_stages(f_c)
            self.assertAlmostEqual(sum(s.fraction for s in stages), 1.0, places=9)
            compute = [s for s in stages if s.kind == COMPUTE]
            self.assertEqual(len(compute), 1)
            self.assertAlmostEqual(compute[0].fraction, f_c, places=9)
            self.assertEqual(len([s for s in stages if s.kind == LABOUR]), 4)

    def test_invalid_compute_share_rejected(self) -> None:
        for bad in (0.0, 1.0, -0.1, 1.5):
            with self.assertRaises(ValueError):
                build_stages(bad)


class AmdahlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stages = build_stages(0.40)
        self.acc = labour_stage_names(self.stages)

    def test_software_only_limit_is_one_over_f_compute(self) -> None:
        base = multipliers_for(self.stages, 1.0, 1.0)
        self.assertAlmostEqual(asymptote(self.stages, base, self.acc), 2.5, places=9)
        huge = amdahl_speedup(self.stages, multipliers_for(self.stages, 1e9, 1.0))
        self.assertAlmostEqual(huge, 2.5, places=6)
        for k in SWEEP:
            sp = amdahl_speedup(self.stages, multipliers_for(self.stages, float(k), 1.0))
            self.assertLessEqual(sp, 2.5 + 1e-12)

    def test_compute_growth_lifts_limit_to_g_over_f_compute(self) -> None:
        for g in (2.0, 4.0, 10.0):
            mult = multipliers_for(self.stages, 1.0, g)
            self.assertAlmostEqual(asymptote(self.stages, mult, self.acc), g / 0.40, places=9)
        # compute-only (k = 1) limit is 1 / f_labour
        comp_only = amdahl_speedup(self.stages, multipliers_for(self.stages, 1.0, 1e9))
        self.assertAlmostEqual(comp_only, 1.0 / 0.60, places=6)

    def test_speedup_is_monotone_in_k_and_in_g(self) -> None:
        prev = 0.0
        for k in SWEEP:
            sp = amdahl_speedup(self.stages, multipliers_for(self.stages, float(k), 1.0))
            self.assertGreater(sp, prev)
            prev = sp
        prev = 0.0
        for g in SWEEP:
            sp = amdahl_speedup(self.stages, multipliers_for(self.stages, 30.0, float(g)))
            self.assertGreater(sp, prev)
            prev = sp

    def test_k_for_fraction_of_asymptote_is_exact(self) -> None:
        base = multipliers_for(self.stages, 1.0, 1.0)
        k95 = k_for_fraction_of_asymptote(self.stages, base, self.acc, 0.95)
        self.assertAlmostEqual(k95, 28.5, places=6)
        sp = amdahl_speedup(self.stages, multipliers_for(self.stages, k95, 1.0))
        self.assertAlmostEqual(sp, 0.95 * 2.5, places=9)

    def test_human_decision_lowers_the_ceiling(self) -> None:
        acc_h = labour_stage_names(self.stages, human_decision=True)
        base_h = multipliers_for(self.stages, 1.0, 1.0, human_decision=True)
        self.assertAlmostEqual(asymptote(self.stages, base_h, acc_h), 1.0 / 0.45, places=9)
        self.assertLess(asymptote(self.stages, base_h, acc_h), 2.5)


class QueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stages = build_stages(0.40)

    def test_single_agent_single_gpu_reproduces_amdahl(self) -> None:
        for k, g in ((30.0, 1.0), (1.0, 1.0), (30.0, 4.0)):
            res = simulate_queue(1, 1, self.stages, k, g, horizon=1000.0)
            expected = amdahl_speedup(self.stages, multipliers_for(self.stages, k, g))
            self.assertAlmostEqual(res.throughput, expected, delta=0.01 * expected)
            self.assertAlmostEqual(res.mean_cycle_time, cycle_time(self.stages, multipliers_for(self.stages, k, g)), places=6)
            self.assertEqual(res.mean_wait, 0.0)

    def test_conservation_submitted_equals_completed_plus_in_flight(self) -> None:
        configs = ((1, 1, 0.0), (8, 8, 0.0), (128, 8, 0.0), (64, 4, 0.5), (16, 8, 1.0))
        for n, c, jitter in configs:
            res = simulate_queue(n, c, self.stages, 30.0, 1.0, horizon=50.0, jitter=jitter, seed=3)
            self.assertEqual(res.submitted, res.completed + res.queued + res.running, msg=str(res))
            self.assertLessEqual(res.running, c)
            self.assertGreaterEqual(res.queued, 0)

    def test_deterministic_for_same_seed_and_seed_free_without_jitter(self) -> None:
        a = simulate_queue(64, 8, self.stages, 30.0, 1.0, horizon=50.0, jitter=0.5, seed=3)
        b = simulate_queue(64, 8, self.stages, 30.0, 1.0, horizon=50.0, jitter=0.5, seed=3)
        self.assertEqual(a, b)
        c = simulate_queue(64, 8, self.stages, 30.0, 1.0, horizon=50.0, jitter=0.0, seed=1)
        d = simulate_queue(64, 8, self.stages, 30.0, 1.0, horizon=50.0, jitter=0.0, seed=99)
        self.assertEqual(c, d)

    def test_throughput_capped_by_pool_ceiling_and_saturates(self) -> None:
        ceiling = pool_ceiling(8, self.stages, 1.0)
        self.assertAlmostEqual(ceiling, 20.0, places=9)
        rows = [simulate_queue(n, 8, self.stages, 30.0, 1.0, horizon=50.0) for n in agent_sweep(128)]
        for r in rows:
            self.assertLessEqual(r.throughput, ceiling + 1e-9)
            self.assertLessEqual(r.utilization, 1.0 + 1e-9)
        by_n = {r.agents: r for r in rows}
        self.assertAlmostEqual(by_n[32].throughput, by_n[128].throughput, delta=0.01 * ceiling)
        self.assertGreater(by_n[128].mean_wait, by_n[32].mean_wait)
        self.assertEqual(saturation_point(rows), 8)

    def test_faster_agents_saturate_a_fixed_pool_sooner(self) -> None:
        # Analytic knee = ceiling x single-agent cycle time: slower (human) thinkers share GPUs better.
        ceiling = pool_ceiling(8, self.stages, 1.0)
        knee_fast = ceiling * cycle_time(self.stages, multipliers_for(self.stages, 30.0, 1.0))
        knee_slow = ceiling * cycle_time(self.stages, multipliers_for(self.stages, 1.0, 1.0))
        self.assertAlmostEqual(knee_fast, 8.4, places=6)
        self.assertAlmostEqual(knee_slow, 20.0, places=6)
        self.assertLess(knee_fast, knee_slow)

    def test_agent_sweep_shape(self) -> None:
        self.assertEqual(agent_sweep(128), [1, 2, 4, 8, 16, 32, 64, 128])
        self.assertEqual(agent_sweep(100), [1, 2, 4, 8, 16, 32, 64, 100])
        self.assertEqual(agent_sweep(1), [1])
        with self.assertRaises(ValueError):
            simulate_queue(0, 8, self.stages, 30.0, 1.0, horizon=10.0)
        self.assertFalse(math.isnan(simulate_queue(1, 1, self.stages, 30.0, 1.0, horizon=10.0).mean_cycle_time))


if __name__ == "__main__":
    unittest.main()
