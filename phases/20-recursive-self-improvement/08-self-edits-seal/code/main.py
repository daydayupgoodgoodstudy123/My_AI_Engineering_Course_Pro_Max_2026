"""SEAL-style self-edit outer-loop simulator — stdlib Python.

A toy logistic model learns a sequence of "knowledge tasks". It never trains on
the raw facts directly: a self-edit policy picks a strategy from a bank
(paraphrase-augment, implication-expand, high-lr, low-lr, replay-mix, ...) that
rewrites the training batch and hyperparameters; an inner loop applies gradient
steps; an outer ReST-EM loop keeps the top-k self-edits by held-out reward and
reinforces their strategies. Tracks new-task accuracy and forgetting of old tasks.
Usage: python main.py [--tasks 6] [--edits-per-task 10] [--steps 30] [--seed 26]
       [--outer rest-em|fixed-random] [--replay off|on] [--reward new|anchored]
See docs/en.md (Phase 20, Lesson 08).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_SEED = 26
SHARED = 4          # shared "category" features, used by every task with task-specific signs
STYLE = 4           # phrasing features; the truth never depends on them
LEAVES = 2          # task-specific features per task (one positive, one negative)
FACTS_PER_TASK = 12  # a "passage" states twelve facts
QUESTIONS_PER_TASK = 100
PARENT_DROP_P = 0.9   # a passage states the leaf but omits the implied category this often
CATEGORY_W = 1.0      # |weight| of each shared category in the teacher; leaves are +/-2
BASE_LR = 1.0
PIPELINE_REPLAY = 12  # replay examples the pipeline forces into every batch when --replay on
POLICY_MIX = 0.5      # ReST-EM M-step: move this far toward the survivors' empirical distribution
EXPLORE = 0.3         # candidates are drawn from (1-EXPLORE)*policy + EXPLORE*uniform; deployment from the policy


# ----------------------------------------------------------------------------
# Feature layout, teacher (ground truth) and data
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Layout:
    """Index bookkeeping for the hand-made binary feature vector."""

    tasks: int

    @property
    def dim(self) -> int:
        return SHARED + LEAVES * self.tasks + self.tasks + STYLE

    def leaf(self, task: int, k: int) -> int:
        return SHARED + LEAVES * task + k

    def topic(self, task: int) -> int:
        return SHARED + LEAVES * self.tasks + task

    def style(self, j: int) -> int:
        return SHARED + LEAVES * self.tasks + self.tasks + j

    def parent_of(self, task: int, k: int) -> int:
        """Implication rule: leaf L_{task,k} implies shared category P_{(task+k) mod SHARED}."""
        return (task + k) % SHARED


@dataclass(frozen=True)
class Example:
    x: tuple[int, ...]
    y: int
    task: int


@dataclass(frozen=True)
class Teacher:
    task: int
    w: tuple[float, ...]
    b: float

    def label(self, x: tuple[int, ...]) -> int:
        return 1 if sum(wi * xi for wi, xi in zip(self.w, x)) + self.b > 0 else 0


@dataclass
class Task:
    idx: int
    teacher: Teacher
    facts: list[Example]       # raw passage facts: implied categories often omitted, one style
    questions: list[Example]   # held-out "no-passage" questions: complete, fresh style


def make_teacher(layout: Layout, task: int, rng: random.Random) -> Teacher:
    w = [0.0] * layout.dim
    for j in range(SHARED):
        w[j] = rng.choice((-CATEGORY_W, CATEGORY_W))   # categories mean different things per topic
    w[layout.leaf(task, 0)] = 2.0
    w[layout.leaf(task, 1)] = -2.0
    return Teacher(task, tuple(w), -0.5)        # half-integer bias: no ties


def closure(x: tuple[int, ...], layout: Layout) -> tuple[int, ...]:
    """Turn on every category implied by a present leaf (penguin => bird)."""
    out = list(x)
    for t in range(layout.tasks):
        for k in range(LEAVES):
            if out[layout.leaf(t, k)]:
                out[layout.parent_of(t, k)] = 1
    return tuple(out)


def restyle(x: tuple[int, ...], layout: Layout, rng: random.Random) -> tuple[int, ...]:
    out = list(x)
    for j in range(STYLE):
        out[layout.style(j)] = 1 if rng.random() < 0.5 else 0
    return tuple(out)


def sample_complete(layout: Layout, teacher: Teacher, rng: random.Random) -> Example:
    x = [0] * layout.dim
    for k in range(LEAVES):
        x[layout.leaf(teacher.task, k)] = 1 if rng.random() < 0.5 else 0
    for j in range(SHARED):
        x[j] = 1 if rng.random() < 0.35 else 0
    x[layout.topic(teacher.task)] = 1
    xc = restyle(closure(tuple(x), layout), layout, rng)
    return Example(xc, teacher.label(xc), teacher.task)


def write_as_passage(ex: Example, layout: Layout, passage_style: tuple[int, ...],
                     rng: random.Random) -> Example:
    """The passage states the leaf but usually omits the category it implies; one house style."""
    x = list(ex.x)
    for k in range(LEAVES):
        if x[layout.leaf(ex.task, k)] and rng.random() < PARENT_DROP_P:
            x[layout.parent_of(ex.task, k)] = 0
    for j in range(STYLE):
        x[layout.style(j)] = passage_style[j]
    return Example(tuple(x), ex.y, ex.task)   # label is still the truth about the complete fact


def make_world(n_tasks: int, seed: int) -> tuple[Layout, list[Task]]:
    rng = random.Random(seed)
    layout = Layout(n_tasks)
    tasks: list[Task] = []
    for t in range(n_tasks):
        teacher = make_teacher(layout, t, rng)
        style = tuple(1 if rng.random() < 0.5 else 0 for _ in range(STYLE))
        facts = [write_as_passage(sample_complete(layout, teacher, rng), layout, style, rng)
                 for _ in range(FACTS_PER_TASK)]
        questions = [sample_complete(layout, teacher, rng) for _ in range(QUESTIONS_PER_TASK)]
        tasks.append(Task(t, teacher, facts, questions))
    return layout, tasks


# ----------------------------------------------------------------------------
# Student model and inner loop
# ----------------------------------------------------------------------------
@dataclass
class Model:
    w: list[float]
    b: float = 0.0

    def copy(self) -> "Model":
        return Model(list(self.w), self.b)

    def prob(self, x: tuple[int, ...]) -> float:
        z = sum(wi * xi for wi, xi in zip(self.w, x)) + self.b
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        ez = math.exp(z)
        return ez / (1.0 + ez)


def log_loss(model: Model, batch: list[Example]) -> float:
    eps = 1e-12
    total = 0.0
    for ex in batch:
        p = min(max(model.prob(ex.x), eps), 1 - eps)
        total += -math.log(p) if ex.y else -math.log(1 - p)
    return total / len(batch)


def sgd_step(model: Model, batch: list[Example], lr: float) -> None:
    """One full-batch gradient step on mean log-loss (in place)."""
    grad_w = [0.0] * len(model.w)
    grad_b = 0.0
    inv = 1.0 / len(batch)
    for ex in batch:
        err = (model.prob(ex.x) - ex.y) * inv
        grad_b += err
        for i, xi in enumerate(ex.x):
            if xi:
                grad_w[i] += err * xi
    for i in range(len(model.w)):
        model.w[i] -= lr * grad_w[i]
    model.b -= lr * grad_b


def train(model: Model, batch: list[Example], steps: int, lr: float) -> Model:
    out = model.copy()
    for _ in range(steps):
        sgd_step(out, batch, lr)
    return out


def accuracy(model: Model, examples: list[Example]) -> float:
    hits = sum(1 for ex in examples if (model.prob(ex.x) >= 0.5) == bool(ex.y))
    return hits / len(examples)


# ----------------------------------------------------------------------------
# Self-edit bank and policy
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Strategy:
    name: str
    lr_mult: float = 1.0
    paraphrases: int = 0      # extra copies per fact with re-randomised style
    implication: bool = False  # add the closure (implied categories) of each fact
    replay: int = 0           # earlier-task facts mixed into the batch


BANK: tuple[Strategy, ...] = (
    Strategy("raw"),
    Strategy("paraphrase-augment", paraphrases=3),
    Strategy("implication-expand", implication=True),
    Strategy("para+impl", paraphrases=3, implication=True),
    Strategy("high-lr", lr_mult=3.0),
    Strategy("low-lr", lr_mult=0.3),
    Strategy("replay-mix", replay=12),
)


def build_batch(strategy: Strategy, task: Task, buffer: list[Example], layout: Layout,
                rng: random.Random, pipeline_replay: int) -> list[Example]:
    """Apply a self-edit: rewrite the passage into a training batch. Labels are never touched."""
    batch = list(task.facts)
    if strategy.paraphrases:
        for ex in task.facts:
            for _ in range(strategy.paraphrases):
                batch.append(Example(restyle(ex.x, layout, rng), ex.y, ex.task))
    if strategy.implication:
        for ex in task.facts:
            batch.append(Example(closure(ex.x, layout), ex.y, ex.task))
    n_replay = min(strategy.replay + pipeline_replay, len(buffer))
    if n_replay:
        batch.extend(rng.sample(buffer, n_replay))
    return batch


@dataclass
class SelfEditPolicy:
    """Categorical policy over the bank. ReST-EM M-step: after filtering, fit the policy to the
    survivors; we model that fit as moving the probabilities POLICY_MIX of the way toward the
    survivors' empirical distribution (a behaviour-cloning step with a learning rate)."""

    probs_: list[float] = field(default_factory=lambda: [1.0 / len(BANK)] * len(BANK))

    def probs(self) -> list[float]:
        return list(self.probs_)

    def sample(self, rng: random.Random) -> Strategy:
        return rng.choices(BANK, weights=self.probs_, k=1)[0]

    def reinforce(self, kept: list[Strategy]) -> None:
        if not kept:
            return
        empirical = [sum(1 for s in kept if s.name == b.name) / len(kept) for b in BANK]
        self.probs_ = [(1 - POLICY_MIX) * p + POLICY_MIX * e for p, e in zip(self.probs_, empirical)]

    def explore(self, rng: random.Random) -> Strategy:
        """Training-time sampling: mostly the policy, partly uniform, so no strategy dies untested."""
        weights = [(1 - EXPLORE) * p + EXPLORE / len(BANK) for p in self.probs_]
        return rng.choices(BANK, weights=weights, k=1)[0]


