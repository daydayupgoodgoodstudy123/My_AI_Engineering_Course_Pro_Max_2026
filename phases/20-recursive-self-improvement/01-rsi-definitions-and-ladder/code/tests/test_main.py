"""Tests for Phase 20 / Lesson 01: loop recurrences, convergence and the ladder classifier."""

from __future__ import annotations

import math
import random
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from main import (  # noqa: E402
    Closure, Domain, LoopParams, Mechanism, SystemProfile, Target, Verifier,
    alibaba_level, analytic_ceiling, chen_closure, classify, cycles_to_multiple, gains,
    matched_fixed_improver, simulate_diminishing, simulate_fixed_improver,
    simulate_self_referential,
)


def profile(**overrides) -> SystemProfile:
    base = dict(name="X", year=2026, proposes=True, applies=True, validates=True,
                mechanism=Mechanism.CODE, domain=Domain.SINGLE, transfers=False,
                verifier=Verifier.EXECUTION, target=Target.BEHAVIOUR, lesson="-")
    base.update(overrides)
    return SystemProfile(**base)


class LoopRecurrenceTests(unittest.TestCase):
    def test_fixed_shapes_converge_or_crawl_but_never_reach_10x(self):
        p = LoopParams()
        a = simulate_fixed_improver(200, p, random.Random(0))
        self.assertAlmostEqual(a[-1], p.ceiling * p.c0, places=6)
        self.assertTrue(all(y >= x for x, y in zip(a, a[1:])))
        self.assertIsNone(cycles_to_multiple(a))
        b = simulate_diminishing(30, p, random.Random(0))
        g = gains(b)
        self.assertTrue(all(y < x for x, y in zip(g, g[1:])), "shape (b) gains must shrink every cycle")
        self.assertGreater(b[-1], b[0])
        self.assertIsNone(cycles_to_multiple(b))

    def test_self_referential_subcritical_converges_to_analytic_ceiling(self):
        p = LoopParams()
        traj = simulate_self_referential(300, p, random.Random(0), returns=0.8)
        self.assertAlmostEqual(analytic_ceiling(p, 0.8), 2.5)            # 1 + 0.3 / (1 - 0.8)
        self.assertAlmostEqual(traj[-1], analytic_ceiling(p, 0.8), places=6)
        self.assertIsNone(analytic_ceiling(p, 1.0))
        self.assertIsNone(cycles_to_multiple(traj))

    def test_self_referential_supercritical_accelerates_and_hits_10x(self):
        p = LoopParams()
        traj = simulate_self_referential(30, p, random.Random(0), returns=1.2)
        g = gains(traj)
        self.assertTrue(all(y > x for x, y in zip(g, g[1:])), "shape (c) gains must grow every cycle")
        # C_n = 1 + 0.3 (1.2^n - 1) / 0.2 >= 10  <=>  1.2^n >= 7  <=>  n = ceil(log 7 / log 1.2) = 11
        self.assertEqual(cycles_to_multiple(traj), math.ceil(math.log(7) / math.log(1.2)))
        self.assertEqual(cycles_to_multiple(traj), 11)

    def test_fixed_improver_with_matched_params_equals_subcritical_recursion(self):
        p = LoopParams(noise=0.0)
        c = simulate_self_referential(40, p, random.Random(0), returns=0.8)
        a = simulate_fixed_improver(40, matched_fixed_improver(p, 0.8), random.Random(0))
        self.assertEqual(len(a), len(c))
        for x, y in zip(a, c):
            self.assertAlmostEqual(x, y, places=9)

    def test_mechanism_noise_is_a_drag_on_the_median(self):
        """Invariant: under multiplicative noise the median final capability of the
        self-referential loop sits below the noise-free value at the same r."""
        det = simulate_self_referential(30, LoopParams(noise=0.0), random.Random(0), returns=1.0)[-1]
        p = LoopParams(noise=0.1)
        finals = [simulate_self_referential(30, p, random.Random(1000 + t), returns=1.0)[-1]
                  for t in range(300)]
        self.assertLess(statistics.median(finals), det)
        self.assertTrue(all(f >= 1.0 for f in finals), "capability never falls below its start")


class LadderClassifierTests(unittest.TestCase):
    def test_boundary_editing_mechanism_but_human_applies_is_not_L4(self):
        p = profile(mechanism=Mechanism.CODE, applies=False)
        level, notes = alibaba_level(p)
        self.assertEqual(level, "L2")
        self.assertTrue(any("human" in n for n in notes))
        self.assertIs(chen_closure(p), Closure.HUMAN_IN_LOOP)
        # same system with the human removed from the apply step -> L4
        self.assertEqual(alibaba_level(profile(mechanism=Mechanism.CODE, applies=True))[0], "L4")
        # no proposal at all -> L1; operators-only self-reference -> L4 with a flag
        self.assertEqual(alibaba_level(profile(proposes=False))[0], "L1")
        level, notes = alibaba_level(profile(mechanism=Mechanism.OPERATORS))
        self.assertEqual(level, "L4")
        self.assertTrue(any("operators-only" in n for n in notes))

    def test_named_systems_land_on_expected_rungs(self):
        by_name = {s.name: classify(s) for s in main.SYSTEMS}
        self.assertEqual(len(main.SYSTEMS), 10)
        self.assertEqual(by_name["Human-in-loop FT"].level, "L2")
        self.assertEqual(by_name["AlphaZero"].level, "L3")
        self.assertEqual(by_name["STaR"].level, "L3")
        self.assertEqual(by_name["ADAS"].level, "L3")          # transfer without self-reference
        self.assertEqual(by_name["DGM"].level, "L4")
        self.assertEqual(by_name["Hyperagents"].level, "L4")   # transfer across fixed benchmarks
        self.assertEqual(by_name["AIDE^2"].level, "L4")
        self.assertFalse(any(v.level == "L5" for v in by_name.values()))

    def test_L5_requires_open_domain_and_transfer_on_top_of_self_reference(self):
        l4 = profile(mechanism=Mechanism.CODE, domain=Domain.MULTI, transfers=True)
        self.assertEqual(alibaba_level(l4)[0], "L4")
        l5 = profile(mechanism=Mechanism.CODE, domain=Domain.OPEN, transfers=True)
        self.assertEqual(alibaba_level(l5)[0], "L5")
        self.assertIs(chen_closure(l5), Closure.CLOSED_OPEN)
        # open domain without self-reference stays L3
        self.assertEqual(alibaba_level(profile(mechanism=Mechanism.NONE, domain=Domain.OPEN, transfers=True))[0], "L3")


if __name__ == "__main__":
    unittest.main()
