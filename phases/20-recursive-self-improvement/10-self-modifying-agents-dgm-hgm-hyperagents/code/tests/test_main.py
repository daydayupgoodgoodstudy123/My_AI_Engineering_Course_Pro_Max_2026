"""Deterministic unit tests for the archive-tree search simulator (Phase 20, Lesson 10)."""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as M  # noqa: E402


def node(i, parent, depth, p, s, f, cfg):
    return M.Node(id=i, parent=parent, depth=depth, p=p, skill=0.5, m=0.5, step=cfg.step0,
                  successes=s, failures=f)


def hand_tree(cfg):
    """root(5/15) -> a(10/10) -> b(15/5); root -> c(2/18)."""
    root = node(0, None, 0, 0.25, 5, 15, cfg)
    a = node(1, 0, 1, 0.50, 10, 10, cfg)
    b = node(2, 1, 2, 0.75, 15, 5, cfg)
    c = node(3, 0, 1, 0.10, 2, 18, cfg)
    root.children.extend([1, 3])
    a.children.append(2)
    return [root, a, b, c]


class CmpEstimatorMath(unittest.TestCase):
    def test_clade_counts_pool_the_whole_subtree(self):
        archive = hand_tree(M.Config())
        counts = M.all_clade_counts(archive)
        self.assertEqual(counts[0], (32, 48))   # root pools everything
        self.assertEqual(counts[1], (25, 15))   # a pools a + b
        self.assertEqual(counts[2], (15, 5))    # leaf: own counts only
        self.assertEqual(counts[3], (2, 18))
        self.assertEqual(sorted(M.clade_members(archive, 1)), [1, 2])
        self.assertEqual(sorted(M.clade_members(archive, 0)), [0, 1, 2, 3])

    def test_cmp_estimate_is_pooled_pass_rate_with_prior(self):
        self.assertAlmostEqual(M.cmp_estimate(25, 15, prior=1.0), 26 / 42)
        self.assertAlmostEqual(M.cmp_estimate(0, 0, prior=1.0), 0.5)   # no evidence -> prior mean
        self.assertAlmostEqual(M.cmp_estimate(15, 5, prior=0.0), 0.75)

    def test_realized_cmp_is_mean_of_descendants_excluding_self(self):
        archive = hand_tree(M.Config())
        realized = M.realized_cmp_all(archive)
        self.assertAlmostEqual(realized[0], (0.50 + 0.75 + 0.10) / 3)
        self.assertAlmostEqual(realized[1], 0.75)
        self.assertIsNone(realized[2])
        self.assertEqual(M.descendant_counts(archive), [3, 1, 0, 0])


class DeadClades(unittest.TestCase):
    def test_waste_counts_clades_that_never_beat_the_prior_best(self):
        cfg = M.Config()
        root = node(0, None, 0, 0.20, 4, 16, cfg)
        a = node(1, 0, 1, 0.30, 6, 14, cfg)     # beats 0.20 -> useful
        b = node(2, 1, 2, 0.25, 5, 15, cfg)     # clade max 0.25 <= best 0.30 -> wasted
        c = node(3, 0, 1, 0.10, 2, 18, cfg)     # wasted
        root.children.extend([1, 3])
        a.children.append(2)
        self.assertAlmostEqual(M.dead_clade_waste([root, a, b, c]), 2 / 3)
        self.assertEqual(M.dead_clade_waste([root]), 0.0)


class PolicyRules(unittest.TestCase):
    def test_novelty_bonus_decreases_with_children(self):
        bonuses = [M.novelty_bonus(k) for k in (0, 1, 2, 5, 20)]
        self.assertEqual(bonuses, sorted(bonuses, reverse=True))
        self.assertAlmostEqual(M.novelty_bonus(0), 1.0)
        self.assertAlmostEqual(M.novelty_bonus(3), 0.25)
        self.assertGreater(M.dgm_weight(0.4, 0), M.dgm_weight(0.4, 1))
        self.assertGreater(M.dgm_weight(0.5, 2), M.dgm_weight(0.2, 2))

    def test_mismatch_knob_mixes_task_skill_and_independent_skill(self):
        cfg0 = M.Config(mismatch=0.0)
        cfg1 = M.Config(mismatch=1.0)
        cfg5 = M.Config(mismatch=0.5)
        self.assertAlmostEqual(M.metaproductivity(0.45, 0.1, cfg0), 1.0)   # 0.5 + 2*(0.45-0.20)
        self.assertAlmostEqual(M.metaproductivity(0.45, 0.1, cfg1), 0.1)   # skill only
        self.assertAlmostEqual(M.metaproductivity(0.45, 0.1, cfg5), 0.55)
        self.assertAlmostEqual(M.metaproductivity(cfg0.p0, 0.5, cfg5), 0.5)


class ArchiveInvariants(unittest.TestCase):
    def test_every_node_but_root_has_an_earlier_parent(self):
        for policy in M.POLICIES:
            cfg = M.Config(budget=40)
            archive = M.run_trial(policy, cfg, random.Random(f"inv:{policy}"))
            self.assertEqual(len(archive), cfg.budget + 1)
            self.assertIsNone(archive[0].parent)
            for n in archive[1:]:
                self.assertIsNotNone(n.parent)
                self.assertLess(n.parent, n.id)
                self.assertIn(n.id, archive[n.parent].children)
                self.assertEqual(n.depth, archive[n.parent].depth + 1)
                self.assertEqual(n.successes + n.failures, cfg.tasks)
                self.assertTrue(0.0 <= n.score <= 1.0 and 0.0 < n.p < 1.0)
            if policy == "latest":
                self.assertTrue(all(n.parent == n.id - 1 for n in archive[1:]))

    def test_step_is_frozen_unless_meta_editable(self):
        frozen = M.run_trial("hgm", M.Config(budget=30), random.Random("step"))
        self.assertTrue(all(n.step == M.Config().step0 for n in frozen))
        editable = M.run_trial("hgm", M.Config(budget=30, meta_editable=True), random.Random("step"))
        self.assertGreater(len({round(n.step, 6) for n in editable}), 1)


class Determinism(unittest.TestCase):
    def test_same_seed_same_summary(self):
        cfg = M.Config(budget=30)
        a = M.summarise("dgm", cfg, trials=6, seed=11)
        b = M.summarise("dgm", cfg, trials=6, seed=11)
        self.assertEqual(a, b)
        c = M.summarise("dgm", cfg, trials=6, seed=12)
        self.assertNotEqual(a["best_p_median"], c["best_p_median"])

    def test_hgm_beats_latest_only_when_score_barely_tracks_m(self):
        # seed 11, mismatch 1.0 (corr(score, m) is lowest), equal budget.
        cfg = M.Config(budget=60, mismatch=1.0)
        hgm = M.summarise("hgm", cfg, trials=20, seed=11)
        latest = M.summarise("latest", cfg, trials=20, seed=11)
        self.assertGreaterEqual(hgm["best_p_median"], latest["best_p_median"])
        self.assertLessEqual(hgm["waste_median"], latest["waste_median"])


if __name__ == "__main__":
    unittest.main()