# ----------------------------------------------------------------------------
# Outer loop
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Config:
    tasks: int = 6
    edits: int = 10
    steps: int = 30
    seed: int = DEFAULT_SEED
    outer: str = "rest-em"      # or "fixed-random"
    replay: str = "off"         # or "on": pipeline forces replay into every batch
    reward: str = "new"         # or "anchored": new-task accuracy minus regression on earlier tasks


@dataclass
class TaskResult:
    task: int
    strategy: str
    new_acc: float
    old_avg: Optional[float]
    forgetting: Optional[float]   # mean(peak_j - current_j) over earlier tasks, in points
    oracle: float                 # best new-task accuracy among the sampled self-edits
    kept: list[str]


@dataclass
class RunResult:
    cfg: Config
    per_task: list[TaskResult]
    policy_probs: list[float]
    deployed_counts: dict[str, int]

    @property
    def mean_new_acc(self) -> float:
        return statistics.fmean(r.new_acc for r in self.per_task)

    @property
    def final_old_avg(self) -> Optional[float]:
        return self.per_task[-1].old_avg

    @property
    def final_forgetting(self) -> Optional[float]:
        return self.per_task[-1].forgetting

    @property
    def mean_forgetting(self) -> Optional[float]:
        vals = [r.forgetting for r in self.per_task if r.forgetting is not None]
        return statistics.fmean(vals) if vals else None


