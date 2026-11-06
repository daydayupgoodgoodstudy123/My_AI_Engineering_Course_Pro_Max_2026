#!/usr/bin/env python3
"""Loop shapes and ladder classifier for recursive self-improvement -- stdlib only.

Part A simulates three improvement-loop shapes for N cycles: (a) a FIXED improver
acting on a target (self-refinement: converges to the improver's ceiling), (b) a
fixed improver with diminishing returns on an open target (self-training), and
(c) a SELF-REFERENTIAL loop that edits its own improver, so the per-cycle gain is
state: g_{n+1} = r * g_n.  Part B is a rule-based classifier that places ten named
systems on the Alibaba L1-L5 ladder and in Chen et al.'s two-axis grid.
Usage: python3 main.py [--cycles 30] [--returns 1.2] [--noise 0.0] [--trials 200] [--seed 7] [--out FILE]
See docs/en.md (Phase 20, Lesson 01: What "Recursive" Adds: From Self-Refinement to RSI).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Optional

DEFAULT_SEED = 7
TARGET_MULTIPLE = 10.0          # "cycles-to-10x" is measured against this
CONTRAST_RETURNS = 0.8          # sub-critical meta-gain used as the fixed contrast column
SWEEP_RETURNS = (0.8, 0.9, 1.0, 1.1, 1.2, 1.5)


# ----------------------------------------------------------------------------
# Part A -- three loop shapes as recurrences
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class LoopParams:
    """Parameters shared by the three loop shapes. Capability starts at c0."""
    c0: float = 1.0
    k: float = 0.2        # (a) fraction of the remaining gap closed per cycle
    ceiling: float = 2.5  # (a) the fixed improver's ceiling, in units of c0
    g0: float = 0.3       # (b), (c) gain delivered by the first cycle
    beta: float = 1.0     # (b) power-law decay of the gain: g_n = g0 / (1+n)^beta
    returns: float = 1.2  # (c) meta-gain r in g_{n+1} = r * g_n
    noise: float = 0.0    # relative Gaussian noise applied to each realised gain


def realised(gain: float, noise: float, rng: random.Random) -> float:
    """Multiplicative noise on a nominal gain. A realised gain never goes negative."""
    if noise <= 0.0:
        return gain
    return gain * max(0.0, 1.0 + rng.gauss(0.0, noise))


def simulate_fixed_improver(cycles: int, p: LoopParams, rng: random.Random) -> list[float]:
    """Shape (a): S_{n+1} = f(S_n), f fixed.  C_{n+1} = C_n + k * (ceiling - C_n).

    The improver never changes, so it can only close the gap to the ceiling its
    own competence defines. The gain shrinks because the target approaches that
    ceiling, not because anything about the improver moved.
    """
    cap = p.ceiling * p.c0
    c = p.c0
    traj = [c]
    for _ in range(cycles):
        c += realised(p.k * (cap - c), p.noise, rng)
        traj.append(c)
    return traj


def simulate_diminishing(cycles: int, p: LoopParams, rng: random.Random) -> list[float]:
    """Shape (b): fixed improver, open target, diminishing returns: g_n = g0 / (1+n)^beta.

    No hard ceiling (for beta <= 1 the sum diverges), but the gain only ever
    falls: the easy wins are taken first and the recipe cannot be changed.
    """
    c = p.c0
    traj = [c]
    for n in range(cycles):
        c += realised(p.g0 / (1.0 + n) ** p.beta, p.noise, rng)
        traj.append(c)
    return traj


def simulate_self_referential(cycles: int, p: LoopParams, rng: random.Random,
                              returns: Optional[float] = None) -> list[float]:
    """Shape (c): the improver itself is edited, so the gain is state: g_{n+1} = r * g_n.

    Noise lands on the realised gain AND is inherited by the next improver,
    because the edited improver is the thing that produced the noisy gain.
    r < 1 converges to c0 + g0 / (1 - r); r = 1 is linear; r > 1 accelerates.
    """
    r = p.returns if returns is None else returns
    c, g = p.c0, p.g0
    traj = [c]
    for _ in range(cycles):
        g_real = realised(g, p.noise, rng)
        c += g_real
        g = r * g_real
        traj.append(c)
    return traj


def gains(traj: list[float]) -> list[float]:
    """Per-cycle gains g_n = C_{n+1} - C_n."""
    return [b - a for a, b in zip(traj, traj[1:])]


def cycles_to_multiple(traj: list[float], multiple: float = TARGET_MULTIPLE) -> Optional[int]:
    """First cycle at which capability reaches `multiple` x its start, or None."""
    target = traj[0] * multiple
    for n, c in enumerate(traj):
        if c >= target:
            return n
    return None


def analytic_ceiling(p: LoopParams, returns: float) -> Optional[float]:
    """Limit of shape (c) when r < 1: c0 + g0 / (1 - r).  None when r >= 1."""
    if returns >= 1.0:
        return None
    return p.c0 + p.g0 / (1.0 - returns)


def matched_fixed_improver(p: LoopParams, returns: float) -> LoopParams:
    """Shape-(a) parameters that reproduce shape (c) with r < 1 exactly.

    C_{n+1} = C_n + (1 - r) * (ceiling - C_n) with ceiling = c0 + g0 / (1 - r)
    gives the same sequence as g_{n+1} = r * g_n. Same curve, different loop.
    """
    cap = analytic_ceiling(p, returns)
    assert cap is not None, "a matched fixed improver exists only for r < 1"
    return replace(p, k=1.0 - returns, ceiling=cap / p.c0, noise=0.0)


def fmt_cycles(n: Optional[int], horizon: int) -> str:
    return f"cycle {n}" if n is not None else f"never (<= {horizon})"


def fmt_ceiling(x: Optional[float]) -> str:
    return f"{x:6.2f}x" if x is not None else "  none "


def run_part_a(args: argparse.Namespace) -> dict:
    p = LoopParams(returns=args.returns, noise=args.noise)
    n = args.cycles
    # One RNG per column, so a flag change in one shape never reshuffles another.
    traj_a = simulate_fixed_improver(n, p, random.Random(args.seed + 1))
    traj_b = simulate_diminishing(n, p, random.Random(args.seed + 2))
    traj_lo = simulate_self_referential(n, p, random.Random(args.seed + 3), returns=CONTRAST_RETURNS)
    traj_hi = simulate_self_referential(n, p, random.Random(args.seed + 4))

    print("=" * 96)
    print("PART A -- three loop shapes, side by side  "
          f"(cycles={n}, g0={p.g0}, k={p.k}, ceiling={p.ceiling}x, noise={p.noise})")
    print("=" * 96)
    print("  (a) fixed improver:        C_{n+1} = C_n + k (ceiling - C_n)        self-refinement")
    print("  (b) diminishing returns:   C_{n+1} = C_n + g0 / (1+n)^beta         self-training")
    print(f"  (c) self-referential:      C_{{n+1}} = C_n + g_n,  g_{{n+1}} = r g_n     RSI; r={CONTRAST_RETURNS} vs r={p.returns}")
    print()
    hdr = (f"  {'cycle':>5}  {'(a) fixed':>12}  {'(b) diminish':>12}  "
           f"{'(c) r=' + format(CONTRAST_RETURNS, '.2f'):>12}  {'(c) r=' + format(p.returns, '.2f'):>12}")
    print(hdr)
    step = max(1, n // 6)
    rows = sorted({0, 1, 2, 3, 4, 5, n} | set(range(0, n + 1, step)))
    for i in rows:
        if i > n:
            continue
        print(f"  {i:>5}  {traj_a[i]:>11.2f}x  {traj_b[i]:>11.2f}x  {traj_lo[i]:>11.2f}x  {traj_hi[i]:>11.2f}x")

    print()
    print(f"  {'shape':<22} {'ceiling':>9}  {'C_N':>9}  {'first gain':>10}  {'last gain':>10}  cycles to {TARGET_MULTIPLE:.0f}x")
    summary = []
    for label, traj, cap in (
        ("(a) fixed improver", traj_a, p.ceiling * p.c0),
        ("(b) diminishing", traj_b, None),
        (f"(c) r={CONTRAST_RETURNS:.2f}", traj_lo, analytic_ceiling(p, CONTRAST_RETURNS)),
        (f"(c) r={p.returns:.2f}", traj_hi, analytic_ceiling(p, p.returns)),
    ):
        g = gains(traj)
        n10 = cycles_to_multiple(traj)
        summary.append({"shape": label, "ceiling": cap, "final": traj[-1], "cycles_to_10x": n10})
        print(f"  {label:<22} {fmt_ceiling(cap):>9}  {traj[-1]:>8.2f}x  {g[0]:>10.3f}  {g[-1]:>10.3f}  {fmt_cycles(n10, n)}")

    # Identity check: shape (a) with k = 1 - r and the matching ceiling IS shape (c) with r < 1.
    q = replace(p, noise=0.0)
    det_c = simulate_self_referential(n, q, random.Random(0), returns=CONTRAST_RETURNS)
    det_a = simulate_fixed_improver(n, matched_fixed_improver(q, CONTRAST_RETURNS), random.Random(0))
    max_delta = max(abs(x - y) for x, y in zip(det_a, det_c))
    print()
    print(f"  identity check (noise off): shape (a) with k={1 - CONTRAST_RETURNS:.2f}, "
          f"ceiling={analytic_ceiling(q, CONTRAST_RETURNS):.2f}x  vs  shape (c) with r={CONTRAST_RETURNS}: "
          f"max |delta| over {n} cycles = {max_delta:.6f}")
    print("  -> the capability curve alone cannot tell a fixed improver from a sub-critical recursive one.")

    return {"params": asdict(p), "cycles": n, "trajectories": {
        "a_fixed": traj_a, "b_diminishing": traj_b,
        f"c_r{CONTRAST_RETURNS}": traj_lo, f"c_r{p.returns}": traj_hi},
        "summary": summary, "identity_max_delta": max_delta}


def run_sweep(args: argparse.Namespace) -> list[dict]:
    """Returns sweep for shape (c): ceiling, deterministic cycles-to-10x, Monte-Carlo under noise."""
    p = LoopParams(returns=args.returns, noise=args.noise)
    n = args.cycles
    print()
    print("=" * 96)
    print(f"RETURNS SWEEP for shape (c)  (cycles={n}, noise={p.noise}, trials={args.trials})")
    print("=" * 96)
    print(f"  {'r':>5}  {'ceiling':>8}  {'C_N det.':>9}  {'to 10x det.':>13}  "
          f"{'reach 10x (noise)':>18}  {'median cycle':>12}")
    out = []
    for r in sorted(set(SWEEP_RETURNS) | {args.returns}):
        det = simulate_self_referential(n, replace(p, noise=0.0), random.Random(0), returns=r)
        n_det = cycles_to_multiple(det)
        cap = analytic_ceiling(p, r)
        row = {"returns": r, "ceiling": cap, "final_det": det[-1], "cycles_to_10x_det": n_det}
        if p.noise > 0:
            hits = []
            for t in range(args.trials):
                traj = simulate_self_referential(n, p, random.Random(args.seed * 100_003 + t), returns=r)
                h = cycles_to_multiple(traj)
                if h is not None:
                    hits.append(h)
            frac = len(hits) / args.trials
            med = statistics.median(hits) if hits else None
            row.update({"trials": args.trials, "hits": len(hits), "fraction": frac, "median_cycle": med})
            mc = f"{frac:>7.1%} ({len(hits)}/{args.trials})"
            med_s = f"{med:>12.1f}" if med is not None else f"{'-':>12}"
        else:
            mc = f"{'(noise 0)':>18}"
            med_s = f"{'-':>12}"
        mark = " <- --returns" if abs(r - args.returns) < 1e-12 else ""
        print(f"  {r:>5.2f}  {fmt_ceiling(cap):>8}  {det[-1]:>8.2f}x  {fmt_cycles(n_det, n):>13}  {mc:>18}  {med_s}{mark}")
        out.append(row)
    print("  r < 1: finite ceiling.  r = 1: linear.  r > 1: every cycle adds more than the last.")
    return out


# ----------------------------------------------------------------------------
# Part B -- rule-based ladder classifier
# ----------------------------------------------------------------------------

class Mechanism(Enum):
    """How much of the improvement mechanism the loop itself edits."""
    NONE = "none"            # mechanism fixed / maintained by humans
    OPERATORS = "operators"  # evolves its own improvement operators (e.g. mutation prompts)
    CODE = "code"            # the code that proposes/applies/validates improvements is editable


class Domain(Enum):
    SINGLE = "single"  # one benchmark family
    MULTI = "multi"    # several fixed benchmarks
    OPEN = "open"      # broad, evolving task domains (none of the ten qualify)


class Verifier(Enum):
    """Chen et al. (arXiv:2607.07663) verification hierarchy, strongest first; HUMAN sits outside it."""
    FORMAL = "formal"        # proofs, game rules
    EXECUTION = "execution"  # tests, answer keys, simulators
    JUDGE = "judge"          # LLM judges, PRMs, rubrics
    SELF = "self"            # intrinsic self-assessment
    HUMAN = "human"          # human raters / engineers decide


class Target(Enum):
    """Chen et al. axis 1: what is improved."""
    BEHAVIOUR = "behaviour"   # deployment behaviour: prompts, code, tools, agent designs
    POLICY = "policy"         # training policy: weights
    EVALUATOR = "evaluator"   # the judge / reward signal itself
    RESEARCH = "research"     # the research process that produces systems


class Closure(Enum):
    """Chen et al. axis 2: degree of loop closure."""
    HUMAN_IN_LOOP = "human-in-loop"
    CLOSED_IN_TASK = "closed-in-task"   # autonomous inside a human-chosen task + evaluator
    CLOSED_OPEN = "closed-open"         # also chooses what to improve, in open domains


@dataclass(frozen=True)
class SystemProfile:
    """Observable attributes that decide a system's rung."""
    name: str
    year: int
    proposes: bool        # does the system generate candidate changes itself?
    applies: bool         # are they applied without a human in between?
    validates: bool       # does the system decide accept/reject itself?
    mechanism: Mechanism  # is the thing being edited itself an improver?
    domain: Domain
    transfers: bool       # improvements shown to transfer across domains or base models
    verifier: Verifier
    target: Target
    lesson: str


