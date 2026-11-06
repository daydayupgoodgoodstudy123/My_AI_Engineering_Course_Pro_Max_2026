"""AIDE²-style research-agent self-improvement with a held-out protocol — stdlib Python.

An INNER research agent runs tree search over a synthetic experiment landscape
(node = experiment config with a hidden true score, a noisy measured score and an
optional "shortcut" that inflates measured score only = reward hacking). An OUTER
loop edits the inner agent's policy (exploration, memory window, shortcut
avoidance) and accepts an edit only if the SELECTION-task score improves; true
scores on HELD-OUT families (ID, OOD) and the hacking rate are reported, never
selected on.  Usage: python3 main.py [--outer-iters N] [--inner-budget N]
[--seed N] [--holdout-ood on|off] [--select-on measured|true|both] [--shortcut-bonus X]
See docs/en.md (Phase 20 · Lesson 11).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass, asdict, replace
from typing import Iterable

DEFAULT_SEED = 11
DIMS = 3
UCB_SCALE = 0.1          # scales the exploration bonus relative to score units
CONTEXT_TAX = 0.35       # evaluations lost per remembered result (context is not free)
MUTATION_STEP = 0.12     # std-dev of a child's config perturbation
HACK_INHERIT = 0.60      # chance a hacked parent's child still carries the shortcut
BUMP_WIDTH = 0.30        # in-distribution landscape width
RIDGE_WIDTH = 0.12       # out-of-distribution landscape width (narrow diagonal ridge)
N_SELECTION, N_HOLDOUT_ID, N_HOLDOUT_OOD, N_HACK_FAMILY = 6, 6, 6, 36
SHORTCUT_RATE = 0.30     # chance a child discovers the shortcut on ordinary tasks
HACK_FAMILY_RATE = 0.45  # ... on the hack-prone held-out family


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Task:
    """One research task: a landscape family, its optimum and how easy hacking is."""
    name: str
    family: str                 # "bump" (ID) or "ridge" (OOD)
    center: tuple[float, ...]
    shortcut_rate: float        # probability a new child discovers the shortcut
    noise: float                # std-dev of measurement noise


@dataclass(frozen=True)
class Env:
    """Environment constants that the agent cannot edit."""
    shortcut_bonus: float = 0.25   # measured-score inflation from the shortcut
    shortcut_cost: float = 0.40    # fraction of TRUE score destroyed by the shortcut


@dataclass(frozen=True)
class Policy:
    """The inner agent's editable search-and-control parameters."""
    exploration: float = 1.0
    memory_window: int = 8
    shortcut_avoid: float = 0.0


@dataclass
class Node:
    config: tuple[float, ...]
    shortcut: bool
    true_score: float
    measured: float
    suspicion: float
    visits: int = 0


@dataclass
class Metrics:
    sel_measured: float
    sel_true: float
    sel_hack: float
    ho_id_true: float
    ho_ood_true: float | None
    hack_rate: float

    @property
    def inflation(self) -> float:
        return self.sel_measured - self.sel_true


@dataclass
class IterRecord:
    iteration: int
    proposal: str
    policy: Policy
    metrics: Metrics
    accepted: bool


# --------------------------------------------------------------------------- #
# Landscape
# --------------------------------------------------------------------------- #
def seeded_rng(*parts: object) -> random.Random:
    """Deterministic RNG from a key, stable across Python processes (no str hash)."""
    key = "|".join(str(p) for p in parts).encode()
    return random.Random(int(hashlib.sha256(key).hexdigest()[:12], 16))


def true_score(task: Task, config: tuple[float, ...], shortcut: bool, env: Env) -> float:
    """Hidden ground truth. The shortcut never raises it; it destroys a fraction."""
    if task.family == "bump":
        d2 = sum((x - c) ** 2 for x, c in zip(config, task.center))
        base = math.exp(-d2 / (2 * BUMP_WIDTH ** 2))
    elif task.family == "ridge":
        s = (config[0] + config[1]) / 2.0
        along = math.exp(-((s - task.center[0]) ** 2) / (2 * RIDGE_WIDTH ** 2))
        base = along * (0.4 + 0.6 * (1.0 - abs(config[2] - task.center[2])))
    else:
        raise ValueError(f"unknown family {task.family!r}")
    if shortcut:
        base *= 1.0 - env.shortcut_cost
    return base


