"""Archive-tree search simulator for self-modifying agents (stdlib only).

Each archive node is an agent with a latent benchmark performance p and a
latent metaproductivity m (how good its children tend to be). Three expansion
policies spend the same node budget: latest-only (no archive), DGM-style
(sigmoid of score x novelty bonus) and HGM-style (Thompson sampling on
clade-pooled pass/fail counts, i.e. an estimate of CMP). --mismatch sets how
much of m is an independent heritable skill rather than task performance;
--meta-editable lets the improvement operator's step size evolve too.
Usage: python main.py [--budget 60] [--trials 40] [--mismatch 0.7] [--policy all] [--meta-editable] [--seed 11]
See docs/en.md (Phase 20, Lesson 10).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_SEED = 11
POLICIES = ("latest", "dgm", "hgm")
SWEEP_MISMATCH = (0.0, 0.5, 1.0)
MIN_DESCENDANTS = 3  # a node needs this many descendants before its realised CMP counts


@dataclass
class Config:
    budget: int = 60            # child agents created per trial (root not counted)
    mismatch: float = 0.7       # share of m that is an independent skill, not task performance
    tasks: int = 20             # Bernoulli benchmark tasks per evaluation
    p0: float = 0.20            # root performance (DGM started at 20.0% on SWE-bench)
    step0: float = 0.03         # improvement-operator step size at the root
    luck: float = 0.03          # sd of the random part of an edit's effect on p
    m_per_p: float = 2.0        # task-skill part of m: 0.5 + m_per_p * (p - p0)
    skill_noise: float = 0.10   # sd of the heritable self-improvement-skill random walk
    break_prob: float = 0.05    # chance an edit breaks the agent (tool use, parser...)
    break_loss: float = 0.15    # performance lost by a breaking edit (inherited by the clade)
    break_skill_loss: float = 0.25  # self-improvement skill lost by a breaking edit
    step_noise: float = 0.25    # log-sd of the step mutation when meta_editable
    meta_editable: bool = False
    dgm_lambda: float = 10.0    # DGM paper: sigmoid slope on the score
    prior: float = 1.0          # Laplace pseudo-count in the CMP estimate


@dataclass
class Node:
    id: int
    parent: Optional[int]
    depth: int
    p: float                    # latent true benchmark performance
    skill: float                # latent heritable self-improvement skill, 0..1
    m: float                    # metaproductivity actually driving the children
    step: float                 # improvement-operator step size
    successes: int
    failures: int
    broken: bool = False
    children: list[int] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Observed benchmark score: what every policy is allowed to see."""
        return self.successes / (self.successes + self.failures)


# ----------------------------------------------------------------- generative model

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def metaproductivity(p: float, skill: float, cfg: Config) -> float:
    """m = (1 - mismatch) * task-skill part + mismatch * independent skill.
    mismatch 0: being good at the task IS being good at self-modification
    (the coding-domain alignment DGM relied on). mismatch 1: unrelated."""
    from_task = clamp(0.5 + cfg.m_per_p * (p - cfg.p0), 0.0, 1.0)
    return (1.0 - cfg.mismatch) * from_task + cfg.mismatch * skill


def evaluate(rng: random.Random, p: float, tasks: int) -> tuple[int, int]:
    """Run `tasks` Bernoulli(p) benchmark tasks; return (passed, failed)."""
    passed = sum(1 for _ in range(tasks) if rng.random() < p)
    return passed, tasks - passed


def make_root(rng: random.Random, cfg: Config) -> Node:
    s, f = evaluate(rng, cfg.p0, cfg.tasks)
    return Node(id=0, parent=None, depth=0, p=cfg.p0, skill=0.5,
                m=metaproductivity(cfg.p0, 0.5, cfg), step=cfg.step0, successes=s, failures=f)


