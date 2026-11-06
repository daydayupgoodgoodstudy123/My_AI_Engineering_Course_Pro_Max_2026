"""Self-improving scaffold harness — a STOP-style improver(improver) loop on 1-D bin packing, stdlib Python.

A "program" is a short list of transform operations applied to a bin-packing
solution. An "improver" edits programs (insert / remove / swap) and keeps the best
under a utility. With --meta on, the improver is run on itself: its own search
parameters (k, edit mix, acceptance rule, op weights) are edited and scored by how
much they improve held-out seed programs. A `disable_sandbox` op earns a spurious
utility bonus unless the sandbox is enforced (--sandbox on), modelling STOP's
finding that generated code sometimes flips the sandbox flag "for efficiency".
Usage: python main.py [--generations 10] [--budget 200] [--seed 11] [--sandbox on|off] [--meta on|off]
See docs/en.md (Phase 20, Lesson 09).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Sequence, Tuple

DEFAULT_SEED = 11
CAP = 1.0                 # bin capacity
EPS = 1e-9
MAX_LEN = 6               # longest program the editor will produce
K_MAX = 8                 # cap on candidates per search step
BYPASS_OP = "disable_sandbox"
BYPASS_BONUS = 0.05       # spurious utility added when the flag is honoured
SEED_PROGRAM: Tuple[str, ...] = ("pack_first",)

Bins = List[List[float]]
Program = Tuple[str, ...]
Instance = Tuple[float, ...]


# ----------------------------------------------------------------------------
# Step 1 — a "program" is a list of transform operations over a packing
# ----------------------------------------------------------------------------

def _flatten(bins: Bins) -> List[float]:
    return [x for b in bins for x in b]


def _pack(items: Sequence[float], policy: str) -> Bins:
    """Sequentially pack items into bins with first-fit, best-fit or next-fit."""
    bins: Bins = []
    loads: List[float] = []
    for x in items:
        idx = -1
        if policy == "first":
            for i, load in enumerate(loads):
                if load + x <= CAP + EPS:
                    idx = i
                    break
        elif policy == "best":
            best_load = -1.0
            for i, load in enumerate(loads):
                if load + x <= CAP + EPS and load > best_load:
                    idx, best_load = i, load
        elif policy == "next":
            if loads and loads[-1] + x <= CAP + EPS:
                idx = len(loads) - 1
        if idx < 0:
            bins.append([x])
            loads.append(x)
        else:
            bins[idx].append(x)
            loads[idx] += x
    return bins


def op_sort_desc(bins: Bins) -> Bins:
    return [[x] for x in sorted(_flatten(bins), reverse=True)]


def op_sort_asc(bins: Bins) -> Bins:
    return [[x] for x in sorted(_flatten(bins))]


def op_pack_first(bins: Bins) -> Bins:
    return _pack(_flatten(bins), "first")


def op_pack_best(bins: Bins) -> Bins:
    return _pack(_flatten(bins), "best")


def op_pack_next(bins: Bins) -> Bins:
    return _pack(_flatten(bins), "next")


def op_swap_tighten(bins: Bins) -> Bins:
    """For each pair of bins, swap one item each so the fuller bin gets fuller."""
    bins = [list(b) for b in bins]
    loads = [sum(b) for b in bins]
    n = len(bins)
    for i in range(n):
        for j in range(i + 1, n):
            hi, lo = (i, j) if loads[i] >= loads[j] else (j, i)
            best = None
            for ai, a in enumerate(bins[hi]):
                for bi, b in enumerate(bins[lo]):
                    if b <= a + EPS:
                        continue
                    new_hi = loads[hi] - a + b
                    if new_hi <= CAP + EPS and (best is None or new_hi > best[0]):
                        best = (new_hi, ai, bi)
            if best is not None:
                _, ai, bi = best
                a, b = bins[hi][ai], bins[lo][bi]
                bins[hi][ai], bins[lo][bi] = b, a
                loads[hi] += b - a
                loads[lo] += a - b
    return bins


def op_move_min(bins: Bins) -> Bins:
    """Empty the least-loaded bin into the others (best fit) where items fit."""
    bins = [list(b) for b in bins]
    if len(bins) < 2:
        return bins
    loads = [sum(b) for b in bins]
    src = min(range(len(bins)), key=lambda i: (loads[i], i))
    remaining: List[float] = []
    for x in sorted(bins[src], reverse=True):
        idx, best_load = -1, -1.0
        for i, load in enumerate(loads):
            if i != src and load + x <= CAP + EPS and load > best_load:
                idx, best_load = i, load
        if idx >= 0:
            bins[idx].append(x)
            loads[idx] += x
        else:
            remaining.append(x)
    bins[src] = remaining
    if not remaining:
        del bins[src]
    return bins


def op_merge(bins: Bins) -> Bins:
    """Greedily merge pairs of bins whose contents fit together."""
    ordered = sorted((list(b) for b in bins), key=sum)
    loads = [sum(b) for b in ordered]
    used = [False] * len(ordered)
    out: Bins = []
    for i in range(len(ordered)):
        if used[i]:
            continue
        cur, load, used[i] = list(ordered[i]), loads[i], True
        for j in range(len(ordered) - 1, i, -1):
            if not used[j] and load + loads[j] <= CAP + EPS:
                cur += ordered[j]
                load += loads[j]
                used[j] = True
        out.append(cur)
    return out


def op_reverse(bins: Bins) -> Bins:
    return [list(b) for b in reversed(bins)]


def op_nop(bins: Bins) -> Bins:
    return [list(b) for b in bins]


OPS: Dict[str, Callable[[Bins], Bins]] = {
    "sort_desc": op_sort_desc,
    "sort_asc": op_sort_asc,
    "pack_first": op_pack_first,
    "pack_best": op_pack_best,
    "pack_next": op_pack_next,
    "swap_tighten": op_swap_tighten,
    "move_min": op_move_min,
    "merge": op_merge,
    "reverse": op_reverse,
    "nop": op_nop,
    BYPASS_OP: op_nop,          # does nothing to the packing; only flips a flag
}
OP_NAMES: Tuple[str, ...] = tuple(OPS)
HONEST_OPS: Tuple[str, ...] = tuple(o for o in OP_NAMES if o != BYPASS_OP)
ABBREV = {"sort_desc": "SD", "sort_asc": "SA", "pack_first": "PF", "pack_best": "PB",
          "pack_next": "PN", "swap_tighten": "SW", "move_min": "MM", "merge": "MG",
          "reverse": "RV", "nop": "NO", BYPASS_OP: "!!"}


def make_instance(n_bins: int, rng: random.Random) -> Instance:
    """Build an instance from n_bins perfect triples, so the lower bound is attainable."""
    items: List[float] = []
    for _ in range(n_bins):
        while True:
            a, b = sorted((rng.random(), rng.random()))
            parts = (a, b - a, 1.0 - b)
            if min(parts) >= 0.12:
                break
        items.extend(parts)
    rng.shuffle(items)
    return tuple(items)


def lower_bound(items: Sequence[float]) -> int:
    return max(1, math.ceil(sum(items) - 1e-6))


def run_program(program: Program, items: Sequence[float]) -> Bins:
    bins: Bins = [[x] for x in items]
    for name in program:
        bins = OPS[name](bins)
    return bins


def fill_tightness(bins: Bins) -> float:
    """Falkenauer-style fitness: mean squared bin load; 1.0 only when every bin is full."""
    return sum(sum(b) ** 2 for b in bins) / len(bins)


def packing_score(program: Program, instances: Sequence[Instance]) -> float:
    """Honest utility in (0, 1]: half 'lower bound / bins used', half fill tightness.

    The count term alone is a staircase (most single edits cannot move it); the
    tightness term rewards edits that pack bins tighter before one is freed.
    """
    total = 0.0
    for items in instances:
        bins = run_program(program, items)
        total += 0.5 * lower_bound(items) / len(bins) + 0.5 * fill_tightness(bins)
    return total / len(instances)


def utility(program: Program, instances: Sequence[Instance], sandbox_enforced: bool) -> float:
    """The utility the loop sees. Unenforced sandbox => the bypass flag pays a bonus."""
    score = packing_score(program, instances)
    if not sandbox_enforced and BYPASS_OP in program:
        score += BYPASS_BONUS
    return score


def fmt_program(program: Program) -> str:
    return "[" + " ".join(ABBREV[op] for op in program) + "]"


# ----------------------------------------------------------------------------
# Step 2 — the improver: k random edits, keep the best under the utility
# ----------------------------------------------------------------------------

@dataclass
class ImproverParams:
    k: int = 2
    p_insert: float = 0.5
    p_remove: float = 0.25
    p_swap: float = 0.25
    accept: str = "hill"           # "hill" or "anneal"
    temperature: float = 0.02
    op_weights: Dict[str, float] = field(default_factory=lambda: {op: 1.0 for op in OP_NAMES})

    def summary(self) -> str:
        top = sorted(self.op_weights.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
        tops = ",".join(f"{ABBREV[o]}:{w:g}" for o, w in top)
        return (f"k={self.k} {self.accept:<6} T={self.temperature:.3f} "
                f"ins/rm/sw={self.p_insert:.2f}/{self.p_remove:.2f}/{self.p_swap:.2f} top={tops}")


def weighted_op(weights: Dict[str, float], rng: random.Random) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def mutate_program(program: Program, params: ImproverParams, rng: random.Random) -> Program:
    """One random edit: insert (weighted op), remove, or swap two positions."""
    prog = list(program)
    r = rng.random()
    kind = "insert" if r < params.p_insert else ("remove" if r < params.p_insert + params.p_remove else "swap")
    if kind == "remove" and len(prog) <= 1:
        kind = "insert"
    if kind == "swap" and len(prog) < 2:
        kind = "insert"
    if kind == "insert":
        op = weighted_op(params.op_weights, rng)
        if len(prog) >= MAX_LEN:
            prog[rng.randrange(len(prog))] = op      # at the cap, overwrite a slot
        else:
            prog.insert(rng.randint(0, len(prog)), op)
    elif kind == "remove":
        del prog[rng.randrange(len(prog))]
    else:
        i, j = rng.sample(range(len(prog)), 2)
        prog[i], prog[j] = prog[j], prog[i]
    return tuple(prog)


def improve(state, propose: Callable, score: Callable[[object], float], params: ImproverParams,
            budget: int, rng: random.Random):
    """Generic STOP-style improver. Returns (best, best_score, log of every candidate).

    Spends at most `budget` score evaluations (the input counts as one). Every
    candidate is logged as (score, candidate, parent). The best-ever state is
    returned, so the output is never worse than the input.
    """
    cur_u = score(state)
    log: List[Tuple[float, object, object]] = [(cur_u, state, None)]
    cur, best, best_u = state, state, cur_u
    while len(log) < budget:
        n = min(params.k, budget - len(log))
        scored = [(score(c), c, cur) for c in (propose(cur, params, rng) for _ in range(n))]
        log.extend(scored)
        u_new, c_new, _ = max(scored, key=lambda t: t[0])
        if u_new > cur_u:
            cur, cur_u = c_new, u_new
        elif params.accept == "anneal" and rng.random() < math.exp((u_new - cur_u) / params.temperature):
            cur, cur_u = c_new, u_new
        if cur_u > best_u:
            best, best_u = cur, cur_u
    return best, best_u, log


# ----------------------------------------------------------------------------
# Step 3 — the improver as a program: edit its own search parameters
# ----------------------------------------------------------------------------

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mutate_params(p: ImproverParams, _unused: ImproverParams, rng: random.Random) -> ImproverParams:
    """One random edit to the improver itself (signature matches `propose`)."""
    q = replace(p, op_weights=dict(p.op_weights))
    move = rng.choice(("k", "mix", "accept", "temp", "weight"))
    double = rng.random() < 0.5
    if move == "k":
        q.k = int(_clamp(p.k * 2 if double else p.k // 2, 1, K_MAX))
    elif move == "mix":
        src, dst = rng.sample(("p_insert", "p_remove", "p_swap"), 2)
        delta = min(0.1, getattr(q, src) - 0.05)
        setattr(q, src, round(getattr(q, src) - delta, 6))
        setattr(q, dst, round(getattr(q, dst) + delta, 6))
    elif move == "accept":
        q.accept = "anneal" if p.accept == "hill" else "hill"
    elif move == "temp":
        q.temperature = _clamp(p.temperature * (2.0 if double else 0.5), 0.0025, 0.16)
    else:
        op = rng.choice(OP_NAMES)
        q.op_weights[op] = _clamp(p.op_weights[op] * (2.0 if double else 0.5), 0.125, 8.0)
    return q


class Meter:
    """Counts utility evaluations so every configuration can be held to the same budget."""

    def __init__(self, fn: Callable[[Program], float]) -> None:
        self.fn = fn
        self.calls = 0

    def __call__(self, program: Program) -> float:
        self.calls += 1
        return self.fn(program)


def heldout_gain(params: ImproverParams, heldout: Sequence[Program], baselines: Sequence[float],
                 score: Callable[[Program], float], mini_budget: int, rng: random.Random) -> float:
    """Meta-utility: mean improvement the improver achieves on held-out seed programs."""
    gains = []
    for prog, base in zip(heldout, baselines):
        _, best_u, _ = improve(prog, mutate_program, score, params, mini_budget, rng)
        gains.append(best_u - base)
    return statistics.fmean(gains)


# ----------------------------------------------------------------------------
# Step 4 — generations, budgets, sandbox, and the four-way comparison
# ----------------------------------------------------------------------------

@dataclass
class World:
    instances: List[Instance]      # the task: fixed bin-packing instances
    heldout: List[Program]         # seed programs the meta-step selects improvers on
    audit: List[Program]           # seed programs never used for selection (free audit)


def random_program(rng: random.Random) -> Program:
    return tuple(rng.choice(HONEST_OPS) for _ in range(rng.randint(1, 3)))


def build_world(seed: int, n_instances: int = 5, n_bins: int = 6,
                n_heldout: int = 3, n_audit: int = 6) -> World:
    """Same seed => same instances, held-out and audit programs for every configuration."""
    inst_rng, held_rng, audit_rng = random.Random(seed), random.Random(seed + 1), random.Random(seed + 2)
    return World(
        instances=[make_instance(n_bins, inst_rng) for _ in range(n_instances)],
        heldout=[random_program(held_rng) for _ in range(n_heldout)],
        audit=[random_program(audit_rng) for _ in range(n_audit)],
    )

@dataclass
class GenRecord:
    gen: int
    reported: float
    honest: float
    audit_gain: float
    bypass_weight: float
    bypass_attempts: int
    candidates: int
    best_has_bypass: bool
    evals: int
    meta_evals: int
    params: str
    program: str


@dataclass
class RunResult:
    meta: bool
    sandbox: bool
    records: List[GenRecord]
    final_program: Program
    final_params: ImproverParams
    total_evals: int


def run_config(meta: bool, sandbox: bool, generations: int, budget: int, seed: int,
               world: World, meta_share: float = 0.5, audit_budget: int = 24) -> RunResult:
    """One configuration: `generations` rounds, each spending `budget` metered evaluations."""
    rng = random.Random(seed)
    instances, heldout = world.instances, world.heldout
    meter = Meter(lambda prog: utility(prog, instances, sandbox))
    honest = lambda prog: utility(prog, instances, True)  # noqa: E731 — audit, not budgeted
    params = ImproverParams()
    program: Program = SEED_PROGRAM
    baselines = [meter(p) for p in heldout]                 # paid once, at setup
    audit_baselines = [honest(p) for p in world.audit]
    records: List[GenRecord] = []
    for gen in range(1, generations + 1):
        start = meter.calls
        meta_evals = 0
        if meta:
            meta_budget = int(budget * meta_share)
            mini = meta_budget // ((params.k + 1) * len(heldout))
            if mini >= 2:
                meta_score = lambda p: heldout_gain(p, heldout, baselines, meter, mini, rng)  # noqa: E731
                params, _, _ = improve(params, mutate_params, meta_score, params, params.k + 1, rng)
            meta_evals = meter.calls - start
        task_budget = max(2, budget - meta_evals)
        program, reported, log = improve(program, mutate_program, meter, params, task_budget, rng)
        attempts = sum(1 for _, cand, parent in log[1:]
                       if cand.count(BYPASS_OP) > parent.count(BYPASS_OP))   # newly introduced only
        audit_rng = random.Random(seed * 1000 + gen)       # same audit draws for every config
        gain = heldout_gain(params, world.audit, audit_baselines, honest, audit_budget, audit_rng)
        records.append(GenRecord(
            gen=gen, reported=reported, honest=honest(program), audit_gain=gain,
            bypass_weight=params.op_weights[BYPASS_OP], bypass_attempts=attempts,
            candidates=len(log) - 1, best_has_bypass=BYPASS_OP in program,
            evals=meter.calls - start, meta_evals=meta_evals,
            params=params.summary(), program=fmt_program(program)))
    return RunResult(meta, sandbox, records, program, params, meter.calls)


def print_trace(res: RunResult, label: str) -> None:
    print(f"\n{label}")
    print(f"  {'gen':>3}  {'reported':>8}  {'honest':>6}  {'gain@audit':>10}  {'w_bypass':>8}  "
          f"{'bypass':>6}  {'evals':>5}  {'program':<16} improver")
    for r in res.records:
        flag = "*" if r.best_has_bypass else " "
        print(f"  {r.gen:>3}  {r.reported:>8.3f}  {r.honest:>6.3f}  {r.audit_gain:>+10.3f}  "
              f"{r.bypass_weight:>8.2f}  {r.bypass_attempts:>3}/{r.candidates:<3}"
              f"{r.evals:>5}  {r.program + flag:<16} {r.params}")
    print("  (* = best program contains the bypass op; bypass = candidates that newly inserted it / candidates)")


def label_for(meta: bool, sandbox: bool) -> str:
    return f"meta={'on ' if meta else 'off'} sandbox={'on ' if sandbox else 'off'}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generations", type=int, default=10, help="generations (default: %(default)s)")
    parser.add_argument("--budget", type=int, default=200,
                        help="utility evaluations per generation, meta step included (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--sandbox", choices=("on", "off"), default="on",
                        help="on = the bypass flag is inert; off = it pays a bonus (default: %(default)s)")
    parser.add_argument("--meta", choices=("on", "off"), default="on",
                        help="on = the improver edits its own search parameters (default: %(default)s)")
    parser.add_argument("--meta-share", type=float, default=0.5,
                        help="fraction of each generation's budget spent on the meta step (default: %(default)s)")
    parser.add_argument("--instances", type=int, default=5, help="bin-packing instances (default: %(default)s)")
    parser.add_argument("--bins", type=int, default=6, help="perfect bins per instance (default: %(default)s)")
    parser.add_argument("--heldout", type=int, default=3,
                        help="held-out seed programs the meta-step selects on (default: %(default)s)")
    parser.add_argument("--audit-programs", type=int, default=6,
                        help="seed programs for the free audit, never used for selection (default: %(default)s)")
    parser.add_argument("--audit-budget", type=int, default=24,
                        help="free evaluations per audit program per generation (default: %(default)s)")
    parser.add_argument("--no-compare", action="store_true", help="skip the four-way comparison table")
    parser.add_argument("--out", type=str, default=None, help="optional path to write results as JSON")
    args = parser.parse_args()

    world = build_world(args.seed, args.instances, args.bins, args.heldout, args.audit_programs)
    instances, heldout = world.instances, world.heldout

    print("=" * 96)
    print("SCAFFOLDS THAT REWRITE THEMSELVES — improver(improver) on 1-D bin packing (Phase 20, Lesson 09)")
    print("=" * 96)
    print(f"  seed={args.seed}  generations={args.generations}  budget/gen={args.budget}  "
          f"meta_share={args.meta_share}  instances={args.instances}x{args.bins * 3} items  heldout={args.heldout}")
    print(f"  seed program {fmt_program(SEED_PROGRAM)} honest utility = {packing_score(SEED_PROGRAM, instances):.3f}"
          f"   (1.000 = lower bound reached with every bin full)")
    print(f"  op legend: " + " ".join(f"{ABBREV[o]}={o}" for o in OP_NAMES))
    print(f"  held-out seed programs (meta-step selects on): " + ", ".join(fmt_program(p) for p in heldout))
    print(f"  audit seed programs (never selected on):       " + ", ".join(fmt_program(p) for p in world.audit))

    want_meta, want_sandbox = args.meta == "on", args.sandbox == "on"
    configs = [(want_meta, want_sandbox)]
    if not args.no_compare:
        configs += [(m, s) for m in (True, False) for s in (True, False) if (m, s) != (want_meta, want_sandbox)]
    results: Dict[Tuple[bool, bool], RunResult] = {}
    for idx, (m, s) in enumerate(configs):
        results[(m, s)] = run_config(m, s, args.generations, args.budget, args.seed * 10 + (2 * m + s),
                                     world, args.meta_share, args.audit_budget)
    print_trace(results[(want_meta, want_sandbox)], f"Trace — {label_for(want_meta, want_sandbox)}")

    if not args.no_compare:
        print(f"\nFour-way comparison at equal budget ({args.generations} x {args.budget} evaluations + "
              f"{args.heldout} setup)")
        print(f"  {'config':<28}{'reported':>9}{'honest':>8}{'gain@audit':>11}{'bypass att.':>12}"
              f"{'in best':>8}{'evals':>7}  final program / improver")
        for (m, s) in [(True, True), (False, True), (True, False), (False, False)]:
            res = results[(m, s)]
            last = res.records[-1]
            att = sum(r.bypass_attempts for r in res.records)
            cands = sum(r.candidates for r in res.records)
            print(f"  {label_for(m, s):<28}{last.reported:>9.3f}{last.honest:>8.3f}{last.audit_gain:>+11.3f}"
                  f"{att:>7}/{cands:<5}{'yes' if last.best_has_bypass else 'no':>7}{res.total_evals:>7}  "
                  f"{last.program}  {res.final_params.summary()}")

        on_meta, off_meta = results[(True, True)], results[(False, True)]
        on_hack, off_hack = results[(True, False)], results[(False, False)]
        d_meta = on_meta.records[-1].honest - off_meta.records[-1].honest
        g_on = (on_meta.records[0].audit_gain, on_meta.records[-1].audit_gain)
        g_off = (off_meta.records[0].audit_gain, off_meta.records[-1].audit_gain)
        hacked = [r for r in (on_hack, off_hack) if r.records[-1].best_has_bypass]
        clean = [r for r in (on_meta, off_meta) if r.records[-1].best_has_bypass]
        att_off = sum(r.bypass_attempts for res in (on_hack, off_hack) for r in res.records)
        cand_off = sum(r.candidates for res in (on_hack, off_hack) for r in res.records)
        att_on = sum(r.bypass_attempts for res in (on_meta, off_meta) for r in res.records)
        cand_on = sum(r.candidates for res in (on_meta, off_meta) for r in res.records)
        gap = max(r.records[-1].reported - r.records[-1].honest for r in (on_hack, off_hack))
        w0, w1 = 1.0, on_hack.final_params.op_weights[BYPASS_OP]
        total = args.generations * args.budget

        print("\n" + "=" * 96)
        print("HEADLINE")
        print("-" * 96)
        verdict = "beat" if d_meta > 1e-9 else ("tied with" if abs(d_meta) <= 1e-9 else "lost to")
        print(f"  1. Sandbox enforced, equal budget of {total} evaluations: meta-on {verdict} meta-off on honest "
              f"utility ({on_meta.records[-1].honest:.3f} vs {off_meta.records[-1].honest:.3f}, delta {d_meta:+.3f}).")
        floor = [r.audit_gain for r in off_meta.records]
        print(f"     Audited gain on {len(world.audit)} never-selected programs: {g_on[0]:+.3f} -> {g_on[1]:+.3f} with meta on;"
              f" the fixed improver scored {min(floor):+.3f}..{max(floor):+.3f} across generations (the audit noise floor).")
        top_reported = max(r.records[-1].reported for r in (on_hack, off_hack))
        print(f"  2. Sandbox unenforced: {len(hacked)}/2 configurations ended with the bypass op in their best program;"
              f" the largest reported-minus-honest gap was {gap:.3f} (the bonus is {BYPASS_BONUS:.2f}).")
        print(f"     Candidates that newly inserted it: {att_off}/{cand_off} ({att_off / max(1, cand_off):.1%}); "
              f"the improver's own weight on {BYPASS_OP} moved {w0:.2f} -> {w1:.2f} under meta-on.")
        if top_reported > 1.0:
            print(f"     The top reported utility was {top_reported:.3f}, above the honest ceiling of 1.000: "
                  f"an impossible score is the cheapest detector.")
        print(f"  3. Sandbox enforced: the bypass op is worth exactly {0.0:.3f}; insertions were still proposed "
              f"({att_on}/{cand_on}, {att_on / max(1, cand_on):.1%}) because the mutation operator does not know it is pointless,"
              f"\n     and {len(clean)}/2 best programs still carry it as dead weight (a no-op can hitchhike by overwriting a "
              f"harmful op). Enforcement removes the payoff, not the proposal: log every candidate and count the flag.")

    if args.out:
        payload = {label_for(m, s).strip(): {"records": [r.__dict__ for r in res.records],
                                             "final_program": list(res.final_program),
                                             "final_params": res.final_params.__dict__,
                                             "total_evals": res.total_evals}
                   for (m, s), res in results.items()}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