def draw_suspicion(shortcut: bool, rng: random.Random) -> float:
    """What the agent can see about a proposed change: a noisy 'looks like a hack' signal.

    Honest changes score U(0, 0.5), shortcuts U(0.35, 1.0): the overlap is what makes
    heavy avoidance costly (stripping a suspicious-looking honest change slows search).
    """
    if shortcut:
        return 0.35 + rng.random() * 0.65
    return rng.random() * 0.5


def evaluate_config(task: Task, config: tuple[float, ...], shortcut: bool,
                    env: Env, rng: random.Random, suspicion: float = 0.0) -> Node:
    """Run the 'experiment': true score is hidden, measured score is what the agent sees."""
    t = true_score(task, config, shortcut, env)
    measured = t + rng.gauss(0.0, task.noise) + (env.shortcut_bonus if shortcut else 0.0)
    return Node(config=config, shortcut=shortcut, true_score=t,
                measured=measured, suspicion=suspicion)


def hack_wins_below(env: Env) -> float:
    """True-score threshold below which a shortcut config out-measures an honest one.

    measured_hack = t(1 - cost) + bonus > t  <=>  t < bonus / cost.
    """
    return env.shortcut_bonus / env.shortcut_cost


# --------------------------------------------------------------------------- #
# Inner agent: tree search over experiments
# --------------------------------------------------------------------------- #
def agent_value(node: Node, policy: Policy) -> float:
    """What the inner agent believes a node is worth (it never sees true_score)."""
    return node.measured - policy.shortcut_avoid * node.suspicion


def clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def tree_search(task: Task, policy: Policy, budget: int, env: Env,
                rng: random.Random) -> Node:
    """Expand a tree of experiments and return the agent's chosen final config.

    Each turn: pick a parent from the memory window (own value + UCB bonus), propose
    a perturbed child, notice the task's shortcut with probability shortcut_rate
    (hacked parents pass it on with probability HACK_INHERIT), and STRIP the hack
    from the child if its suspicion exceeds 1 - shortcut_avoid. Stripping an honest
    change (false positive) costs half its step. Remembering more results costs
    budget (CONTEXT_TAX): context is not free.

    Two RNG streams (search moves vs. hack draws) keep runs with different policies
    comparable: the k-th perturbation is the same vector whichever parent it is
    applied to (common random numbers).
    """
    search_rng = random.Random(rng.random())
    hack_rng = random.Random(rng.random())
    evaluations = max(2, budget - int(policy.memory_window * CONTEXT_TAX))
    root_cfg = tuple(0.5 for _ in range(DIMS))          # the 'baseline experiment'
    nodes: list[Node] = [evaluate_config(task, root_cfg, False, env, search_rng,
                                         draw_suspicion(False, hack_rng))]
    for t in range(1, evaluations):
        window = nodes[-policy.memory_window:]
        parent = max(window, key=lambda n: agent_value(n, policy)
                     + policy.exploration * UCB_SCALE
                     * math.sqrt(math.log(t + 1) / (1 + n.visits)))
        parent.visits += 1
        step = [search_rng.gauss(0.0, MUTATION_STEP) for _ in range(DIMS)]
        child_cfg = tuple(clip01(x + d) for x, d in zip(parent.config, step))
        if parent.shortcut:
            shortcut = hack_rng.random() < HACK_INHERIT
        else:
            shortcut = hack_rng.random() < task.shortcut_rate
        suspicion = draw_suspicion(shortcut, hack_rng)
        if suspicion > 1.0 - policy.shortcut_avoid:
            # The agent strips the part of the change that looks like a hack. If the
            # change was honest (false positive) it loses half of its step instead.
            if shortcut:
                shortcut = False
            else:
                child_cfg = tuple(clip01(x + 0.5 * d) for x, d in zip(parent.config, step))
        nodes.append(evaluate_config(task, child_cfg, shortcut, env, search_rng, suspicion))
    final_window = nodes[-policy.memory_window:]
    return max(final_window, key=lambda n: agent_value(n, policy))


