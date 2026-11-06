"""Zero-data self-play simulator (Absolute Zero / R-Zero / Agent0) — stdlib Python.

A proposer picks a difficulty d and samples a d-step integer program; a stdlib
executor validates the task (rejecting degenerate ones) and later verifies the
answer in one of three modes (deduction / abduction / induction). A solver with
latent skill s succeeds with probability sigmoid(s - d) and learns only from
verified solutions. Compare proposer rewards and watch a leaky verifier
(--verifier-fp) poison the loop.
Usage: python3 main.py [--rounds 40] [--reward learnability] [--verifier-fp 0.0] [--seed 11]
See docs/en.md (Phase 20, Lesson 07: Zero-Data Self-Play).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass

DEFAULT_SEED = 11
MODULUS = 97
OPS = ("add", "sub", "mul", "xor")
MODES = ("deduction", "abduction", "induction")
REWARD_SCHEMES = ("learnability", "azr", "random", "hardest", "easiest")
N_INPUTS = 4

Program = tuple[tuple[str, int], ...]


# ---------------------------------------------------------------- helpers
def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def solve_probability(skill: float, difficulty: int) -> float:
    """The solver's latent chance of solving a task of difficulty d."""
    return sigmoid(skill - difficulty)


# ---------------------------------------------------------------- tasks & executor
@dataclass(frozen=True)
class Task:
    mode: str
    program: Program
    inputs: tuple[int, ...]

    @property
    def difficulty(self) -> int:
        return len(self.program)


def execute(program: Program, x: int) -> int:
    """The executor. Ground truth for every task comes from running this."""
    for op, k in program:
        if op == "add":
            x = (x + k) % MODULUS
        elif op == "sub":
            x = (x - k) % MODULUS
        elif op == "mul":
            x = (x * k) % MODULUS
        elif op == "xor":
            x = (x ^ k) % MODULUS
        else:
            raise ValueError(f"unknown op {op!r}")
    return x


def sample_program(d: int, rng: random.Random) -> Program:
    ops: list[tuple[str, int]] = []
    for _ in range(d):
        op = rng.choice(OPS)
        if op == "mul":
            k = rng.randint(0, 12)  # k = 0 collapses the program to a constant
        elif op == "xor":
            k = rng.randint(1, 127)
        else:
            k = rng.randint(1, MODULUS - 1)
        ops.append((op, k))
    return tuple(ops)


def propose_task(d: int, mode: str, rng: random.Random) -> Task:
    inputs = tuple(rng.sample(range(MODULUS), N_INPUTS))
    return Task(mode, sample_program(d, rng), inputs)


def validate_task(task: Task) -> tuple[bool, str]:
    """Executor-side validation (AZR: the environment filters proposals)."""
    if task.mode not in MODES:
        return False, "unknown-mode"
    if not task.program:
        return False, "empty-program"
    try:
        outputs = [execute(task.program, x) for x in task.inputs]
    except ValueError as exc:
        return False, str(exc)
    if len(set(outputs)) == 1:
        return False, "constant-output"
    return True, "ok"


def reference_answer(task: Task):
    if task.mode == "deduction":
        return execute(task.program, task.inputs[0])
    if task.mode == "abduction":
        return task.inputs[0]
    return task.program


def verify(task: Task, answer) -> bool:
    """Executor-side verification, one rule per task mode (AZR Section 3.2)."""
    if task.mode == "deduction":  # given p and i, predict o
        return answer == execute(task.program, task.inputs[0])
    if task.mode == "abduction":  # given p and o, find any i with p(i) = o
        if not isinstance(answer, int):
            return False
        return execute(task.program, answer) == execute(task.program, task.inputs[0])
    try:  # induction: the synthesized program must match shown AND held-out pairs
        return all(execute(answer, x) == execute(task.program, x) for x in task.inputs)
    except (ValueError, TypeError):
        return False