def spawn_child(rng: random.Random, parent: Node, cfg: Config, archive: list[Node]) -> Node:
    """One self-modification of `parent`: the parent's metaproductivity sets the
    expected gain, luck adds noise, headroom (1 - p) gives diminishing returns,
    and a breaking edit damages both performance and self-improvement skill."""
    headroom = (1.0 - parent.p) / (1.0 - cfg.p0)
    scale = parent.step / cfg.step0          # an improved operator moves p further per edit
    drift = 2.0 * cfg.step0 * (parent.m - 0.5)
    p = parent.p + scale * (drift + cfg.luck * rng.gauss(0.0, 1.0)) * headroom
    skill = parent.skill + cfg.skill_noise * rng.gauss(0.0, 1.0)
    broken = rng.random() < cfg.break_prob
    if broken:
        p -= cfg.break_loss
        skill -= cfg.break_skill_loss
    p = clamp(p, 0.01, 0.99)
    skill = clamp(skill, 0.0, 1.0)
    step = parent.step
    if cfg.meta_editable:
        step = clamp(parent.step * math.exp(rng.gauss(0.0, cfg.step_noise)),
                     0.25 * cfg.step0, 4.0 * cfg.step0)
    s, f = evaluate(rng, p, cfg.tasks)
    node = Node(id=len(archive), parent=parent.id, depth=parent.depth + 1, p=p, skill=skill,
                m=metaproductivity(p, skill, cfg), step=step, successes=s, failures=f, broken=broken)
    archive.append(node)
    parent.children.append(node.id)
    return node


# ----------------------------------------------------------------- clade statistics

def clade_members(archive: list[Node], node_id: int) -> list[int]:
    """Ids of the subtree rooted at node_id, including node_id (iterative DFS)."""
    out, stack = [], [node_id]
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(archive[cur].children)
    return out


def all_clade_counts(archive: list[Node]) -> list[tuple[int, int]]:
    """Pooled (passed, failed) over each node's clade, in one reverse pass.
    Ids are creation-ordered, so every parent has a smaller id than its children."""
    s = [n.successes for n in archive]
    f = [n.failures for n in archive]
    for node in reversed(archive):
        if node.parent is not None:
            s[node.parent] += s[node.id]
            f[node.parent] += f[node.id]
    return list(zip(s, f))


def cmp_estimate(successes: int, failures: int, prior: float = 1.0) -> float:
    """HGM's estimator: clade-pooled pass rate with a Laplace pseudo-count."""
    return (successes + prior) / (successes + failures + 2.0 * prior)


def realized_cmp_all(archive: list[Node]) -> list[Optional[float]]:
    """Mean true p over a node's descendants (self excluded); None for leaves."""
    n = len(archive)
    sums = [0.0] * n
    counts = [0] * n
    for node in reversed(archive):
        if node.parent is not None:
            sums[node.parent] += sums[node.id] + node.p
            counts[node.parent] += counts[node.id] + 1
    return [sums[i] / counts[i] if counts[i] else None for i in range(n)]


def descendant_counts(archive: list[Node]) -> list[int]:
    counts = [0] * len(archive)
    for node in reversed(archive):
        if node.parent is not None:
            counts[node.parent] += counts[node.id] + 1
    return counts


# ----------------------------------------------------------------- expansion policies

def novelty_bonus(n_children: int) -> float:
    """DGM paper: h_i = 1 / (1 + n_children) keeps the archive open-ended."""
    return 1.0 / (1.0 + n_children)


def dgm_weight(score: float, n_children: int, lam: float = 10.0) -> float:
    """DGM paper: parent weight = sigmoid(lam * (score - 0.5)) * novelty bonus."""
    return sigmoid(lam * (score - 0.5)) * novelty_bonus(n_children)


def choose_parent(policy: str, archive: list[Node], rng: random.Random, cfg: Config,
                  remaining: int, total: int) -> Node:
    if policy == "latest":
        return archive[-1]
    if policy == "dgm":
        weights = [dgm_weight(n.score, len(n.children), cfg.dgm_lambda) for n in archive]
        return rng.choices(archive, weights=weights, k=1)[0]
    if policy == "hgm":
        # Thompson sampling on clade-pooled counts; tau = B / b sharpens toward
        # exploitation as the remaining budget b shrinks (HGM paper, Sec. 3.3).
        tau = total / max(1, remaining)
        best, best_draw = archive[0], -1.0
        for node, (s, f) in zip(archive, all_clade_counts(archive)):
            draw = rng.betavariate(tau * (cfg.prior + s), tau * (cfg.prior + f))
            if draw > best_draw:
                best, best_draw = node, draw
        return best
    raise ValueError(f"unknown policy {policy!r}")


def run_trial(policy: str, cfg: Config, rng: random.Random) -> list[Node]:
    archive = [make_root(rng, cfg)]
    for i in range(cfg.budget):
        parent = choose_parent(policy, archive, rng, cfg, cfg.budget - i, cfg.budget)
        spawn_child(rng, parent, cfg, archive)
    return archive


# ----------------------------------------------------------------- tree metrics