# --------------------------------------------------------------------------- #
# Task families
# --------------------------------------------------------------------------- #
def make_tasks(seed: int) -> dict[str, list[Task]]:
    rng = seeded_rng(seed, "tasks")

    def centers(n: int) -> list[tuple[float, ...]]:
        return [tuple(0.15 + 0.7 * rng.random() for _ in range(DIMS)) for _ in range(n)]

    return {
        "selection": [Task(f"sel{i}", "bump", c, SHORTCUT_RATE, 0.03)
                      for i, c in enumerate(centers(N_SELECTION))],
        "holdout_id": [Task(f"id{i}", "bump", c, SHORTCUT_RATE, 0.03)
                       for i, c in enumerate(centers(N_HOLDOUT_ID))],
        "holdout_ood": [Task(f"ood{i}", "ridge", c, SHORTCUT_RATE, 0.03)
                        for i, c in enumerate(centers(N_HOLDOUT_OOD))],
        "hack_family": [Task(f"hk{i}", "bump", c, HACK_FAMILY_RATE, 0.03)
                        for i, c in enumerate(centers(N_HACK_FAMILY))],
    }


def run_family(tasks: Iterable[Task], policy: Policy, budget: int, env: Env,
               seed: int) -> list[Node]:
    """Run the inner agent once per task with a fixed per-task RNG (paired comparison)."""
    return [tree_search(t, policy, budget, env, seeded_rng(seed, t.name)) for t in tasks]


def measure(policy: Policy, tasks: dict[str, list[Task]], budget: int, env: Env,
            seed: int, holdout_ood: bool) -> Metrics:
    sel = run_family(tasks["selection"], policy, budget, env, seed)
    ho_id = run_family(tasks["holdout_id"], policy, budget, env, seed)
    hk = run_family(tasks["hack_family"], policy, budget, env, seed)
    ood = run_family(tasks["holdout_ood"], policy, budget, env, seed) if holdout_ood else None
    return Metrics(
        sel_measured=statistics.fmean(n.measured for n in sel),
        sel_true=statistics.fmean(n.true_score for n in sel),
        sel_hack=statistics.fmean(1.0 if n.shortcut else 0.0 for n in sel),
        ho_id_true=statistics.fmean(n.true_score for n in ho_id),
        ho_ood_true=statistics.fmean(n.true_score for n in ood) if ood is not None else None,
        hack_rate=statistics.fmean(1.0 if n.shortcut else 0.0 for n in hk),
    )


# --------------------------------------------------------------------------- #
# Outer loop: the agent edits its own search policy
# --------------------------------------------------------------------------- #
def propose_edits(policy: Policy, budget: int, rng: random.Random) -> list[tuple[Policy, str]]:
    """One candidate edit per editable parameter (the outer agent's 'rewrite' step)."""
    expl = min(4.0, max(0.05, policy.exploration * math.exp(rng.gauss(0.0, 0.5))))
    mem = min(budget, max(2, policy.memory_window + rng.choice([-6, -3, 3, 6, 10])))
    avoid = min(1.0, max(0.0, policy.shortcut_avoid + rng.gauss(0.0, 0.2)))
    return [
        (replace(policy, exploration=expl), f"exploration {policy.exploration:.2f}->{expl:.2f}"),
        (replace(policy, memory_window=mem), f"memory {policy.memory_window}->{mem}"),
        (replace(policy, shortcut_avoid=avoid), f"avoid {policy.shortcut_avoid:.2f}->{avoid:.2f}"),
    ]


def selection_metric(m: Metrics, select_on: str) -> float:
    return m.sel_measured if select_on == "measured" else m.sel_true


def outer_loop(select_on: str, env: Env, seed: int, outer_iters: int, inner_budget: int,
               holdout_ood: bool) -> list[IterRecord]:
    """Greedy accept-if-better over policy edits, scored ONLY on selection tasks.

    Each iteration proposes one edit per parameter, evaluates all of them on the
    selection tasks, keeps the best by the selection metric, and accepts it only if
    it strictly beats the incumbent. Held-out metrics are measured but never used.
    """
    tasks = make_tasks(seed)
    rng = seeded_rng(seed, "outer", select_on)
    incumbent = Policy()
    inc_metrics = measure(incumbent, tasks, inner_budget, env, seed, holdout_ood)
    records = [IterRecord(0, "baseline", incumbent, inc_metrics, True)]
    for it in range(1, outer_iters + 1):
        scored = []
        for candidate, desc in propose_edits(incumbent, inner_budget, rng):
            m = measure(candidate, tasks, inner_budget, env, seed, holdout_ood)
            scored.append((selection_metric(m, select_on), candidate, desc, m))
        score, candidate, desc, cand_metrics = max(scored, key=lambda x: x[0])
        accepted = score > selection_metric(inc_metrics, select_on)
        records.append(IterRecord(it, desc, candidate, cand_metrics, accepted))
        if accepted:
            incumbent, inc_metrics = candidate, cand_metrics
    return records