def wrong_answer(task: Task, rng: random.Random):
    """A plausible-looking answer that the executor will reject."""
    if task.mode == "deduction":
        truth = execute(task.program, task.inputs[0])
        return (truth + rng.randint(1, MODULUS - 1)) % MODULUS
    if task.mode == "abduction":
        target = execute(task.program, task.inputs[0])
        start = rng.randrange(MODULUS)
        for off in range(MODULUS):
            x = (start + off) % MODULUS
            if execute(task.program, x) != target:
                return x
        return start  # unreachable for validated (non-constant) programs
    return task.program + (("add", rng.randint(1, MODULUS - 1)),)


def attempt(task: Task, skill: float, rng: random.Random):
    """The solver: correct with probability sigmoid(s - d), otherwise wrong."""
    if rng.random() < solve_probability(skill, task.difficulty):
        return reference_answer(task)
    return wrong_answer(task, rng)


def judge(task: Task, answer, verifier_fp: float, rng: random.Random) -> tuple[bool, bool]:
    """Return (accepted, truly_correct). A leaky verifier accepts some failures."""
    truly = verify(task, answer)
    accepted = truly or (verifier_fp > 0.0 and rng.random() < verifier_fp)
    return accepted, truly


# ---------------------------------------------------------------- proposer rewards
def learnability_reward(p_hat: float) -> float:
    """R-Zero / Agent0 uncertainty reward: 1 - |2p - 1|. Peaks at p = 0.5."""
    return 1.0 - abs(2.0 * p_hat - 1.0)


def azr_reward(p_hat: float) -> float:
    """Absolute Zero Eq. 4: 0 if the solver never succeeds, else 1 - p (so 0 at p = 1)."""
    return 0.0 if p_hat <= 0.0 else 1.0 - p_hat


def proposer_reward(scheme: str, p_hat: float, d: int, max_d: int) -> float:
    if scheme == "learnability":
        return learnability_reward(p_hat)
    if scheme == "azr":
        return azr_reward(p_hat)
    if scheme == "hardest":
        return d / max_d
    if scheme == "easiest":
        return (max_d - d) / (max_d - 1)
    if scheme == "random":
        return 0.0
    raise ValueError(f"unknown reward scheme {scheme!r}")


@dataclass
class Proposer:
    """Gaussian policy over difficulty: d ~ round(N(mu, sigma)), mu updated by REINFORCE.

    mu is the proposer's current belief about where the solver's frontier is. The
    update follows the score function (d - mu) / sigma, scaled by the advantage
    (reward minus a running baseline), so whichever difficulties earn above-average
    reward pull mu toward them. 'random' ignores all of this and samples uniformly.
    """

    max_d: int
    scheme: str
    mu: float = 4.0
    sigma: float = 1.5
    step: float = 0.15
    baseline: float = 0.5

    def sample(self, rng: random.Random) -> int:
        if self.scheme == "random":
            return rng.randint(1, self.max_d)
        d = int(round(rng.gauss(self.mu, self.sigma)))
        return min(max(d, 1), self.max_d)

    def update(self, d: int, reward: float) -> None:
        if self.scheme == "random":
            return
        adv = reward - self.baseline
        self.mu += self.step * adv * (d - self.mu) / self.sigma
        self.mu = min(max(self.mu, 1.0), float(self.max_d))
        self.baseline += 0.1 * (reward - self.baseline)

    def mean_difficulty(self) -> float:
        if self.scheme == "random":
            return (1 + self.max_d) / 2.0
        return self.mu


# ---------------------------------------------------------------- the loop
@dataclass
class Config:
    rounds: int = 40
    tasks_per_round: int = 24
    attempts: int = 4
    reward: str = "learnability"
    verifier_fp: float = 0.0
    max_difficulty: int = 14
    initial_skill: float = 2.0
    proposer_start: float = 4.0
    learning_rate: float = 0.015
    seed: int = DEFAULT_SEED


