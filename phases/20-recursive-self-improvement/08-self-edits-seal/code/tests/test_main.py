"""Tests for the SEAL-style self-edit outer-loop simulator (Phase 20, Lesson 08).

Run from code/:  python3 -m unittest discover tests -v
"""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as M  # noqa: E402


def protective_mass(res: M.RunResult) -> float:
    return sum(p for s, p in zip(M.BANK, res.policy_probs) if s.name in ("low-lr", "replay-mix"))


class TestInnerLoop(unittest.TestCase):
    def test_gradient_step_reduces_loss(self) -> None:
        layout, tasks = M.make_world(3, seed=1)
        model = M.Model([0.0] * layout.dim)
        batch = tasks[0].facts
        before = M.log_loss(model, batch)
        M.sgd_step(model, batch, lr=0.5)
        after = M.log_loss(model, batch)
        self.assertLess(after, before)
        trained = M.train(model, batch, steps=20, lr=0.5)
        self.assertLess(M.log_loss(trained, batch), after)
        self.assertGreater(M.accuracy(trained, batch), 0.9)

    def test_closure_is_monotone_and_idempotent(self) -> None:
        layout, tasks = M.make_world(3, seed=2)
        for ex in tasks[1].facts + tasks[2].questions:
            closed = M.closure(ex.x, layout)
            self.assertTrue(all(c >= x for c, x in zip(closed, ex.x)), "closure only turns features on")
            self.assertEqual(M.closure(closed, layout), closed, "closure is idempotent")
            for k in range(M.LEAVES):
                if closed[layout.leaf(ex.task, k)]:
                    self.assertEqual(closed[layout.parent_of(ex.task, k)], 1, "leaf implies its category")


class TestStrategyBank(unittest.TestCase):
    def test_transforms_preserve_label_consistency(self) -> None:
        """Every example a self-edit produces must still carry the truth about its complete fact."""
        layout, tasks = M.make_world(4, seed=5)
        rng = random.Random(0)
        buffer = [ex for t in tasks[:2] for ex in t.facts]
        for strat in M.BANK:
            for pipe in (0, M.PIPELINE_REPLAY):
                batch = M.build_batch(strat, tasks[2], buffer, layout, rng, pipe)
                self.assertGreaterEqual(len(batch), len(tasks[2].facts))
                for ex in batch:
                    truth = tasks[ex.task].teacher.label(M.closure(ex.x, layout))
                    self.assertEqual(ex.y, truth, f"{strat.name} changed a label")

    def test_batch_sizes_follow_the_strategy(self) -> None:
        layout, tasks = M.make_world(4, seed=5)
        rng = random.Random(1)
        buffer = [ex for t in tasks[:2] for ex in t.facts]
        n = len(tasks[2].facts)
        sizes = {s.name: len(M.build_batch(s, tasks[2], buffer, layout, rng, 0)) for s in M.BANK}
        self.assertEqual(sizes["raw"], n)
        self.assertEqual(sizes["paraphrase-augment"], n * 4)
        self.assertEqual(sizes["implication-expand"], n * 2)
        self.assertEqual(sizes["replay-mix"], n + min(12, len(buffer)))
        self.assertEqual(sizes["high-lr"], n)
        with_pipe = len(M.build_batch(M.BANK[0], tasks[2], buffer, layout, rng, M.PIPELINE_REPLAY))
        self.assertEqual(with_pipe, n + min(M.PIPELINE_REPLAY, len(buffer)))


class TestOuterLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.grid = M.grid(M.Config())   # default seed, default flags

    def test_rest_em_beats_fixed_random_on_new_task_accuracy(self) -> None:
        rest = self.grid[("rest-em", "off")]
        rand = self.grid[("fixed-random", "off")]
        self.assertGreater(rest.mean_new_acc, rand.mean_new_acc)

    def test_rest_em_without_replay_forgets_more_than_random(self) -> None:
        rest = self.grid[("rest-em", "off")]
        rand = self.grid[("fixed-random", "off")]
        self.assertGreater(rest.mean_forgetting, rand.mean_forgetting)

    def test_replay_reduces_forgetting(self) -> None:
        for outer in ("rest-em", "fixed-random"):
            off = self.grid[(outer, "off")].mean_forgetting
            on = self.grid[(outer, "on")].mean_forgetting
            self.assertLess(on, off, f"replay should reduce forgetting for {outer}")

    def test_anchored_reward_shifts_policy_toward_protective_strategies(self) -> None:
        new = self.grid[("rest-em", "off")]
        anchored = M.run(M.Config(reward="anchored"))
        self.assertGreater(protective_mass(anchored), protective_mass(new))
        self.assertLess(anchored.mean_forgetting, new.mean_forgetting)

    def test_policy_update_is_a_distribution_that_moves_toward_survivors(self) -> None:
        pol = M.SelfEditPolicy()
        self.assertAlmostEqual(sum(pol.probs()), 1.0)
        pol.reinforce([M.BANK[2], M.BANK[2]])
        probs = pol.probs()
        self.assertAlmostEqual(sum(probs), 1.0)
        self.assertEqual(max(probs), probs[2])
        self.assertAlmostEqual(probs[2], (1 - M.POLICY_MIX) / len(M.BANK) + M.POLICY_MIX)

    def test_determinism(self) -> None:
        a = M.run(M.Config())
        b = M.run(M.Config())
        key = lambda r: [(t.strategy, t.new_acc, t.old_avg, t.forgetting, t.oracle, t.kept) for t in r.per_task]
        self.assertEqual(key(a), key(b))
        self.assertEqual(a.policy_probs, b.policy_probs)
        self.assertEqual(a.deployed_counts, b.deployed_counts)


if __name__ == "__main__":
    unittest.main()