def best_node(archive: list[Node]) -> Node:
    return max(archive, key=lambda n: (n.p, -n.id))


def lineage(archive: list[Node], node_id: int) -> list[int]:
    out = []
    cur: Optional[int] = node_id
    while cur is not None:
        out.append(cur)
        cur = archive[cur].parent
    return out


def dead_clade_waste(archive: list[Node]) -> float:
    """Fraction of created nodes whose clade never beat the best true p that
    already existed when the node was created (budget spent on dead ends)."""
    clade_max = [n.p for n in archive]
    for node in reversed(archive):
        if node.parent is not None:
            clade_max[node.parent] = max(clade_max[node.parent], clade_max[node.id])
    best_before, wasted = -1.0, 0
    for node in archive:
        if node.parent is not None and clade_max[node.id] <= best_before:
            wasted += 1
        best_before = max(best_before, node.p)
    return wasted / (len(archive) - 1) if len(archive) > 1 else 0.0


def pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def mismatch_stats(archive: list[Node], min_desc: int = MIN_DESCENDANTS
                   ) -> tuple[Optional[float], Optional[bool], Optional[float]]:
    """(corr between own score and realised CMP, top-score node != top-CMP node,
    corr between own score and the latent m). The first two use nodes with at
    least `min_desc` descendants; the last uses every node (m is never observed
    by a policy, so this is the simulator's x-ray of the --mismatch knob)."""
    latent = pearson([n.score for n in archive], [n.m for n in archive])
    realized = realized_cmp_all(archive)
    counts = descendant_counts(archive)
    elig = [n for n in archive if counts[n.id] >= min_desc]
    if len(elig) < 3:
        return None, None, latent
    xs = [n.score for n in elig]
    ys = [realized[n.id] for n in elig]
    top_score = max(elig, key=lambda n: (n.score, -n.id)).id
    top_cmp = max(elig, key=lambda n: (realized[n.id], -n.id)).id
    return pearson(xs, ys), top_score != top_cmp, latent


def summarise(policy: str, cfg: Config, trials: int, seed: int) -> dict:
    best_p, waste, depth, corrs, latents, step_best, step_mean = [], [], [], [], [], [], []
    top_mismatch, eligible, broken_best = 0, 0, 0
    for t in range(trials):
        rng = random.Random(f"{seed}:{policy}:{t}:{cfg.mismatch}:{int(cfg.meta_editable)}")
        archive = run_trial(policy, cfg, rng)
        best = best_node(archive)
        best_p.append(best.p)
        waste.append(dead_clade_waste(archive))
        depth.append(best.depth)
        step_best.append(best.step / cfg.step0)
        step_mean.append(statistics.fmean(n.step for n in archive) / cfg.step0)
        broken_best += any(archive[a].broken for a in lineage(archive, best.id))
        corr, mism, latent = mismatch_stats(archive)
        if corr is not None:
            corrs.append(corr)
        if latent is not None:
            latents.append(latent)
        if mism is not None:
            eligible += 1
            top_mismatch += int(mism)
    q = statistics.quantiles(best_p, n=4) if trials >= 4 else [min(best_p), 0.0, max(best_p)]
    return {
        "policy": policy,
        "trials": trials,
        "mismatch": cfg.mismatch,
        "best_p_median": statistics.median(best_p),
        "best_p_q25": q[0],
        "best_p_q75": q[2],
        "waste_median": statistics.median(waste),
        "depth_median": statistics.median(depth),
        "corr_mean": statistics.fmean(corrs) if corrs else None,
        "latent_corr_mean": statistics.fmean(latents) if latents else None,
        "top_mismatch": top_mismatch,
        "eligible": eligible,
        "step_best_median": statistics.median(step_best),
        "step_mean_median": statistics.median(step_mean),
        "broken_in_best_lineage": broken_best / trials,
    }


# ----------------------------------------------------------------- reporting

def fmt_opt(x: Optional[float], spec: str = "+.2f") -> str:
    return "n/a" if x is None else format(x, spec)


def print_policy_table(rows: list[dict], label: str) -> None:
    print(f"\n{label}")
    print(f"  {'policy':<8} {'best p (median)':>16} {'[q25, q75]':>16} {'dead-clade waste':>17} "
          f"{'depth(best)':>12} {'corr(score,m)':>14} {'corr(score,CMP)':>16}")
    for r in rows:
        iqr = f"[{r['best_p_q25']:.3f}, {r['best_p_q75']:.3f}]"
        print(f"  {r['policy']:<8} {r['best_p_median']:>16.3f} {iqr:>16} {r['waste_median']:>17.1%} "
              f"{r['depth_median']:>12.0f} {fmt_opt(r['latent_corr_mean']):>14} {fmt_opt(r['corr_mean']):>16}")