@dataclass
class RoundStat:
    round: int
    mean_difficulty: float
    skill: float
    observed_solve_rate: float
    true_solve_rate: float
    rejected: int
    mean_reward: float


@dataclass
class RunResult:
    scheme: str
    verifier_fp: float
    initial_skill: float
    final_skill: float
    tracking_error: float
    true_solved: int
    false_accepts: int
    zero_gradient_tasks: int
    rejected: int
    tasks: int
    mode_solved: dict[str, int]
    rounds: list[RoundStat]


def run_loop(cfg: Config) -> RunResult:
    rng = random.Random(cfg.seed)
    proposer = Proposer(cfg.max_difficulty, cfg.reward, mu=cfg.proposer_start)
    skill = cfg.initial_skill
    rounds: list[RoundStat] = []
    true_solved = false_accepts = zero_grad = rejected_total = 0
    mode_solved = {m: 0 for m in MODES}
    for r in range(1, cfg.rounds + 1):
        ds: list[int] = []
        rewards: list[float] = []
        acc_n = true_n = tried_n = rejected = 0
        for t in range(cfg.tasks_per_round):
            d = proposer.sample(rng)
            mode = MODES[t % len(MODES)]
            task = propose_task(d, mode, rng)
            ok, _reason = validate_task(task)
            if not ok:  # the executor filters degenerate proposals; they earn nothing
                rejected += 1
                proposer.update(d, 0.0)
                continue
            k_acc = k_true = 0
            for _ in range(cfg.attempts):
                accepted, truly = judge(task, attempt(task, skill, rng), cfg.verifier_fp, rng)
                k_acc += int(accepted)
                k_true += int(truly)
            p_hat = k_acc / cfg.attempts  # the proposer only sees what the verifier accepted
            reward = proposer_reward(cfg.reward, p_hat, d, cfg.max_difficulty)
            proposer.update(d, reward)
            # Solver learns from accepted solutions. Group signal 4p(1-p) is zero when
            # every attempt agrees (GRPO-style: no advantage). Accepted-but-wrong
            # solutions teach the wrong thing and pull skill down.
            signal = 4.0 * p_hat * (1.0 - p_hat)
            if k_acc > 0:
                skill += cfg.learning_rate * signal * (k_true - (k_acc - k_true)) / k_acc
                skill = min(max(skill, 0.0), cfg.max_difficulty + 1.0)
            if p_hat in (0.0, 1.0):
                zero_grad += 1
            ds.append(d)
            rewards.append(reward)
            acc_n += k_acc
            true_n += k_true
            tried_n += cfg.attempts
            true_solved += k_true
            false_accepts += k_acc - k_true
            mode_solved[mode] += k_true
        rejected_total += rejected
        rounds.append(RoundStat(
            round=r,
            mean_difficulty=statistics.fmean(ds) if ds else float("nan"),
            skill=skill,
            observed_solve_rate=acc_n / tried_n if tried_n else 0.0,
            true_solve_rate=true_n / tried_n if tried_n else 0.0,
            rejected=rejected,
            mean_reward=statistics.fmean(rewards) if rewards else 0.0,
        ))
    tracking = statistics.fmean(abs(s.mean_difficulty - s.skill) for s in rounds) if rounds else 0.0
    return RunResult(
        scheme=cfg.reward, verifier_fp=cfg.verifier_fp, initial_skill=cfg.initial_skill,
        final_skill=skill, tracking_error=tracking, true_solved=true_solved,
        false_accepts=false_accepts, zero_gradient_tasks=zero_grad, rejected=rejected_total,
        tasks=cfg.rounds * cfg.tasks_per_round, mode_solved=mode_solved, rounds=rounds,
    )


