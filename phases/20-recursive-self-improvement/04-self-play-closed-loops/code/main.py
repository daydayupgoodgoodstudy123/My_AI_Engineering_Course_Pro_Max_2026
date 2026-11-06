"""Self-play closed loop on tic-tac-toe — stdlib Python.

A tabular Q-learning policy generates its own training data by playing itself
and frozen past generations; the game rules are a perfect verifier of outcomes
and a minimax oracle is a perfect verifier of move quality. The same loop is
run twice, once with a clean verifier and once with a verifier that flips the
terminal result with probability p, to show how a corrupted verifier breaks
the closure that makes AlphaZero-style loops work.

Usage: python main.py [--generations 8] [--episodes 5000] [--verifier-noise 0.2]
                      [--population 1] [--seed 11] [--eval-games 200] [--out stats.json]
See docs/en.md (Phase 20, Lesson 04).
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

DEFAULT_SEED = 11
EMPTY, X, O = 0, 1, 2
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))
FROZEN_EPSILON = 0.10   # frozen opponents keep a little randomness so the learner sees variety

Board = Tuple[int, ...]
Policy = Callable[[Board, random.Random], int]


# ----------------------------------------------------------------------------
# Step 1 — environment and minimax oracle (perfect verifier)
# ----------------------------------------------------------------------------

def start_board() -> Board:
    return (EMPTY,) * 9


def player_to_move(board: Board) -> int:
    return X if board.count(X) == board.count(O) else O


def legal_moves(board: Board) -> List[int]:
    return [i for i, cell in enumerate(board) if cell == EMPTY]


def play(board: Board, move: int) -> Board:
    if board[move] != EMPTY:
        raise ValueError(f"square {move} is occupied")
    cells = list(board)
    cells[move] = player_to_move(board)
    return tuple(cells)


def winner(board: Board) -> Optional[int]:
    """X or O if someone has three in a row, 0 for a draw, None while the game is on."""
    for a, b, c in LINES:
        if board[a] != EMPTY and board[a] == board[b] == board[c]:
            return board[a]
    return None if EMPTY in board else 0


def outcome_for(result: int, seat: int) -> int:
    """Terminal reward from one seat's point of view: +1 win, -1 loss, 0 draw."""
    if result == 0:
        return 0
    return 1 if result == seat else -1


class MinimaxOracle:
    """Exact game-theoretic value of every position; memoised, 5,478 reachable boards."""

    def __init__(self) -> None:
        self._memo: Dict[Board, int] = {}

    def value(self, board: Board) -> int:
        """Value for the player to move: +1 forced win, 0 draw, -1 forced loss."""
        result = winner(board)
        if result is not None:
            return 0 if result == 0 else -1      # a decided game was won by the previous mover
        if board in self._memo:
            return self._memo[board]
        best = max(-self.value(play(board, m)) for m in legal_moves(board))
        self._memo[board] = best
        return best

    def move_values(self, board: Board) -> Dict[int, int]:
        return {m: -self.value(play(board, m)) for m in legal_moves(board)}

    def optimal_moves(self, board: Board) -> List[int]:
        values = self.move_values(board)
        best = max(values.values())
        return [m for m, v in values.items() if v == best]

    def is_optimal(self, board: Board, move: int) -> bool:
        return move in self.optimal_moves(board)

    def policy(self) -> Policy:
        return lambda board, rng: rng.choice(self.optimal_moves(board))


def random_policy(board: Board, rng: random.Random) -> int:
    return rng.choice(legal_moves(board))


# ----------------------------------------------------------------------------
# Step 2 — tabular Q-learning agent
# ----------------------------------------------------------------------------