def run(cfg: Config) -> RunResult:
    layout, tasks = make_world(cfg.tasks, cfg.seed)
    rng = random.Random(cfg.seed + 1000)   # same start for every config: differences are mechanism
    model = Model([0.0] * layout.dim)
    policy = SelfEditPolicy()
    buffer: list[Example] = []
    peaks: dict[int, float] = {}
    results: list[TaskResult] = []
    deployed_counts: dict[str, int] = {s.name: 0 for s in BANK}
    pipe = PIPELINE_REPLAY if cfg.replay == "on" else 0
    k_keep = max(1, cfg.edits // 4)

    def pick(r: random.Random, training: bool) -> Strategy:
        if cfg.outer != "rest-em":
            return r.choice(BANK)
        return policy.explore(r) if training else policy.sample(r)

    def old_average(m: Model, upto: int) -> Optional[float]:
        if upto == 0:
            return None
        return statistics.fmean(accuracy(m, tasks[j].questions) for j in range(upto))

    def forgetting_pts(m: Model, upto: int) -> Optional[float]:
        """Mean drop, in points, from each earlier task's peak accuracy to its accuracy under m."""
        if upto == 0:
            return None
        return statistics.fmean((peaks[j] - accuracy(m, tasks[j].questions)) * 100 for j in range(upto))

    for task in tasks:
        # --- RL training step: sample self-edits, apply each in a sandbox copy, score them
        candidates = []
        for i in range(cfg.edits):
            strat = pick(rng, training=True)
            batch = build_batch(strat, task, buffer, layout, rng, pipe)
            trial = train(model, batch, cfg.steps, BASE_LR * strat.lr_mult)
            new_acc = accuracy(trial, task.questions)
            reward = new_acc
            if cfg.reward == "anchored":
                regression = forgetting_pts(trial, task.idx)
                reward = new_acc - (regression or 0.0) / 100   # every point lost on an anchor costs a point
            candidates.append((reward, -i, strat, new_acc))
        candidates.sort(reverse=True)
        kept = [c[2] for c in candidates[:k_keep]]
        if cfg.outer == "rest-em":
            policy.reinforce(kept)
        oracle = max(c[3] for c in candidates)

        # --- deployment: ONE self-edit from the (updated) policy changes the real weights
        strat = pick(rng, training=False)
        batch = build_batch(strat, task, buffer, layout, rng, pipe)
        model = train(model, batch, cfg.steps, BASE_LR * strat.lr_mult)
        deployed_counts[strat.name] += 1

        new_acc = accuracy(model, task.questions)
        old_avg = old_average(model, task.idx)
        forgetting = forgetting_pts(model, task.idx)
        peaks[task.idx] = new_acc
        buffer.extend(task.facts)
        results.append(TaskResult(task.idx, strat.name, new_acc, old_avg, forgetting, oracle,
                                  [s.name for s in kept]))
    return RunResult(cfg, results, policy.probs(), deployed_counts)


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------
def fmt_pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.1%}"


