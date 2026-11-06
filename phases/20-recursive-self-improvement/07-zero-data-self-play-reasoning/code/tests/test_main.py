"""Tests for the zero-data self-play simulator (Phase 20, Lesson 07)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


class RewardFormulaTests(unittest.TestCase):
    def test_learnability_reward_bounds_and_peak(self) -> None:
        for i in range(21):
            r = main.learnability_reward(i / 20)
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)
        self.assertAlmostEqual(main.learnability_reward(0.5), 1.0)
        self.assertAlmostEqual(main.learnability_reward(0.0), 0.0)
        self.assertAlmostEqual(main.learnability_reward(1.0), 0.0)
        self.assertAlmostEqual(main.learnability_reward(0.25), main.learnability_reward(0.75))

    def test_azr_reward_zero_at_both_ends(self) -> None:
        self.assertEqual(main.azr_reward(0.0), 0.0)
        self.assertEqual(main.azr_reward(1.0), 0.0)
        self.assertAlmostEqual(main.azr_reward(0.25), 0.75)
        # Asymmetric: a quarter-solved task is worth more than a three-quarters-solved one.
        self.assertGreater(main.azr_reward(0.25), main.azr_reward(0.75))


class ExecutorTests(unittest.TestCase):
    def test_execute_and_verify_all_modes(self) -> None:
        prog = (("add", 5), ("mul", 3), ("xor", 6))
        self.assertEqual(main.execute(prog, 10), 43)  # ((10+5)*3) % 97 = 45; 45 ^ 6 = 43
        rng = random.Random(0)
        for mode in main.MODES:
            task = main.Task(mode, prog, (10, 20, 30, 40))
            self.assertTrue(main.validate_task(task)[0])
            self.assertTrue(main.verify(task, main.reference_answer(task)), mode)
            self.assertFalse(main.verify(task, main.wrong_answer(task, rng)), mode)

    def test_validate_rejects_constant_program(self) -> None:
        task = main.Task("deduction", (("mul", 0), ("add", 7)), (1, 2, 3, 4))
        ok, reason = main.validate_task(task)
        self.assertFalse(ok)
        self.assertEqual(reason, "constant-output")
        self.assertFalse(main.validate_task(main.Task("deduction", (), (1, 2, 3, 4)))[0])


class LoopTests(unittest.TestCase):
    def test_learnability_tracks_the_frontier(self) -> None:
        res = main.run_loop(main.Config(reward="learnability", seed=11))
        skills = [s.skill for s in res.rounds]
        ds = [s.mean_difficulty for s in res.rounds]
        self.assertGreater(skills[-1], skills[0])
        self.assertGreater(sum(ds[-5:]) / 5, sum(ds[:5]) / 5)  # proposals get harder as s rises
        self.assertGreater(pearson(ds, skills), 0.8)
        self.assertLess(res.tracking_error, 2.0)

    def test_learnability_beats_hardest_and_easiest_at_seed_11(self) -> None:
        runs = {s: main.run_loop(main.Config(reward=s, seed=11))
                for s in ("learnability", "hardest", "easiest")}
        final = {s: r.final_skill for s, r in runs.items()}
        self.assertGreater(final["learnability"], final["hardest"])
        self.assertGreater(final["learnability"], final["easiest"])
        # 'hardest' drifts to the ceiling and almost never gets a verified solution:
        # it gains under one skill level and solves < 10% as many tasks as learnability.
        self.assertLess(final["hardest"] - main.Config().initial_skill, 1.0)
        self.assertLess(runs["hardest"].true_solved, 0.1 * runs["learnability"].true_solved)
        # 'easiest' solves MORE tasks than learnability yet learns less: volume is not signal.
        self.assertGreater(runs["easiest"].true_solved, runs["learnability"].true_solved)

    def test_verifier_false_positives_reduce_final_skill(self) -> None:
        clean = main.run_loop(main.Config(reward="learnability", verifier_fp=0.0, seed=11))
        leaky = main.run_loop(main.Config(reward="learnability", verifier_fp=0.25, seed=11))
        self.assertEqual(clean.false_accepts, 0)
        self.assertGreater(leaky.false_accepts, 0)
        self.assertLess(leaky.final_skill, clean.final_skill)
        last = leaky.rounds[-1]
        self.assertGreater(last.observed_solve_rate, last.true_solve_rate)

    def test_determinism(self) -> None:
        a = main.run_loop(main.Config(reward="azr", seed=3))
        b = main.run_loop(main.Config(reward="azr", seed=3))
        self.assertEqual(a, b)
        c = main.run_loop(main.Config(reward="azr", seed=4))
        self.assertNotEqual(a.final_skill, c.final_skill)


if __name__ == "__main__":
    unittest.main()