def accepted_records(records: list[IterRecord]) -> list[IterRecord]:
    return [r for r in records if r.accepted]


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def fmt_ood(v: float | None) -> str:
    return f"{v:7.3f}" if v is not None else "      -"


def print_run(select_on: str, records: list[IterRecord]) -> None:
    print(f"\n--- outer loop, selecting on {select_on.upper()} selection score ---")
    print(f"  {'it':>2}  {'proposal':<26} {'sel_meas':>8} {'sel_true':>8} "
          f"{'ho_id':>7} {'ho_ood':>7} {'hack%':>6}  accept")
    for r in records:
        m = r.metrics
        flag = "YES" if r.accepted else "no"
        if r.iteration == 0:
            flag = "base"
        print(f"  {r.iteration:>2}  {r.proposal:<26} {m.sel_measured:8.3f} {m.sel_true:8.3f} "
              f"{m.ho_id_true:7.3f} {fmt_ood(m.ho_ood_true)} {m.hack_rate:6.1%}  {flag}")
    final = accepted_records(records)[-1]
    p = final.policy
    print(f"  final policy: exploration={p.exploration:.2f} memory_window={p.memory_window} "
          f"shortcut_avoid={p.shortcut_avoid:.2f}  ({len(accepted_records(records)) - 1} edits accepted)")