def fmt_pts(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:+.1f}"


def print_run(res: RunResult) -> None:
    cfg = res.cfg
    print(f"\nPer-task log (outer={cfg.outer}, replay={cfg.replay}, reward={cfg.reward})")
    print(f"  {'task':>4}  {'deployed self-edit':<20}  {'new-acc':>7}  {'old-avg':>7}  "
          f"{'forget':>7}  {'oracle':>7}  kept by ReST-EM filter")
    for r in res.per_task:
        print(f"  {r.task:>4}  {r.strategy:<20}  {fmt_pct(r.new_acc):>7}  {fmt_pct(r.old_avg):>7}  "
              f"{fmt_pts(r.forgetting):>7}  {fmt_pct(r.oracle):>7}  {', '.join(r.kept)}")
    print(f"  mean new-task accuracy {res.mean_new_acc:.1%} | final old-task average "
          f"{fmt_pct(res.final_old_avg)} | final forgetting {fmt_pts(res.final_forgetting)} pts")
    print("\n  Self-edit policy after the last task (probability of sampling each strategy):")
    for s, p in zip(BANK, res.policy_probs):
        bar = "#" * int(round(p * 40))
        print(f"    {s.name:<20} {p:>6.1%}  {bar}")
    deployed = ", ".join(f"{n}x{c}" for n, c in res.deployed_counts.items() if c)
    print(f"  Deployed strategies: {deployed}")


def grid(cfg: Config) -> dict[tuple[str, str], RunResult]:
    out = {}
    for outer in ("fixed-random", "rest-em"):
        for replay in ("off", "on"):
            out[(outer, replay)] = run(Config(cfg.tasks, cfg.edits, cfg.steps, cfg.seed,
                                              outer, replay, cfg.reward))
    return out