@dataclass
class QAgent:
    alpha: float = 0.4
    gamma: float = 1.0
    epsilon: float = 0.30
    q: Dict[Tuple[Board, int], float] = field(default_factory=dict)

    def q_value(self, board: Board, move: int) -> float:
        return self.q.get((board, move), 0.0)

    def best_value(self, board: Board) -> float:
        """max_a Q(s, a); 0 at terminal boards (no legal continuation)."""
        if winner(board) is not None:
            return 0.0
        return max(self.q_value(board, m) for m in legal_moves(board))

    def greedy_moves(self, board: Board) -> List[int]:
        moves = legal_moves(board)
        best = max(self.q_value(board, m) for m in moves)
        return [m for m in moves if self.q_value(board, m) == best]

    def choose(self, board: Board, rng: random.Random, epsilon: Optional[float] = None) -> int:
        eps = self.epsilon if epsilon is None else epsilon
        if eps > 0 and rng.random() < eps:
            return rng.choice(legal_moves(board))
        return rng.choice(self.greedy_moves(board))

    def update(self, board: Board, move: int, target: float) -> float:
        """Q(s,a) <- Q(s,a) + alpha * (target - Q(s,a)); returns the new value."""
        old = self.q_value(board, move)
        new = old + self.alpha * (target - old)
        self.q[(board, move)] = new
        return new

    def snapshot(self) -> "QAgent":
        """Frozen copy used as a past-generation opponent (its table never changes again)."""
        return QAgent(alpha=0.0, gamma=self.gamma, epsilon=FROZEN_EPSILON, q=dict(self.q))

    def policy(self, epsilon: Optional[float] = None) -> Policy:
        return lambda board, rng: self.choose(board, rng, epsilon)


def verifier_report(result: int, noise: float, rng: random.Random) -> int:
    """The verifier announces who won. With probability `noise` it flips X<->O (draws stay draws)."""
    if result in (X, O) and noise > 0 and rng.random() < noise:
        return O if result == X else X
    return result


def play_training_game(learner: QAgent, seats: Dict[int, Policy], learning_seats: Sequence[int],
                       rng: random.Random, noise: float, noise_rng: random.Random) -> int:
    """One episode. Learner seats are updated online; the terminal reward comes from the verifier."""
    board = start_board()
    pending: Dict[int, Optional[Tuple[Board, int]]] = {X: None, O: None}
    while winner(board) is None:
        seat = player_to_move(board)
        if seat in learning_seats and pending[seat] is not None:
            s0, a0 = pending[seat]
            learner.update(s0, a0, learner.gamma * learner.best_value(board))
        move = seats[seat](board, rng)
        if seat in learning_seats:
            pending[seat] = (board, move)
        board = play(board, move)
    result = winner(board)
    reported = verifier_report(result, noise, noise_rng)
    for seat in learning_seats:
        if pending[seat] is not None:
            s0, a0 = pending[seat]
            learner.update(s0, a0, float(outcome_for(reported, seat)))
    return result


# ----------------------------------------------------------------------------
# Step 3 — generational self-play
# ----------------------------------------------------------------------------

@dataclass
class LoopConfig:
    generations: int = 8
    episodes: int = 5000
    population: int = 1
    verifier_noise: float = 0.0
    seed: int = DEFAULT_SEED
    eval_games: int = 200
    alpha: float = 0.4
    gamma: float = 1.0
    epsilon: float = 0.30


@dataclass
class GenStats:
    gen: int
    minimax_wdl: Tuple[int, int, int]
    random_wdl: Tuple[int, int, int]
    optimal_move_rate: float
    exploit_loss_rate: float
    exploit_by: int           # which past generation beats us most; -1 if none
    q_size: int

    @property
    def non_loss_vs_minimax(self) -> float:
        w, d, l = self.minimax_wdl
        return (w + d) / max(1, w + d + l)

    @property
    def win_vs_random(self) -> float:
        w, d, l = self.random_wdl
        return w / max(1, w + d + l)


def evaluate_vs(agent_policy: Policy, opponent_policy: Policy, games: int, rng: random.Random,
                oracle: Optional[MinimaxOracle] = None) -> Tuple[Tuple[int, int, int], float]:
    """Greedy agent vs an opponent, alternating seats. Returns (W, D, L) and the agent's optimal-move rate."""
    w = d = l = 0
    optimal = total = 0
    for g in range(games):
        agent_seat = X if g % 2 == 0 else O
        board = start_board()
        while winner(board) is None:
            seat = player_to_move(board)
            if seat == agent_seat:
                move = agent_policy(board, rng)
                if oracle is not None:
                    total += 1
                    optimal += int(oracle.is_optimal(board, move))
            else:
                move = opponent_policy(board, rng)
            board = play(board, move)
        z = outcome_for(winner(board), agent_seat)
        if z > 0:
            w += 1
        elif z < 0:
            l += 1
        else:
            d += 1
    return (w, d, l), (optimal / total if total else 0.0)