# ---------------------------------------------------------------- reporting
def round_table(result: RunResult, cfg: Config) -> list[str]:
    lines = [f"  {'round':>5}  {'mean d':>6}  {'skill':>6}  {'d-s':>6}  {'obs solve':>9}  "
             f"{'true solve':>10}  {'reject':>6}  {'reward':>6}"]
    step = max(1, cfg.rounds // 10)
    for st in result.rounds:
        if st.round == cfg.rounds or st.round % step == 0:
            lines.append(f"  {st.round:>5}  {st.mean_difficulty:>6.2f}  {st.skill:>6.2f}  "
                         f"{st.mean_difficulty - st.skill:>+6.2f}  {st.observed_solve_rate:>9.1%}  "
                         f"{st.true_solve_rate:>10.1%}  {st.rejected:>6}  {st.mean_reward:>6.2f}")
    return lines


def comparison_table(results: dict[str, RunResult]) -> list[str]:
    lines = [f"  {'scheme':<12} {'final s':>7} {'gain':>6} {'track|d-s|':>10} {'true solved':>11} "
             f"{'false acc':>9} {'zero-grad':>9} {'rejected':>8}"]
    for name, r in results.items():
        lines.append(f"  {name:<12} {r.final_skill:>7.2f} {r.final_skill - r.initial_skill:>+6.2f} "
                     f"{r.tracking_error:>10.2f} {r.true_solved:>11} {r.false_accepts:>9} "
                     f"{r.zero_gradient_tasks:>9} {r.rejected:>8}")
    return lines


def fp_table(results: list[RunResult]) -> list[str]:
    lines = [f"  {'verifier fp':>11} {'final s':>7} {'true solved':>11} {'false acc':>9} "
             f"{'obs solve (last)':>16} {'true solve (last)':>17} {'mean d (last)':>13}"]
    for r in results:
        last = r.rounds[-1]
        lines.append(f"  {r.verifier_fp:>11.1%} {r.final_skill:>7.2f} {r.true_solved:>11} "
                     f"{r.false_accepts:>9} {last.observed_solve_rate:>16.1%} "
                     f"{last.true_solve_rate:>17.1%} {last.mean_difficulty:>13.2f}")
    return lines


def headline(results: dict[str, RunResult], fp_runs: list[RunResult], cfg: Config) -> list[str]:
    lrn, hard, easy = results["learnability"], results["hardest"], results["easiest"]
    rnd, azr = results["random"], results["azr"]
    best = max(results.values(), key=lambda r: r.final_skill)
    verb = "beats" if lrn.final_skill > max(hard.final_skill, easy.final_skill) else "does not beat"
    lines = [
        f"Learnability reward {verb} 'hardest' and 'easiest': final skill {lrn.final_skill:.2f} "
        f"vs {hard.final_skill:.2f} and {easy.final_skill:.2f} (all start at {cfg.initial_skill:.2f}; "
        f"ceiling is difficulty {cfg.max_difficulty}).",
        f"Learnability proposals stayed within {lrn.tracking_error:.2f} difficulty levels of the solver's "
        f"skill on average; random stayed within {rnd.tracking_error:.2f} and spent "
        f"{rnd.zero_gradient_tasks / max(1, rnd.tasks - rnd.rejected):.1%} of its valid tasks on "
        f"zero-gradient groups (all fail or all pass).",
        f"'hardest' produced {hard.true_solved} verified solutions out of {hard.tasks * cfg.attempts} attempts; "
        f"'easiest' produced {easy.true_solved} but plateaued at skill {easy.final_skill:.2f} because "
        f"{easy.zero_gradient_tasks / max(1, easy.tasks - easy.rejected):.1%} of its groups were all-pass.",
        f"AZR's asymmetric reward (0 at p=0, else 1-p) ended at {azr.final_skill:.2f} with tracking error "
        f"{azr.tracking_error:.2f}; the symmetric tent ended at {lrn.final_skill:.2f}.",
    ]
    if len(fp_runs) >= 2:
        base, worst = fp_runs[0], fp_runs[-1]
        direction = "cut" if worst.final_skill < base.final_skill else "did not cut"
        lines.append(
            f"A verifier that wrongly accepts {worst.verifier_fp:.1%} of failures {direction} final skill "
            f"from {base.final_skill:.2f} to {worst.final_skill:.2f} under '{cfg.reward}'; it let through "
            f"{worst.false_accepts} false positives and the observed solve rate "
            f"({worst.rounds[-1].observed_solve_rate:.1%}) overstated the true one "
            f"({worst.rounds[-1].true_solve_rate:.1%})."
        )
    lines.append(f"Best scheme at seed {cfg.seed}: '{best.scheme}' (final skill {best.final_skill:.2f}).")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rounds", type=int, default=40, help="self-play rounds (default: %(default)s)")
    parser.add_argument("--reward", choices=REWARD_SCHEMES, default="learnability",
                        help="proposer reward for the detailed run and the fp contrast (default: %(default)s)")
    parser.add_argument("--tasks-per-round", type=int, default=24,
                        help="tasks proposed per round (default: %(default)s)")
    parser.add_argument("--attempts", type=int, default=4,
                        help="solver attempts per task, the GRPO-style group size (default: %(default)s)")
    parser.add_argument("--verifier-fp", type=float, default=0.0,
                        help="probability the executor wrongly accepts a failed attempt (default: %(default)s)")
    parser.add_argument("--max-difficulty", type=int, default=14,
                        help="longest program the proposer may ask for (default: %(default)s)")
    parser.add_argument("--proposer-start", type=float, default=4.0,
                        help="difficulty the proposer believes in at round 1 (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write a JSON summary")
    args = parser.parse_args()

    base = Config(rounds=args.rounds, tasks_per_round=args.tasks_per_round, attempts=args.attempts,
                  reward=args.reward, verifier_fp=args.verifier_fp,
                  max_difficulty=args.max_difficulty, proposer_start=args.proposer_start, seed=args.seed)

    print("=" * 78)
    print("ZERO-DATA SELF-PLAY: proposer / executor / solver (Phase 20, Lesson 07)")
    print("=" * 78)
    print(f"  rounds={base.rounds} tasks/round={base.tasks_per_round} attempts/task={base.attempts} "
          f"max_d={base.max_difficulty} seed={base.seed}")
    print(f"  solver: p(solve) = sigmoid(s - d), s0={base.initial_skill:.2f}, lr={base.learning_rate}")
    print(f"  proposer: d ~ round(N(mu, 1.5)), mu0={base.proposer_start:.2f}, REINFORCE on mu")
    print(f"  verifier false-positive rate: {base.verifier_fp:.1%}")

    detail = run_loop(base)
    print(f"\nRound-by-round, proposer reward = '{base.reward}'")
    for line in round_table(detail, base):
        print(line)
    print(f"  verified solutions by task mode: " +
          ", ".join(f"{m} {n}" for m, n in detail.mode_solved.items()))

    print(f"\nComparison across proposer rewards (same seed, same verifier fp)")
    comparison = {s: run_loop(Config(**{**asdict(base), "reward": s})) for s in REWARD_SCHEMES}
    for line in comparison_table(comparison):
        print(line)

    print(f"\nContrast: leaky verifier under '{base.reward}'")
    fp_levels = sorted({0.0, 0.10, 0.25, base.verifier_fp})
    fp_runs = [run_loop(Config(**{**asdict(base), "verifier_fp": fp})) for fp in fp_levels]
    for line in fp_table(fp_runs):
        print(line)

    print()
    print("=" * 78)
    print("HEADLINE")
    print("-" * 78)
    for line in headline(comparison, fp_runs, base):
        print(f"  {line}")

    if args.out:
        summary = {
            "config": asdict(base),
            "comparison": {s: {k: v for k, v in asdict(r).items() if k != "rounds"}
                           for s, r in comparison.items()},
            "verifier_fp_sweep": [{k: v for k, v in asdict(r).items() if k != "rounds"} for r in fp_runs],
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