def print_mismatch_block(rows: list[dict]) -> None:
    print(f"\nMetaproductivity-Performance Mismatch (nodes with >= {MIN_DESCENDANTS} descendants)")
    for r in rows:
        if r["eligible"]:
            frac = r["top_mismatch"] / r["eligible"]
            print(f"  {r['policy']:<8} top-score node was NOT the top-CMP node in "
                  f"{r['top_mismatch']}/{r['eligible']} trials ({frac:.1%}); "
                  f"mean corr(own score, descendants' mean p) = {fmt_opt(r['corr_mean'])}")


def print_sweep(sweep: dict[float, list[dict]], ref_policy: str) -> None:
    policies = [r["policy"] for r in next(iter(sweep.values()))]
    both = {"hgm", "dgm"} <= set(policies)
    print(f"\nMismatch sweep (median best p; correlations and top!=top measured in the {ref_policy} tree)")
    print(f"  {'mismatch':>8} " + " ".join(f"{p:>8}" for p in policies)
          + ("   hgm-dgm" if both else "") + f" {'corr(score,m)':>14} {'corr(score,CMP)':>16} {'top!=top':>9}")
    for mm, rows in sweep.items():
        by = {r["policy"]: r for r in rows}
        ref = by[ref_policy]
        line = f"  {mm:>8.1f} " + " ".join(f"{by[p]['best_p_median']:>8.3f}" for p in policies)
        if both:
            line += f"   {by['hgm']['best_p_median'] - by['dgm']['best_p_median']:>+7.3f}"
        rate = f"{ref['top_mismatch'] / ref['eligible']:.1%}" if ref["eligible"] else "n/a"
        print(line + f" {fmt_opt(ref['latent_corr_mean']):>14} {fmt_opt(ref['corr_mean']):>16} {rate:>9}")


def print_meta_block(editable: list[dict], frozen: list[dict]) -> None:
    print("\nMeta-editable improvement operator (Hyperagents flavour) vs frozen step")
    print(f"  {'policy':<8} {'best p editable':>16} {'best p frozen':>14} {'delta':>8} "
          f"{'step(best)/step0':>17} {'mean step/step0':>16}")
    for e, f in zip(editable, frozen):
        print(f"  {e['policy']:<8} {e['best_p_median']:>16.3f} {f['best_p_median']:>14.3f} "
              f"{e['best_p_median'] - f['best_p_median']:>+8.3f} {e['step_best_median']:>16.2f}x "
              f"{e['step_mean_median']:>15.2f}x")