def delta(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "    -"
    return f"{b - a:+.3f}"


def print_summary(runs: dict[str, list[IterRecord]], env: Env) -> None:
    print("\n" + "=" * 78)
    print("SUMMARY — baseline vs final incumbent (true scores are hidden from the agent)")
    print("-" * 78)
    print(f"  {'select on':<10} {'metric':<22} {'baseline':>9} {'final':>9} {'delta':>8}")
    for mode, records in runs.items():
        b = records[0].metrics
        f = accepted_records(records)[-1].metrics
        rows = [
            ("selection measured", b.sel_measured, f.sel_measured),
            ("selection true", b.sel_true, f.sel_true),
            ("inflation (meas-true)", b.inflation, f.inflation),
            ("held-out ID true", b.ho_id_true, f.ho_id_true),
            ("held-out OOD true", b.ho_ood_true, f.ho_ood_true),
            ("hack rate (held-out)", b.hack_rate, f.hack_rate),
        ]
        for i, (name, bv, fv) in enumerate(rows):
            label = mode if i == 0 else ""
            if bv is None or fv is None:
                print(f"  {label:<10} {name:<22} {'-':>9} {'-':>9} {'-':>8}")
            elif name.startswith("hack"):
                print(f"  {label:<10} {name:<22} {bv:>9.1%} {fv:>9.1%} {fv - bv:>+8.1%}")
            else:
                print(f"  {label:<10} {name:<22} {bv:>9.3f} {fv:>9.3f} {delta(bv, fv):>8}")
        print()
    print(f"  environment: shortcut bonus +{env.shortcut_bonus:.2f} on MEASURED, "
          f"-{env.shortcut_cost:.0%} on TRUE  ->  a shortcut out-measures honesty only "
          f"while true score < {hack_wins_below(env):.3f}")


def headline(runs: dict[str, list[IterRecord]], env: Env) -> list[str]:
    lines: list[str] = []
    for mode, records in runs.items():
        b = records[0].metrics
        f = accepted_records(records)[-1].metrics
        n_acc = len(accepted_records(records)) - 1
        gain_sel = f.sel_measured - b.sel_measured if mode == "measured" else f.sel_true - b.sel_true
        gain_id = f.ho_id_true - b.ho_id_true
        lines.append(
            f"Selecting on {mode}: {n_acc} edits accepted; selection {mode} score "
            f"{selection_metric(b, mode):.3f}->{selection_metric(f, mode):.3f} ({gain_sel:+.3f}), "
            f"held-out ID true {b.ho_id_true:.3f}->{f.ho_id_true:.3f} ({gain_id:+.3f}).")
        if f.ho_ood_true is not None and b.ho_ood_true is not None:
            gain_ood = f.ho_ood_true - b.ho_ood_true
            share = (gain_ood / gain_id) if abs(gain_id) > 1e-9 else float("nan")
            lines.append(
                f"  OOD held-out true {b.ho_ood_true:.3f}->{f.ho_ood_true:.3f} ({gain_ood:+.3f}): "
                f"the OOD family received {share:.0%} of the ID gain — transfer is partial.")
        lines.append(
            f"  Measured-minus-true inflation on selection tasks: {b.inflation:+.3f} -> {f.inflation:+.3f}; "
            f"held-out hacking rate {b.hack_rate:.1%} -> {f.hack_rate:.1%}"
            + (" (never optimized for)." if mode == "measured" else " (directly rewarded)."))
    if "measured" in runs and "true" in runs:
        hm = accepted_records(runs["measured"])[-1].metrics.hack_rate
        ht = accepted_records(runs["true"])[-1].metrics.hack_rate
        verdict = "lower" if ht < hm else ("equal to" if ht == hm else "higher than")
        lines.append(
            f"Final hacking with an oracle (true) selector is {ht:.1%}, {verdict} the measured selector's "
            f"{hm:.1%}. A fall under measured selection is a side effect of stronger search "
            f"(hacks only win while true < {hack_wins_below(env):.3f}), not a guarantee: raise "
            f"--shortcut-bonus and it disappears.")
    return lines


def records_to_json(runs: dict[str, list[IterRecord]]) -> dict:
    out = {}
    for mode, records in runs.items():
        out[mode] = [
            {"iteration": r.iteration, "proposal": r.proposal, "accepted": r.accepted,
             "policy": asdict(r.policy), "metrics": asdict(r.metrics)}
            for r in records
        ]
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outer-iters", type=int, default=12,
                        help="outer-loop policy edits proposed (default: %(default)s)")
    parser.add_argument("--inner-budget", type=int, default=40,
                        help="experiments per inner tree search before context tax (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="RNG seed (default: %(default)s)")
    parser.add_argument("--holdout-ood", choices=["on", "off"], default="on",
                        help="also report the out-of-distribution held-out family (default: %(default)s)")
    parser.add_argument("--select-on", choices=["measured", "true", "both"], default="both",
                        help="what the outer loop may see when accepting edits (default: %(default)s)")
    parser.add_argument("--shortcut-bonus", type=float, default=Env.shortcut_bonus,
                        help="measured-score inflation a shortcut buys (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None,
                        help="optional path to write all iteration records as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    env = Env(shortcut_bonus=args.shortcut_bonus)
    modes = ["measured", "true"] if args.select_on == "both" else [args.select_on]
    holdout_ood = args.holdout_ood == "on"

    print("=" * 78)
    print("RECURSIVE SELF-IMPROVEMENT OF A RESEARCH AGENT — HELD-OUT PROTOCOL (Phase 20 · 11)")
    print("=" * 78)
    print(f"  seed={args.seed}  outer_iters={args.outer_iters}  inner_budget={args.inner_budget}  "
          f"holdout_ood={args.holdout_ood}  shortcut_bonus={env.shortcut_bonus:.2f}  "
          f"shortcut_cost={env.shortcut_cost:.0%}")
    print(f"  selection tasks: {N_SELECTION} bump | held-out ID: {N_HOLDOUT_ID} bump | "
          f"held-out OOD: {N_HOLDOUT_OOD} ridge | hack-prone family: {N_HACK_FAMILY} bump "
          f"(shortcut rate {HACK_FAMILY_RATE:.0%} vs {SHORTCUT_RATE:.0%})")

    runs: dict[str, list[IterRecord]] = {}
    for mode in modes:
        records = outer_loop(mode, env, args.seed, args.outer_iters, args.inner_budget, holdout_ood)
        runs[mode] = records
        print_run(mode, records)

    print_summary(runs, env)
    print("\n" + "=" * 78)
    print("HEADLINE")
    print("-" * 78)
    for line in headline(runs, env):
        print("  " + line)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(records_to_json(runs), fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