def print_grid(g: dict[tuple[str, str], RunResult], seed: int) -> None:
    print(f"\nContrast grid at seed {seed} (identical tasks and RNG start; only the mechanism differs)")
    print(f"  {'outer':<13} {'replay':<7} {'mean new-acc':>12} {'final old-avg':>13} "
          f"{'mean forget':>12} {'final forget':>13}")
    for (outer, replay), r in g.items():
        print(f"  {outer:<13} {replay:<7} {r.mean_new_acc:>12.1%} {fmt_pct(r.final_old_avg):>13} "
              f"{fmt_pts(r.mean_forgetting):>12} {fmt_pts(r.final_forgetting):>13}")
    print("  (forgetting = mean drop, in points, from each earlier task's peak accuracy; "
          "negative = earlier tasks improved)")


def monte_carlo(cfg: Config, trials: int) -> dict[str, object]:
    keys = (("fixed-random", "off"), ("rest-em", "off"), ("fixed-random", "on"), ("rest-em", "on"))
    lifts: list[float] = []
    forget_up: list[bool] = []
    reductions: list[float] = []
    forget = {key: [] for key in keys}
    for s in range(cfg.seed, cfg.seed + trials):
        g = grid(Config(cfg.tasks, cfg.edits, cfg.steps, s, cfg.outer, cfg.replay, cfg.reward))
        ro, rr, rn = g[("fixed-random", "off")], g[("rest-em", "off")], g[("rest-em", "on")]
        lifts.append((rr.mean_new_acc - ro.mean_new_acc) * 100)
        if rr.mean_forgetting is not None and ro.mean_forgetting is not None:
            forget_up.append(rr.mean_forgetting > ro.mean_forgetting)
            reductions.append(rr.mean_forgetting - rn.mean_forgetting)
        for key, r in g.items():
            if r.mean_forgetting is not None:
                forget[key].append(r.mean_forgetting)
    return {
        "trials": trials,
        "lift_wins": sum(1 for v in lifts if v > 0),
        "lift_median": statistics.median(lifts),
        "forget_up": sum(forget_up),
        "replay_wins": sum(1 for v in reductions if v > 0),
        "replay_median": statistics.median(reductions) if reductions else None,
        "forget_median": {f"{k[0]}/{k[1]}": (statistics.median(v) if v else None)
                          for k, v in forget.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", type=int, default=6,
                        help="knowledge tasks learned in sequence (default: %(default)s)")
    parser.add_argument("--edits-per-task", type=int, default=10,
                        help="self-edits sampled and scored per task (default: %(default)s)")
    parser.add_argument("--steps", type=int, default=30,
                        help="inner-loop gradient steps per self-edit (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--outer", choices=("rest-em", "fixed-random"), default="rest-em",
                        help="outer loop: ReST-EM top-k reinforcement, or a fixed uniform self-edit policy")
    parser.add_argument("--replay", choices=("off", "on"), default="off",
                        help="pipeline-enforced replay of earlier tasks in every batch (outside the policy's control)")
    parser.add_argument("--reward", choices=("new", "anchored"), default="new",
                        help="outer reward: new-task accuracy only, or new-task accuracy minus the "
                             "points lost on earlier tasks (anchor regression penalty)")
    parser.add_argument("--trials", type=int, default=5,
                        help="seeds for the Monte-Carlo check (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write a JSON summary")
    args = parser.parse_args()
    if min(args.tasks, args.edits_per_task, args.steps, args.trials) < 1:
        parser.error("--tasks, --edits-per-task, --steps and --trials must be >= 1")

    cfg = Config(args.tasks, args.edits_per_task, args.steps, args.seed, args.outer, args.replay, args.reward)
    layout = Layout(cfg.tasks)
    print("=" * 78)
    print("SELF-EDITS TO WEIGHTS — SEAL-STYLE OUTER LOOP (Phase 20, Lesson 08)")
    print("=" * 78)
    print(f"config: tasks={cfg.tasks} edits/task={cfg.edits} steps={cfg.steps} seed={cfg.seed} "
          f"outer={cfg.outer} replay={cfg.replay} reward={cfg.reward}")
    print(f"features: {SHARED} shared categories + {LEAVES} leaves/task + 1 topic/task + {STYLE} style "
          f"= {layout.dim} weights; {FACTS_PER_TASK} facts and {QUESTIONS_PER_TASK} held-out questions per task")
    print(f"bank: {', '.join(s.name for s in BANK)}")
    print(f"outer loop: sample {cfg.edits} self-edits, keep top-{max(1, cfg.edits // 4)} by reward, "
          f"move the policy {POLICY_MIX:.0%} toward the survivors; then deploy ONE self-edit from the policy")

    main_run = run(cfg)
    print_run(main_run)

    g = grid(cfg)
    print_grid(g, cfg.seed)

    mc = monte_carlo(cfg, args.trials)
    n = mc["trials"]
    print(f"\nMonte-Carlo over {n} seeds ({cfg.seed}..{cfg.seed + n - 1}), same flags except outer/replay")
    print(f"  rest-em beats fixed-random on mean new-acc (replay off): "
          f"{mc['lift_wins']}/{n} ({mc['lift_wins'] / n:.1%}), median lift {mc['lift_median']:+.1f} pts")
    if mc["replay_median"] is not None:
        print(f"  rest-em forgets MORE than fixed-random (replay off):     "
              f"{mc['forget_up']}/{n} ({mc['forget_up'] / n:.1%})")
        print(f"  replay on reduces mean forgetting (rest-em):             "
              f"{mc['replay_wins']}/{n} ({mc['replay_wins'] / n:.1%}), median reduction {mc['replay_median']:+.1f} pts")
        fm = mc["forget_median"]
        print("  median mean-forgetting (pts): " + " | ".join(f"{k} {v:+.1f}" for k, v in fm.items() if v is not None))

    ro, rr, rro = g[("fixed-random", "off")], g[("rest-em", "off")], g[("rest-em", "on")]
    top = max(zip(BANK, rr.policy_probs), key=lambda t: t[1])
    protective = sum(p for s, p in zip(BANK, main_run.policy_probs) if s.name in ("low-lr", "replay-mix"))
    print("\n" + "=" * 78)
    print("HEADLINE")
    print("-" * 78)
    print(f"  At seed {cfg.seed}, the ReST-EM outer loop moves mean new-task accuracy from "
          f"{ro.mean_new_acc:.1%} (fixed-random self-edits) to {rr.mean_new_acc:.1%}.")
    if rr.mean_forgetting is not None and ro.mean_forgetting is not None:
        verb = "raises" if rr.mean_forgetting > ro.mean_forgetting else "moves"
        print(f"  The same loop {verb} mean forgetting of earlier tasks from {ro.mean_forgetting:+.1f} to "
              f"{rr.mean_forgetting:+.1f} points; with pipeline replay on it is {rro.mean_forgetting:+.1f} points "
              f"at {rro.mean_new_acc:.1%} new-task accuracy.")
    print(f"  Under reward=new the policy puts {top[1]:.1%} of its mass on '{top[0].name}' "
          f"(uniform would be {1 / len(BANK):.1%}); in this run (reward={cfg.reward}) the protective "
          f"strategies low-lr + replay-mix hold {protective:.1%}.")
    print(f"  Across {n} seeds, rest-em beat fixed-random {mc['lift_wins']}/{n} times "
          f"(median {mc['lift_median']:+.1f} pts)" +
          (f", forgot more in {mc['forget_up']}/{n}, and replay cut forgetting {mc['replay_wins']}/{n} times "
           f"(median {mc['replay_median']:+.1f} pts)." if mc["replay_median"] is not None else "."))
    print(f"  Compute: every scored self-edit is one finetune; this run spent {cfg.tasks * (cfg.edits + 1)} "
          f"finetunes to deploy {cfg.tasks} updates (SEAL reports 30-45 s per self-edit evaluation).")

    if args.out:
        summary = {
            "config": cfg.__dict__,
            "per_task": [r.__dict__ for r in main_run.per_task],
            "policy": {s.name: p for s, p in zip(BANK, main_run.policy_probs)},
            "grid": {f"{k[0]}/{k[1]}": {"mean_new_acc": r.mean_new_acc, "final_old_avg": r.final_old_avg,
                                        "mean_forgetting": r.mean_forgetting,
                                        "final_forgetting": r.final_forgetting} for k, r in g.items()},
            "monte_carlo": mc,
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