def train_generation(learner: QAgent, pool: Sequence[QAgent], cfg: LoopConfig,
                     rng: random.Random, noise_rng: random.Random) -> None:
    """Half the episodes are pure self-play (both seats learn); half are against a sampled past generation."""
    for ep in range(cfg.episodes):
        if not pool or ep % 2 == 0:
            seats = {X: learner.policy(), O: learner.policy()}
            play_training_game(learner, seats, (X, O), rng, cfg.verifier_noise, noise_rng)
        else:
            opponent = rng.choice(list(pool))
            my_seat = X if (ep // 2) % 2 == 0 else O
            seats = {my_seat: learner.policy(), 3 - my_seat: opponent.policy()}
            play_training_game(learner, seats, (my_seat,), rng, cfg.verifier_noise, noise_rng)


def evaluate_generation(gen: int, learner: QAgent, past: Sequence[QAgent], oracle: MinimaxOracle,
                        cfg: LoopConfig, eval_rng: random.Random) -> GenStats:
    greedy = learner.policy(epsilon=0.0)
    mm_wdl, opt_rate = evaluate_vs(greedy, oracle.policy(), cfg.eval_games, eval_rng, oracle)
    rnd_wdl, _ = evaluate_vs(greedy, random_policy, cfg.eval_games, eval_rng)
    worst, worst_by = 0.0, -1
    for idx, old in enumerate(past):
        (_, _, l), _ = evaluate_vs(greedy, old.policy(epsilon=0.0), cfg.eval_games, eval_rng)
        rate = l / cfg.eval_games
        if rate > worst:
            worst, worst_by = rate, idx
    return GenStats(gen, mm_wdl, rnd_wdl, opt_rate, worst, worst_by, len(learner.q))


def run_loop(cfg: LoopConfig) -> List[GenStats]:
    rng = random.Random(cfg.seed)
    noise_rng = random.Random(cfg.seed * 7919 + 1)
    eval_rng = random.Random(cfg.seed * 7919 + 2)
    oracle = MinimaxOracle()
    learner = QAgent(alpha=cfg.alpha, gamma=cfg.gamma, epsilon=cfg.epsilon)
    frozen: List[QAgent] = []
    history: List[GenStats] = []
    for gen in range(cfg.generations):
        pool = frozen[-cfg.population:] if cfg.population > 0 else []
        train_generation(learner, pool, cfg, rng, noise_rng)
        history.append(evaluate_generation(gen, learner, frozen, oracle, cfg, eval_rng))
        frozen.append(learner.snapshot())
    return history


# ----------------------------------------------------------------------------
# Step 4 — report
# ----------------------------------------------------------------------------

def wdl(t: Tuple[int, int, int]) -> str:
    return f"{t[0]:>3}/{t[1]:>3}/{t[2]:>3}"


def print_run(label: str, cfg: LoopConfig, history: List[GenStats]) -> None:
    print(f"\n{label}")
    print(f"  generations={cfg.generations} episodes/gen={cfg.episodes} population={cfg.population} "
          f"verifier-noise={cfg.verifier_noise:.2f} seed={cfg.seed} eval-games={cfg.eval_games}")
    print(f"  {'gen':>3}  {'vs minimax W/D/L':>17}  {'non-loss':>8}  {'vs random W/D/L':>16}  "
          f"{'win':>6}  {'optimal':>7}  {'exploit':>7}  {'by':>4}  {'|Q|':>6}")
    for s in history:
        by = f"g{s.exploit_by}" if s.exploit_by >= 0 else "-"
        print(f"  {s.gen:>3}  {wdl(s.minimax_wdl):>17}  {s.non_loss_vs_minimax:>8.1%}  "
              f"{wdl(s.random_wdl):>16}  {s.win_vs_random:>6.1%}  {s.optimal_move_rate:>7.1%}  "
              f"{s.exploit_loss_rate:>7.1%}  {by:>4}  {s.q_size:>6}")


def mean_exploit(history: List[GenStats]) -> float:
    """Average over generations of the worst loss rate against any past generation (0 = never refuted)."""
    return sum(s.exploit_loss_rate for s in history) / max(1, len(history))


def first_gen_reaching(history: List[GenStats], threshold: float) -> int:
    for s in history:
        if s.non_loss_vs_minimax >= threshold:
            return s.gen
    return -1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generations", type=int, default=8, help="self-play generations (default: %(default)s)")
    parser.add_argument("--episodes", type=int, default=5000, help="training games per generation (default: %(default)s)")
    parser.add_argument("--verifier-noise", type=float, default=0.2,
                        help="probability the verifier flips who won, for the noisy run (default: %(default)s)")
    parser.add_argument("--population", type=int, default=1,
                        help="how many past generations stay in the opponent pool; 1 = previous only (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--eval-games", type=int, default=200, help="evaluation games per opponent (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write per-generation stats as JSON")
    args = parser.parse_args()

    base = dict(generations=args.generations, episodes=args.episodes, population=args.population,
                seed=args.seed, eval_games=args.eval_games)
    clean_cfg = LoopConfig(verifier_noise=0.0, **base)
    noisy_cfg = LoopConfig(verifier_noise=args.verifier_noise, **base)

    print("=" * 96)
    print("SELF-PLAY CLOSED LOOP — tic-tac-toe, tabular Q-learning, minimax oracle (Phase 20, Lesson 04)")
    print("=" * 96)
    print("  columns: non-loss = (W+D)/games vs a minimax-optimal opponent (optimal play never loses);")
    print("           optimal = share of the learner's moves the oracle rates minimax-optimal;")
    print("           exploit = highest loss rate against any frozen past generation (exploitability proxy).")

    clean = run_loop(clean_cfg)
    print_run("RUN A — clean verifier (game rules report the true result)", clean_cfg, clean)
    noisy = run_loop(noisy_cfg)
    print_run(f"RUN B — corrupted verifier (result flipped with p={args.verifier_noise:.2f})", noisy_cfg, noisy)

    if args.out:
        payload = {"clean": [asdict(s) for s in clean], "noisy": [asdict(s) for s in noisy],
                   "config": {"clean": asdict(clean_cfg), "noisy": asdict(noisy_cfg)}}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")

    c0, cN = clean[0], clean[-1]
    n0, nN = noisy[0], noisy[-1]
    last = cN.gen
    c_reach = first_gen_reaching(clean, 0.95)
    n_reach = first_gen_reaching(noisy, 0.95)
    c_peak = max(clean, key=lambda s: s.non_loss_vs_minimax)
    n_peak = max(noisy, key=lambda s: s.non_loss_vs_minimax)

    print()
    print("=" * 96)
    print("HEADLINE")
    print("-" * 96)
    print(f"  Clean verifier: non-loss vs minimax went {c0.non_loss_vs_minimax:.1%} (gen 0) -> "
          f"{cN.non_loss_vs_minimax:.1%} (gen {last}); optimal-move rate {c0.optimal_move_rate:.1%} -> "
          f"{cN.optimal_move_rate:.1%}; win rate vs random {c0.win_vs_random:.1%} -> {cN.win_vs_random:.1%}.")
    if c_reach >= 0:
        print(f"  Clean verifier first reached >=95.0% non-loss at generation {c_reach} "
              f"({c_reach * clean_cfg.episodes + clean_cfg.episodes:,} games of self-generated data).")
    else:
        print(f"  Clean verifier never reached 95.0% non-loss in {clean_cfg.generations} generations "
              f"(peak {c_peak.non_loss_vs_minimax:.1%} at gen {c_peak.gen}).")
    print(f"  Verifier flipped with p={args.verifier_noise:.2f}: non-loss {n0.non_loss_vs_minimax:.1%} -> "
          f"{nN.non_loss_vs_minimax:.1%}; optimal-move rate {nN.optimal_move_rate:.1%}; "
          f"win rate vs random {nN.win_vs_random:.1%}" +
          (f"; first >=95.0% at generation {n_reach}." if n_reach >= 0 else
           f"; never reached 95.0% (peak {n_peak.non_loss_vs_minimax:.1%} at gen {n_peak.gen})."))
    gap = cN.non_loss_vs_minimax - nN.non_loss_vs_minimax
    verdict = ("the corrupted verifier costs" if gap > 0 else "the corrupted verifier gained")
    print(f"  Same seed, same games, same episodes: {verdict} {abs(gap):.1%} non-loss and "
          f"{abs(cN.optimal_move_rate - nN.optimal_move_rate):.1%} optimal-move rate at generation {last}.")
    print(f"  Exploitability proxy (worst loss rate vs any frozen past generation), averaged over generations: "
          f"clean {mean_exploit(clean):.1%}, noisy {mean_exploit(noisy):.1%}; at gen {last}: clean "
          f"{cN.exploit_loss_rate:.1%}, noisy {nN.exploit_loss_rate:.1%} (50.0% = a past generation wins every "
          f"game as one colour). Tables: {cN.q_size:,} vs {nN.q_size:,} entries.")
    print("  Reading: a perfect verifier turns self-generated games into monotone progress toward the minimax")
    print("  ceiling; corrupt the verifier and the same loop learns the verifier's mistakes (Lesson 14).")


if __name__ == "__main__":
    main()