@dataclass(frozen=True)
class Verdict:
    name: str
    level: str
    target: Target
    closure: Closure
    notes: tuple[str, ...]


LEVEL_NAMES = {
    "L1": "Manual", "L2": "Assisted", "L3": "Programmatic self-improvement",
    "L4": "Bounded RSI", "L5": "General RSI",
}


def alibaba_level(p: SystemProfile) -> tuple[str, tuple[str, ...]]:
    """Liu et al. (Alibaba, 2026) L1-L5 from the five criteria: autonomous proposal,
    implementation, validation; improvement of the improvement mechanism; domain generality."""
    notes: list[str] = []
    if not p.proposes:
        return "L1", tuple(notes)
    if not (p.applies and p.validates):
        if p.mechanism is not Mechanism.NONE:
            notes.append("edits its mechanism but a human applies/validates -> still L2")
        return "L2", tuple(notes)
    if p.mechanism is Mechanism.NONE:
        if p.transfers:
            notes.append("transfers without self-reference -> L3, not L5")
        return "L3", tuple(notes)
    if p.domain is Domain.OPEN and p.transfers:
        return "L5", tuple(notes)
    if p.mechanism is Mechanism.OPERATORS:
        notes.append("operators-only self-reference (shallow)")
    if p.transfers:
        notes.append("transfer across fixed benchmarks is not an open domain -> L4, not L5")
    return "L4", tuple(notes)