def headline(main_rows: list[dict], sweep: dict[float, list[dict]], cfg: Config,
             meta_rows: Optional[tuple[list[dict], list[dict]]]) -> list[str]:
    by = {r["policy"]: r for r in main_rows}
    lines = []
    ranked = sorted(main_rows, key=lambda r: -r["best_p_median"])
    order = " > ".join(f"{r['policy']} {r['best_p_median']:.3f}" for r in ranked)
    lines.append(f"Equal budget of {cfg.budget} nodes at mismatch {cfg.mismatch:.1f}: median best p {order}.")
    if "latest" in by:
        others = [r for r in main_rows if r["policy"] != "latest"]
        if others:
            least = min(others, key=lambda r: r["waste_median"])
            lines.append(f"latest-only spends {by['latest']['waste_median']:.1%} of its budget on dead clades; "
                         f"{least['policy']} spends {least['waste_median']:.1%}.")
    for pol in ("dgm", "hgm", "latest"):
        r = by.get(pol)
        if r and r["eligible"]:
            strength = "weak" if (r["corr_mean"] or 0.0) < 0.5 else "moderate"
            lines.append(f"In {pol} trees the top-scoring node was not the top-CMP node in "
                         f"{r['top_mismatch']}/{r['eligible']} trials ({r['top_mismatch'] / r['eligible']:.1%}); "
                         f"corr(score, CMP) = {fmt_opt(r['corr_mean'])}, a {strength} proxy for metaproductivity.")
            break
    if {"hgm", "dgm"} <= set(by):
        lo, hi = min(sweep), max(sweep)
        gap = {mm: ({r["policy"]: r for r in rows}["hgm"]["best_p_median"]
                    - {r["policy"]: r for r in rows}["dgm"]["best_p_median"]) for mm, rows in sweep.items()}
        trend = "widens" if gap[hi] > gap[lo] else "does not widen"
        ref = {r["policy"]: r for r in sweep[lo]}["dgm"], {r["policy"]: r for r in sweep[hi]}["dgm"]
        lines.append(f"Raising mismatch {lo:.1f} -> {hi:.1f} cuts corr(score, m) in dgm trees from "
                     f"{fmt_opt(ref[0]['latent_corr_mean'])} to {fmt_opt(ref[1]['latent_corr_mean'])}, "
                     f"yet the hgm-dgm gap {trend}: {gap[lo]:+.3f} vs {gap[hi]:+.3f}.")
    if meta_rows:
        editable, frozen = meta_rows
        for e, f in zip(editable, frozen):
            d = e["best_p_median"] - f["best_p_median"]
            lines.append(f"Editable step ({e['policy']}): best p {d:+.3f} vs frozen; the best lineage's step "
                         f"grew to {e['step_best_median']:.2f}x step0 (archive mean {e['step_mean_median']:.2f}x).")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget", type=int, default=60, help="child nodes per trial (default: %(default)s)")
    parser.add_argument("--mismatch", type=float, default=0.7,
                        help="share of metaproductivity that is NOT task performance, 0..1 (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=40, help="trials per policy (default: %(default)s)")
    parser.add_argument("--policy", choices=("all",) + POLICIES, default="all")
    parser.add_argument("--meta-editable", action="store_true",
                        help="let each node's improvement step size mutate (Hyperagents flavour)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="write the summary as JSON to this path")
    args = parser.parse_args()
    if not 0.0 <= args.mismatch <= 1.0:
        parser.error("--mismatch must be in [0, 1]")
    if args.budget < 1 or args.trials < 1:
        parser.error("--budget and --trials must be >= 1")
    policies = list(POLICIES) if args.policy == "all" else [args.policy]
    ref_policy = "dgm" if "dgm" in policies else policies[0]
    cfg = Config(budget=args.budget, mismatch=args.mismatch, meta_editable=args.meta_editable)

    print("=" * 78)
    print("ARCHIVE-TREE SEARCH: latest-only vs DGM-style vs HGM-style (Phase 20, Lesson 10)")
    print("=" * 78)
    print(f"  budget={cfg.budget} nodes/trial  trials={args.trials}  mismatch={cfg.mismatch:.1f} "
          f"(task-skill share of m = {1 - cfg.mismatch:.2f})  tasks/eval={cfg.tasks}  seed={args.seed}  "
          f"meta-editable={'on' if cfg.meta_editable else 'off'}")
    print(f"  root p0={cfg.p0:.2f}  step0={cfg.step0:.2f}  luck sd={cfg.luck:.2f}  "
          f"skill-walk sd={cfg.skill_noise:.2f}  break prob={cfg.break_prob:.0%} "
          f"(p -{cfg.break_loss:.2f}, skill -{cfg.break_skill_loss:.2f})")

    main_rows = [summarise(p, cfg, args.trials, args.seed) for p in policies]
    print_policy_table(main_rows, f"Policy comparison at mismatch {cfg.mismatch:.1f}")
    print_mismatch_block(main_rows)

    sweep: dict[float, list[dict]] = {}
    for mm in SWEEP_MISMATCH:
        sweep_cfg = Config(budget=cfg.budget, mismatch=mm, meta_editable=cfg.meta_editable)
        sweep[mm] = [summarise(p, sweep_cfg, args.trials, args.seed) for p in policies]
    print_sweep(sweep, ref_policy)

    meta_rows = None
    if cfg.meta_editable:
        frozen_cfg = Config(budget=cfg.budget, mismatch=cfg.mismatch, meta_editable=False)
        frozen = [summarise(p, frozen_cfg, args.trials, args.seed) for p in policies]
        meta_rows = (main_rows, frozen)
        print_meta_block(main_rows, frozen)

    print("\n" + "=" * 78)
    print("HEADLINE")
    print("-" * 78)
    for line in headline(main_rows, sweep, cfg, meta_rows):
        print(f"  {line}")

    if args.out:
        payload = {"config": vars(cfg), "seed": args.seed, "main": main_rows,
                   "sweep": {str(k): v for k, v in sweep.items()},
                   "frozen_contrast": meta_rows[1] if meta_rows else None}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
