"""Tests for the control-protocol loop simulator (Phase 20 · Lesson 19)."""

from __future__ import annotations

import math
import random
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def small(**overrides) -> main.Config:
    base = main.Config(cycles=6, edits=6, attack_rate=0.03, monitor_auc=0.8,
                       audit_budget=0.05, trials=400, seed=11)
    return replace(base, **overrides)


def streams_for(cfg: main.Config):
    rng = random.Random(cfg.seed)
    attack = [main.generate_stream(rng, cfg) for _ in range(cfg.trials)]
    return attack, [main.honest_view(s) for s in attack]


class MonitorMathTests(unittest.TestCase):
    def test_dprime_from_auc_matches_gaussian_formula(self):
        self.assertEqual(main.dprime_from_auc(0.5), 0.0)
        self.assertAlmostEqual(main.dprime_from_auc(0.8), 1.1902, places=3)
        self.assertTrue(math.isinf(main.dprime_from_auc(1.0)))
        self.assertLess(main.dprime_from_auc(0.7), main.dprime_from_auc(0.9))

    def test_threshold_calibrated_on_benign_scores(self):
        # A benign edit (score ~ N(0,1)) must exceed the threshold with probability = budget.
        rng = random.Random(0)
        tau = main.threshold_for_budget(0.05)
        hits = sum(1 for _ in range(20000) if rng.gauss(0, 1) > tau)
        self.assertAlmostEqual(hits / 20000, 0.05, delta=0.01)
        self.assertTrue(math.isinf(main.threshold_for_budget(0.0)))
        self.assertEqual(main.threshold_for_budget(1.0), -math.inf)


class ProtocolTests(unittest.TestCase):
    def test_no_oversight_safety_matches_theory(self):
        cfg = small(trials=1500)
        attack, honest = streams_for(cfg)
        r = main.evaluate("no-oversight", attack, honest, cfg)
        theory = (1 - cfg.attack_rate) ** (cfg.cycles * cfg.edits)
        self.assertAlmostEqual(r["safety"], theory, delta=0.04)
        self.assertEqual(r["usefulness"], 1.0)
        self.assertEqual(r["audits_honest"], 0.0)

    def test_higher_audit_budget_never_lowers_safety(self):
        cfg = small()
        attack, honest = streams_for(cfg)
        safeties = [main.evaluate("trusted-monitoring", attack, honest, cfg, b)["safety"]
                    for b in (0.0, 0.02, 0.05, 0.2, 0.5, 1.0)]
        self.assertEqual(safeties, sorted(safeties))
        self.assertGreater(safeties[-2], safeties[1])
        self.assertEqual(safeties[-1], 1.0)          # audit everything -> every harm is caught

    def test_defer_to_trusted_costs_usefulness_and_buys_safety(self):
        cfg = small()
        attack, honest = streams_for(cfg)
        tm = main.evaluate("trusted-monitoring", attack, honest, cfg)
        dtt = main.evaluate("defer-to-trusted", attack, honest, cfg)
        self.assertEqual(tm["usefulness"], 1.0)
        self.assertLess(dtt["usefulness"], tm["usefulness"])
        expected_loss = (cfg.defer_budget - cfg.audit_budget) * (1 - main.TRUSTED_VALUE_FRACTION)
        self.assertAlmostEqual(1 - dtt["usefulness"], expected_loss, delta=0.03)
        self.assertGreaterEqual(dtt["safety"], tm["safety"])

    def test_auc_extremes(self):
        cfg = small()
        attack, honest = streams_for(cfg)
        perfect = main.evaluate("trusted-monitoring", attack, honest, replace(cfg, monitor_auc=1.0))
        self.assertEqual(perfect["safety"], 1.0)      # d' = inf: every harmful edit is audited within any budget > 0
        self.assertEqual(perfect["unsafe_count"], 0)
        coin = main.evaluate("trusted-monitoring", attack, honest, replace(cfg, monitor_auc=0.5))
        good = main.evaluate("trusted-monitoring", attack, honest, replace(cfg, monitor_auc=0.9))
        self.assertLess(coin["safety"], good["safety"])

    def test_adaptive_attacker_lowers_safety(self):
        cfg = small()
        attack, honest = streams_for(cfg)
        a_attack, a_honest = streams_for(replace(cfg, adaptive=True))
        plain = main.evaluate("trusted-monitoring", attack, honest, cfg)["safety"]
        adaptive = main.evaluate("trusted-monitoring", a_attack, a_honest, replace(cfg, adaptive=True))["safety"]
        self.assertLess(adaptive, plain)
        # same number of harmful edits per run, only placed differently
        n_plain = sum(e.harmful for s in attack for c in s for e in c)
        n_adaptive = sum(e.harmful for s in a_attack for c in s for e in c)
        self.assertEqual(n_plain, n_adaptive)


class PauseRuleTests(unittest.TestCase):
    def test_pause_triggers_on_jump_or_suspicious_count(self):
        cfg = main.Config()
        self.assertEqual(main.should_pause(None, 9.0, 0, cfg), [])            # first cycle: no baseline
        self.assertEqual(main.should_pause(4.0, 5.0, 0, cfg), [])            # +25% < 30%
        self.assertTrue(main.should_pause(4.0, 5.3, 0, cfg)[0].startswith("gain jump"))
        self.assertEqual(main.should_pause(4.0, 4.1, cfg.suspicious_max, cfg), [])
        self.assertIn("suspicious", main.should_pause(4.0, 4.1, cfg.suspicious_max + 1, cfg)[0])

    def test_pause_protocol_catches_harm_in_a_jumping_cycle(self):
        cfg = replace(main.Config(), audit_budget=0.0, monitor_auc=0.8)
        quiet = [main.Edit(0.5, False, -3.0) for _ in range(8)]
        loud = [main.Edit(1.0, False, -3.0) for _ in range(7)] + [main.Edit(1.0, True, -3.0)]
        stream = [quiet, loud]                                             # gain 4.0 -> 9.0: a +125% jump
        tm = main.run_protocol(stream, cfg, "trusted-monitoring")
        pause = main.run_protocol(stream, cfg, "tm+pause")
        self.assertFalse(tm.safe)                                           # nothing audited: harm committed
        self.assertTrue(pause.safe and pause.caught)
        self.assertEqual(pause.pauses, 1)
        self.assertEqual(pause.audits, 8)                                   # the whole cycle was audited


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_results(self):
        cfg = small(trials=60)
        self.assertEqual(main.simulate(cfg), main.simulate(cfg))
        other = main.simulate(replace(cfg, seed=cfg.seed + 1))
        self.assertNotEqual(other["protocols"]["trusted-monitoring"]["safety"],
                            main.simulate(cfg)["protocols"]["trusted-monitoring"]["safety"])


if __name__ == "__main__":
    unittest.main()