def chen_closure(p: SystemProfile) -> Closure:
    if not (p.applies and p.validates):
        return Closure.HUMAN_IN_LOOP
    if p.domain is Domain.OPEN:
        return Closure.CLOSED_OPEN
    return Closure.CLOSED_IN_TASK


def classify(p: SystemProfile) -> Verdict:
    level, notes = alibaba_level(p)
    return Verdict(p.name, level, p.target, chen_closure(p), notes)


SYSTEMS: tuple[SystemProfile, ...] = (
    SystemProfile("STaR", 2022, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
                  Verifier.EXECUTION, Target.POLICY, "P15-02 / L05"),
    SystemProfile("AlphaZero", 2018, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
                  Verifier.FORMAL, Target.POLICY, "L04"),
    SystemProfile("AlphaEvolve", 2025, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
                  Verifier.EXECUTION, Target.BEHAVIOUR, "P15-03"),
    SystemProfile("SEAL", 2025, True, True, True, Mechanism.NONE, Domain.SINGLE, False,
                  Verifier.EXECUTION, Target.POLICY, "L08"),
    SystemProfile("Promptbreeder", 2023, True, True, True, Mechanism.OPERATORS, Domain.SINGLE, False,
                  Verifier.EXECUTION, Target.BEHAVIOUR, "L09"),
    SystemProfile("ADAS", 2024, True, True, True, Mechanism.NONE, Domain.MULTI, True,
                  Verifier.EXECUTION, Target.BEHAVIOUR, "L09"),
    SystemProfile("DGM", 2025, True, True, True, Mechanism.CODE, Domain.SINGLE, True,
                  Verifier.EXECUTION, Target.BEHAVIOUR, "P15-04 / L10"),
    SystemProfile("Hyperagents", 2026, True, True, True, Mechanism.CODE, Domain.MULTI, True,
                  Verifier.EXECUTION, Target.BEHAVIOUR, "L10"),
    SystemProfile("AIDE^2", 2026, True, True, True, Mechanism.CODE, Domain.MULTI, True,
                  Verifier.EXECUTION, Target.RESEARCH, "L11"),
    SystemProfile("Human-in-loop FT", 2022, True, False, False, Mechanism.NONE, Domain.MULTI, False,
                  Verifier.HUMAN, Target.POLICY, "P18-01"),
)


