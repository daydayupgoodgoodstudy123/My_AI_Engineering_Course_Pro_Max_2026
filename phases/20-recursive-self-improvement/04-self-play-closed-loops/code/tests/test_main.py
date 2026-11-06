"""Deterministic tests for the self-play closed loop (Phase 20, Lesson 04)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402

CLEAN: list = []
NOISY: list = []
TEST_SEED = 11


def setUpModule() -> None:
    """Run the two contrast loops once; several tests read them."""
    cfg = dict(generations=8, episodes=5000, seed=TEST_SEED)
    CLEAN.extend(main.run_loop(main.LoopConfig(verifier_noise=0.0, **cfg)))
    NOISY.extend(main.run_loop(main.LoopConfig(verifier_noise=0.2, **cfg)))


class BoardRules(unittest.TestCase):
    def test_winner_and_draw_detection(self) -> None:
        self.assertIsNone(main.winner(main.start_board()))
        self.assertEqual(main.winner((1, 1, 1, 2, 2, 0, 0, 0, 0)), main.X)
        self.assertEqual(main.winner((2, 1, 1, 1, 2, 0, 0, 0, 2)), main.O)   # diagonal
        self.assertEqual(main.winner((1, 2, 1, 1, 2, 2, 2, 1, 1)), 0)        # full board, nobody
        board = main.play(main.start_board(), 4)
        self.assertEqual(board[4], main.X)
        self.assertEqual(main.player_to_move(board), main.O)
        self.assertEqual(main.legal_moves(board), [0, 1, 2, 3, 5, 6, 7, 8])
        with self.assertRaises(ValueError):
            main.play(board, 4)


class MinimaxOracle(unittest.TestCase):
    def test_minimax_never_loses(self) -> None:
        oracle = main.MinimaxOracle()
        rng = random.Random(0)
        self.assertEqual(oracle.value(main.start_board()), 0)       # tic-tac-toe is a draw
        (w, d, l), _ = main.evaluate_vs(oracle.policy(), main.random_policy, 300, rng)
        self.assertEqual(l, 0)
        self.assertGreater(w, 200)
        (w2, d2, l2), _ = main.evaluate_vs(oracle.policy(), oracle.policy(), 50, rng)
        self.assertEqual((w2, l2), (0, 0))
        self.assertEqual(d2, 50)

    def test_oracle_rates_moves(self) -> None:
        oracle = main.MinimaxOracle()
        # X: 0,1 ; O: 3,4 ; X to move must block square 5 or lose; square 2 wins outright.
        board = (1, 1, 0, 2, 2, 0, 0, 0, 0)
        values = oracle.move_values(board)
        self.assertEqual(values[2], 1)
        self.assertTrue(oracle.is_optimal(board, 2))
        self.assertFalse(oracle.is_optimal(board, 6))
        self.assertEqual(values[6], -1)


class QLearning(unittest.TestCase):
    def test_q_update_math(self) -> None:
        agent = main.QAgent(alpha=0.5, gamma=0.9)
        s = main.start_board()
        s_next = (1, 2, 0, 0, 0, 0, 0, 0, 0)
        agent.q[(s_next, 4)] = 0.6
        agent.q[(s_next, 8)] = -0.2
        self.assertAlmostEqual(agent.best_value(s_next), 0.6)
        target = 0.0 + agent.gamma * agent.best_value(s_next)        # r + gamma * max_a' Q(s', a')
        new = agent.update(s, 0, target)
        self.assertAlmostEqual(new, 0.0 + 0.5 * (0.54 - 0.0))         # 0.27
        self.assertAlmostEqual(agent.q_value(s, 0), 0.27)
        new2 = agent.update(s, 0, -1.0)                                # a terminal loss
        self.assertAlmostEqual(new2, 0.27 + 0.5 * (-1.0 - 0.27))

    def test_verifier_noise_flips_only_decided_games(self) -> None:
        rng = random.Random(1)
        self.assertEqual(main.verifier_report(main.X, 1.0, rng), main.O)
        self.assertEqual(main.verifier_report(main.O, 1.0, rng), main.X)
        self.assertEqual(main.verifier_report(0, 1.0, rng), 0)
        self.assertEqual(main.verifier_report(main.X, 0.0, rng), main.X)
        flips = sum(main.verifier_report(main.X, 0.2, rng) == main.O for _ in range(5000))
        self.assertTrue(800 <= flips <= 1200)

    def test_snapshot_is_frozen(self) -> None:
        agent = main.QAgent()
        agent.q[(main.start_board(), 4)] = 0.5
        frozen = agent.snapshot()
        agent.update(main.start_board(), 4, 1.0)
        self.assertAlmostEqual(frozen.q_value(main.start_board(), 4), 0.5)
        self.assertEqual(frozen.alpha, 0.0)


class SelfPlayLoop(unittest.TestCase):
    def test_self_play_improves_non_loss_rate(self) -> None:
        self.assertEqual(len(CLEAN), 8)
        self.assertGreater(CLEAN[-1].non_loss_vs_minimax, CLEAN[0].non_loss_vs_minimax)
        self.assertGreaterEqual(CLEAN[-1].non_loss_vs_minimax, 0.90)
        self.assertGreaterEqual(CLEAN[-1].optimal_move_rate, 0.95)
        self.assertEqual(CLEAN[-1].minimax_wdl[0], 0)                 # nobody beats minimax

    def test_noise_degrades_final_non_loss_rate(self) -> None:
        self.assertLess(NOISY[-1].non_loss_vs_minimax, CLEAN[-1].non_loss_vs_minimax)
        self.assertLess(NOISY[-1].optimal_move_rate, CLEAN[-1].optimal_move_rate)
        self.assertGreaterEqual(main.mean_exploit(NOISY), main.mean_exploit(CLEAN))

    def test_determinism(self) -> None:
        again = main.run_loop(main.LoopConfig(generations=8, episodes=5000, seed=TEST_SEED, verifier_noise=0.0))
        self.assertEqual([s.minimax_wdl for s in again], [s.minimax_wdl for s in CLEAN])
        self.assertEqual([s.random_wdl for s in again], [s.random_wdl for s in CLEAN])
        self.assertEqual([s.q_size for s in again], [s.q_size for s in CLEAN])

    def test_population_pool_bounded(self) -> None:
        short = main.run_loop(main.LoopConfig(generations=3, episodes=200, population=2, seed=5))
        self.assertEqual([s.gen for s in short], [0, 1, 2])
        self.assertEqual(short[0].exploit_by, -1)                       # no past generation yet
        self.assertTrue(all(0.0 <= s.exploit_loss_rate <= 1.0 for s in short))


if __name__ == "__main__":
    unittest.main()
