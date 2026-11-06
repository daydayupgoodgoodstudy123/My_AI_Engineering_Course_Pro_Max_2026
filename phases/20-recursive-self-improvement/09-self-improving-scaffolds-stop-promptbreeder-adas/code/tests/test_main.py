"""Tests for the self-improving scaffold harness (Phase 20, Lesson 09)."""
import json
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as M  # noqa: E402


KNOWN = (0.5, 0.5, 0.3, 0.7, 0.2, 0.8)   # three perfect pairs; lower bound 3


class UtilityTests(unittest.TestCase):
    def test_known_instance_scores(self):
        self.assertEqual(M.lower_bound(KNOWN), 3)
        perfect = M.packing_score(("sort_desc", "pack_first"), [KNOWN])
        self.assertAlmostEqual(perfect, 1.0, places=9)            # 3 bins, all full
        trivial = M.packing_score((), [KNOWN])                    # each item in its own bin
        tight = sum(x * x for x in KNOWN) / len(KNOWN)
        self.assertAlmostEqual(trivial, 0.5 * 3 / 6 + 0.5 * tight, places=9)
        self.assertEqual(len(M.run_program(("sort_desc", "pack_first"), KNOWN)), 3)

    def test_every_op_preserves_items_and_capacity(self):
        rng = random.Random(3)
        for _ in range(20):
            items = M.make_instance(5, rng)
            for name, op in M.OPS.items():
                bins = op(M.run_program(("pack_first",), items))
                self.assertEqual(Counter(round(x, 9) for b in bins for x in b),
                                 Counter(round(x, 9) for x in items), name)
                self.assertTrue(all(sum(b) <= M.CAP + 1e-9 for b in bins), name)
                self.assertTrue(all(b for b in bins), f"{name} produced an empty bin")

    def test_sandbox_enforced_makes_bypass_worth_zero(self):
        world = M.build_world(5)
        for prog in world.heldout + [M.SEED_PROGRAM]:
            hacked = prog + (M.BYPASS_OP,)
            self.assertAlmostEqual(M.utility(hacked, world.instances, True),
                                   M.utility(prog, world.instances, True), places=12)
            self.assertAlmostEqual(M.utility(hacked, world.instances, False),
                                   M.utility(prog, world.instances, False) + M.BYPASS_BONUS, places=12)


class ImproverTests(unittest.TestCase):
    def test_improver_never_returns_worse_than_input(self):
        world = M.build_world(7)
        score = lambda p: M.utility(p, world.instances, True)  # noqa: E731
        rng = random.Random(1)
        for i in range(12):
            prog = M.random_program(rng)
            params = M.ImproverParams(k=1 + i % 4, accept="anneal" if i % 2 else "hill", temperature=0.05)
            best, best_u, log = M.improve(prog, M.mutate_program, score, params, 25, rng)
            self.assertGreaterEqual(best_u + 1e-12, score(prog))
            self.assertAlmostEqual(best_u, score(best), places=12)
            self.assertEqual(len(log), 25)                          # budget is spent exactly

    def test_mutations_stay_within_bounds(self):
        rng = random.Random(9)
        params = M.ImproverParams()
        for _ in range(300):
            params = M.mutate_params(params, params, rng)
            self.assertTrue(1 <= params.k <= M.K_MAX)
            self.assertAlmostEqual(params.p_insert + params.p_remove + params.p_swap, 1.0, places=6)
            self.assertTrue(all(0.125 <= w <= 8.0 for w in params.op_weights.values()))
            self.assertIn(params.accept, ("hill", "anneal"))
        prog = M.SEED_PROGRAM
        for _ in range(300):
            prog = M.mutate_program(prog, params, rng)
            self.assertTrue(1 <= len(prog) <= M.MAX_LEN)
            self.assertTrue(set(prog) <= set(M.OP_NAMES))


class LoopTests(unittest.TestCase):
    def test_meta_on_beats_or_ties_meta_off_at_seed_11(self):
        world = M.build_world(M.DEFAULT_SEED)
        on = M.run_config(True, True, 10, 200, M.DEFAULT_SEED * 10 + 3, world)
        off = M.run_config(False, True, 10, 200, M.DEFAULT_SEED * 10 + 1, world)
        self.assertGreaterEqual(on.records[-1].honest + 1e-12, off.records[-1].honest)
        self.assertEqual(on.total_evals, off.total_evals)          # equal budget, meta step included
        for res in (on, off):
            self.assertTrue(all(r.evals <= 200 for r in res.records))
            self.assertAlmostEqual(res.records[-1].reported, res.records[-1].honest, places=12)

    def test_unenforced_sandbox_is_exploited_and_enforced_is_not(self):
        world = M.build_world(4)
        hacked = M.run_config(False, False, 4, 120, 41, world)
        clean = M.run_config(False, True, 4, 120, 41, world)
        last = hacked.records[-1]
        self.assertTrue(last.best_has_bypass)
        self.assertAlmostEqual(last.reported - last.honest, M.BYPASS_BONUS, places=12)
        self.assertAlmostEqual(clean.records[-1].reported, clean.records[-1].honest, places=12)
        self.assertGreater(sum(r.bypass_attempts for r in hacked.records), 0)

    def test_determinism(self):
        def run():
            world = M.build_world(2)
            res = M.run_config(True, False, 3, 80, 21, world)
            return json.dumps([r.__dict__ for r in res.records], sort_keys=True)
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