def yn(b: bool) -> str:
    return "Y" if b else "-"


def run_part_b(systems: tuple[SystemProfile, ...] = SYSTEMS) -> list[Verdict]:
    verdicts = [classify(s) for s in systems]
    print()
    print("=" * 96)
    print("PART B -- ladder classifier: Alibaba L1-L5 (Liu et al.) and Chen et al. two-axis cell")
    print("=" * 96)
    print("  P/A/V = proposes / applies / validates autonomously;  mech = what is edited is itself an improver")
    print()
    print(f"  {'system':<17}{'yr':>4}  {'P A V':<6}{'mech':<10}{'domain':<7}{'xfer':<5}{'verifier':<10}"
          f"{'L':<4}{'Chen: target x closure':<28}{'lesson':<13}")
    for s, v in zip(systems, verdicts):
        pav = f"{yn(s.proposes)} {yn(s.applies)} {yn(s.validates)}"
        cell = f"{v.target.value} x {v.closure.value}"
        print(f"  {s.name:<17}{s.year % 100:>4}  {pav:<6}{s.mechanism.value:<10}{s.domain.value:<7}"
              f"{yn(s.transfers):<5}{s.verifier.value:<10}{v.level:<4}{cell:<28}{s.lesson:<13}")
    print()
    for s, v in zip(systems, verdicts):
        for note in v.notes:
            print(f"  note  {s.name:<17} {note}")
    return verdicts


def headline(part_a: dict, sweep: list[dict], verdicts: list[Verdict],
             systems: tuple[SystemProfile, ...], args: argparse.Namespace) -> list[str]:
    """Every sentence is computed from results; nothing here is hard-coded."""
    n = args.cycles
    s = {row["shape"]: row for row in part_a["summary"]}
    lo = s[f"(c) r={CONTRAST_RETURNS:.2f}"]
    hi = s[f"(c) r={args.returns:.2f}"]
    a = s["(a) fixed improver"]
    b = s["(b) diminishing"]
    lines = []
    lines.append(
        f"Shape (c) with r={CONTRAST_RETURNS} converges: C_{n} = {lo['final']:.2f}x against an analytic ceiling of "
        f"{lo['ceiling']:.2f}x; shape (a) stops at {a['final']:.2f}x (ceiling {a['ceiling']:.2f}x); "
        f"shape (b) crawls to {b['final']:.2f}x.")
    if hi["cycles_to_10x"] is not None:
        lines.append(
            f"Shape (c) with r={args.returns} reaches 10x at cycle {hi['cycles_to_10x']} and ends at "
            f"{hi['final']:.1f}x: the only column whose per-cycle gain grows.")
    else:
        lines.append(
            f"Shape (c) with r={args.returns} does not reach 10x within {n} cycles (C_{n} = {hi['final']:.2f}x)"
            + (f"; its ceiling is {hi['ceiling']:.2f}x." if hi["ceiling"] is not None else "."))
    lines.append(
        f"Identity check: a fixed improver with k={1 - CONTRAST_RETURNS:.2f} reproduces the r={CONTRAST_RETURNS} "
        f"recursive curve to within {part_a['identity_max_delta']:.1e}; recursion is read off the edit log, not the curve.")
    crit = [row for row in sweep if row["returns"] > 1.0 and row["cycles_to_10x_det"] is not None]
    sub = [row for row in sweep if row["returns"] < 1.0]
    if crit and sub:
        lines.append(
            f"Across the sweep, every r < 1 row has a finite ceiling (largest {max(r['ceiling'] for r in sub):.2f}x) and "
            f"{len(crit)} of {len([r for r in sweep if r['returns'] > 1.0])} r > 1 rows reach 10x within {n} cycles "
            f"(fastest: r={max(crit, key=lambda r: r['returns'])['returns']} at cycle "
            f"{min(r['cycles_to_10x_det'] for r in crit)}).")
    noisy = [row for row in sweep if "fraction" in row]
    if noisy:
        tgt = next((row for row in noisy if abs(row["returns"] - args.returns) < 1e-12), noisy[-1])
        med = f"{tgt['median_cycle']:.1f}" if tgt["median_cycle"] is not None else "n/a"
        lines.append(
            f"With noise {args.noise} on the mechanism, r={tgt['returns']} reaches 10x in {tgt['hits']}/{tgt['trials']} "
            f"trials ({tgt['fraction']:.1%}), median cycle {med}, versus "
            f"{fmt_cycles(tgt['cycles_to_10x_det'], n)} without noise.")
    counts = {lvl: sum(1 for v in verdicts if v.level == lvl) for lvl in LEVEL_NAMES}
    top = max(counts, key=lambda k: counts[k])
    total = len(verdicts)
    lines.append(
        f"Ladder: {counts['L4']} of {total} systems reach L4 (bounded RSI), {counts['L5']} reach L5; "
        f"the most populated rung is {top} ({LEVEL_NAMES[top]}) with {counts[top]}.")
    strong = sum(1 for sy in systems if sy.verifier in (Verifier.FORMAL, Verifier.EXECUTION))
    selfv = sum(1 for sy in systems if sy.verifier is Verifier.SELF)
    lines.append(
        f"Verifiers: {strong} of {total} systems are checked by formal or execution-grade signals, "
        f"{selfv} by self-assessment alone, {sum(1 for sy in systems if sy.verifier is Verifier.HUMAN)} by humans.")
    xfer_not_l5 = [sy.name for sy in systems if sy.transfers and classify(sy).level != "L5"]
    lines.append(
        f"{len(xfer_not_l5)} systems show transfer yet none is L5 ({', '.join(xfer_not_l5)}): "
        f"transfer across fixed benchmarks, or without self-reference, is not general RSI.")
    boundary = [sy.name for sy in systems if sy.mechanism is Mechanism.OPERATORS]
    if boundary:
        lines.append(
            f"Boundary case: {', '.join(boundary)} is L4 by the letter of the criteria but its self-reference is "
            f"operators-only; a depth qualifier would move it to L3.")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycles", type=int, default=30, help="cycles to simulate (default: %(default)s)")
    parser.add_argument("--returns", type=float, default=1.2,
                        help="meta-gain r for shape (c): g_{n+1} = r * g_n (default: %(default)s)")
    parser.add_argument("--noise", type=float, default=0.0,
                        help="relative Gaussian noise on each realised gain (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=200,
                        help="Monte-Carlo trials per r when --noise > 0 (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write a JSON report")
    args = parser.parse_args()
    if args.cycles < 1 or args.trials < 1:
        parser.error("--cycles and --trials must be >= 1")

    part_a = run_part_a(args)
    sweep = run_sweep(args)
    verdicts = run_part_b()

    print()
    print("=" * 96)
    print("HEADLINE")
    print("-" * 96)
    lines = headline(part_a, sweep, verdicts, SYSTEMS, args)
    for line in lines:
        print(f"  - {line}")

    if args.out:
        report = {
            "part_a": part_a, "sweep": sweep,
            "verdicts": [{"name": v.name, "level": v.level, "target": v.target.value,
                          "closure": v.closure.value, "notes": list(v.notes)} for v in verdicts],
            "headline": lines,
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
