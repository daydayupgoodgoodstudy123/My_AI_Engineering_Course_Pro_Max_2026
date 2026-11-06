"""Control-protocol simulator for a self-improvement loop (stdlib only).

Each cycle an untrusted improver U proposes k edits; every edit carries a
benign value and, with probability --attack-rate, a hidden harm flag (an
adaptive attacker hides harm in edits that look innocuous). A trusted monitor
T scores suspicion with a given AUC; a perfect human audits what the protocol
sends them. Four protocols are compared on safety (P(no harmful edit is
committed)), usefulness (benign value kept when U is honest), human audits
used, and a safety-usefulness frontier across audit budgets.
Usage: python3 main.py [--cycles 20] [--edits 8] [--attack-rate 0.02]
       [--monitor-auc 0.8] [--audit-budget 0.05] [--trials 300] [--adaptive]
See docs/en.md (Phase 20 · Lesson 19).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass, replace
from statistics import NormalDist
from typing import Sequence

DEFAULT_SEED = 7
VALUE_LO, VALUE_HI = 0.2, 1.0        # true benign value of one edit
HARM_INFLATION = 1.0                 # a harmful edit reports (1 + this) x its value to the loop's evaluator
TRUSTED_VALUE_FRACTION = 0.3         # value of T's conservative replacement edit, relative to U's
ATTACKER_INSIGHT = 0.8               # correlation between the adaptive attacker's guess and T's base noise
FRONTIER_BUDGETS = (0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.0)
AUC_GRID = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0)
PROTOCOLS = ("no-oversight", "trusted-monitoring", "defer-to-trusted", "tm+pause")
_NORMAL = NormalDist()


@dataclass(frozen=True)
class Config:
    cycles: int = 20
    edits: int = 8
    attack_rate: float = 0.02
    monitor_auc: float = 0.8
    audit_budget: float = 0.05
    defer_budget: float = 0.20
    jump: float = 0.30            # pause if a cycle's accepted gain exceeds the previous one by more than this
    suspicious_max: int = 4       # pause if more than this many edits fall in the suspicious band
    trials: int = 300
    seed: int = DEFAULT_SEED
    adaptive: bool = False


@dataclass(frozen=True)
class Edit:
    value: float      # true benign value
    harmful: bool     # hidden flag; only a human audit reveals it
    noise: float      # the monitor's base suspicion for this edit, N(0, 1)


@dataclass
class Outcome:
    safe: bool
    caught: bool
    harm_committed: bool
    kept: float
    maximum: float
    audits: int
    pauses: int
    stop_cycle: int


# --------------------------------------------------------------------------
# Monitor model: benign scores ~ N(0, 1), harmful scores ~ N(d', 1).
# --------------------------------------------------------------------------

def dprime_from_auc(auc: float) -> float:
    """Separation d' such that a Gaussian monitor has the given AUC."""
    if auc >= 1.0:
        return math.inf
    if auc <= 0.5:
        return 0.0
    return math.sqrt(2.0) * _NORMAL.inv_cdf(auc)


def threshold_for_budget(budget: float) -> float:
    """Score above which a BENIGN edit lands with probability `budget`."""
    if budget >= 1.0:
        return -math.inf
    if budget <= 0.0:
        return math.inf
    return _NORMAL.inv_cdf(1.0 - budget)


def suspicion(edit: Edit, dprime: float) -> float:
    return edit.noise + (dprime if edit.harmful else 0.0)


def apparent_value(edit: Edit) -> float:
    """What the loop's own evaluator reports; harmful edits inflate it."""
    return edit.value * (1.0 + HARM_INFLATION) if edit.harmful else edit.value


# --------------------------------------------------------------------------
# The untrusted improver: one stream of edits per trial.
# --------------------------------------------------------------------------

def generate_stream(rng: random.Random, cfg: Config) -> list[list[Edit]]:
    stream: list[list[Edit]] = []
    for _ in range(cfg.cycles):
        values = [rng.uniform(VALUE_LO, VALUE_HI) for _ in range(cfg.edits)]
        noise = [rng.gauss(0.0, 1.0) for _ in range(cfg.edits)]
        flags = [rng.random() < cfg.attack_rate for _ in range(cfg.edits)]
        guess_noise = [rng.gauss(0.0, 1.0) for _ in range(cfg.edits)]  # drawn always: keeps streams aligned
        if cfg.adaptive and any(flags):
            # Same number of harmful edits, but placed where the attacker guesses T will look least.
            spread = math.sqrt(1.0 - ATTACKER_INSIGHT ** 2)
            guess = [ATTACKER_INSIGHT * z + spread * g for z, g in zip(noise, guess_noise)]
            quiet = sorted(range(cfg.edits), key=guess.__getitem__)[: sum(flags)]
            flags = [i in quiet for i in range(cfg.edits)]
        stream.append([Edit(v, h, z) for v, h, z in zip(values, flags, noise)])
    return stream


def honest_view(stream: Sequence[Sequence[Edit]]) -> list[list[Edit]]:
    """The same edits with every harm flag off: how the loop behaves when U is honest."""
    return [[replace(e, harmful=False) for e in cycle] for cycle in stream]


# --------------------------------------------------------------------------
# Protocols
# --------------------------------------------------------------------------

def should_pause(prev_gain: float | None, gain: float, n_suspicious: int, cfg: Config) -> list[str]:
    """Inter-cycle audit trigger (Phase 15 · 07 pause spec, applied to one cycle)."""
    reasons: list[str] = []
    if prev_gain is not None and prev_gain > 0 and gain > (1.0 + cfg.jump) * prev_gain:
        reasons.append(f"gain jump {gain / prev_gain - 1.0:+.1%} > {cfg.jump:.0%}")
    if n_suspicious > cfg.suspicious_max:
        reasons.append(f"{n_suspicious} suspicious edits > {cfg.suspicious_max}")
    return reasons


def run_protocol(stream: Sequence[Sequence[Edit]], cfg: Config, protocol: str,
                 budget: float | None = None) -> Outcome:
    """Play one run of the loop under a protocol. Stops at the first caught or committed harm."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}")
    monitor = protocol != "no-oversight"
    defer = protocol == "defer-to-trusted"
    pause = protocol == "tm+pause"
    budget = cfg.audit_budget if budget is None else budget
    dprime = dprime_from_auc(cfg.monitor_auc)
    tau_audit = threshold_for_budget(budget) if monitor else math.inf
    tau_defer = threshold_for_budget(cfg.defer_budget) if (defer or pause) else math.inf

    maximum = sum(e.value for cycle in stream for e in cycle if not e.harmful)
    kept = 0.0
    audits = 0
    pauses = 0
    prev_gain: float | None = None

    def finish(safe: bool, caught: bool, cycle: int) -> Outcome:
        return Outcome(safe, caught, not safe, kept, maximum, audits, pauses, cycle)

    for cycle_no, edits in enumerate(stream, start=1):
        staged: list[tuple[Edit, bool]] = []      # (edit, replaced_by_T)
        gain = 0.0
        n_suspicious = 0
        audited_here = 0
        for e in edits:
            s = suspicion(e, dprime)
            if s > tau_defer:
                n_suspicious += 1
            if s > tau_audit:
                audits += 1
                audited_here += 1
                if e.harmful:
                    return finish(True, True, cycle_no)       # the human catches it; the run stops safely
                staged.append((e, False))
                gain += apparent_value(e)
            elif defer and s > tau_defer:
                staged.append((e, True))                      # T's conservative edit instead of U's
                gain += e.value * TRUSTED_VALUE_FRACTION
            else:
                staged.append((e, False))
                gain += apparent_value(e)
        if pause and should_pause(prev_gain, gain, n_suspicious, cfg):
            pauses += 1
            audits += len(edits) - audited_here              # humans audit the whole cycle
            if any(e.harmful for e, replaced in staged if not replaced):
                return finish(True, True, cycle_no)
        prev_gain = gain
        for e, replaced in staged:                           # the cycle is merged
            if replaced:
                kept += e.value * TRUSTED_VALUE_FRACTION
            elif e.harmful:
                return finish(False, False, cycle_no)        # harm committed: the run is compromised
            else:
                kept += e.value
    return finish(True, False, len(stream))


# --------------------------------------------------------------------------
# Monte-Carlo evaluation
# --------------------------------------------------------------------------

def evaluate(protocol: str, attack_streams: Sequence[Sequence[Sequence[Edit]]],
             honest_streams: Sequence[Sequence[Sequence[Edit]]], cfg: Config,
             budget: float | None = None) -> dict:
    attack = [run_protocol(s, cfg, protocol, budget) for s in attack_streams]
    honest = [run_protocol(s, cfg, protocol, budget) for s in honest_streams]
    n = len(attack)
    caught_cycles = [o.stop_cycle for o in attack if o.caught]
    no_harm = sum(1 for s in attack_streams if not any(e.harmful for c in s for e in c))
    return {
        "protocol": protocol,
        "budget": cfg.audit_budget if budget is None else budget,
        "trials": n,
        "safety": sum(o.safe for o in attack) / n,
        "safe_count": sum(o.safe for o in attack),
        "caught_count": len(caught_cycles),
        "unsafe_count": sum(o.harm_committed for o in attack),
        "no_harm_count": no_harm,
        "median_catch_cycle": statistics.median(caught_cycles) if caught_cycles else None,
        "usefulness": statistics.fmean(o.kept / o.maximum for o in honest),
        "audits_honest": statistics.fmean(o.audits for o in honest),
        "pauses_honest": statistics.fmean(o.pauses for o in honest),
        "audits_attack": statistics.fmean(o.audits for o in attack),
        "pauses_attack": statistics.fmean(o.pauses for o in attack),
    }


def theoretical_no_oversight_safety(cfg: Config) -> float:
    return (1.0 - cfg.attack_rate) ** (cfg.cycles * cfg.edits)


def simulate(cfg: Config) -> dict:
    rng = random.Random(cfg.seed)
    attack_streams = [generate_stream(rng, cfg) for _ in range(cfg.trials)]
    honest_streams = [honest_view(s) for s in attack_streams]
    other_cfg = replace(cfg, adaptive=not cfg.adaptive)      # the contrast attacker, same seed
    other_rng = random.Random(cfg.seed)
    other_streams = [generate_stream(other_rng, other_cfg) for _ in range(cfg.trials)]

    protocols = {p: evaluate(p, attack_streams, honest_streams, cfg) for p in PROTOCOLS}
    frontier = [
        {
            "budget": b,
            "tm": evaluate("trusted-monitoring", attack_streams, honest_streams, cfg, b),
            "dtt": evaluate("defer-to-trusted", attack_streams, honest_streams, cfg, b),
        }
        for b in FRONTIER_BUDGETS
    ]
    auc_rows = []
    for auc in AUC_GRID:
        cfg_auc = replace(cfg, monitor_auc=auc)
        other_auc = replace(other_cfg, monitor_auc=auc)
        mine = evaluate("trusted-monitoring", attack_streams, honest_streams[:1], cfg_auc)
        other = evaluate("trusted-monitoring", other_streams, honest_streams[:1], other_auc)
        auc_rows.append({"auc": auc, "mine": mine["safety"], "other": other["safety"]})
    return {
        "config": asdict(cfg),
        "theory_no_oversight": theoretical_no_oversight_safety(cfg),
        "protocols": protocols,
        "frontier": frontier,
        "auc_table": auc_rows,
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def print_report(res: dict) -> None:
    cfg = Config(**res["config"])
    n_edits = cfg.cycles * cfg.edits
    attacker = "adaptive (hides harm where T looks least)" if cfg.adaptive else "non-adaptive (harm placed at random)"
    print("=" * 78)
    print("AI CONTROL FOR AN IMPROVEMENT LOOP (Phase 20, Lesson 19)")
    print("=" * 78)
    print(f"  cycles={cfg.cycles}  edits/cycle={cfg.edits}  ({n_edits} edits per run)  trials={cfg.trials}  seed={cfg.seed}")
    print(f"  attack rate={cfg.attack_rate:.1%} per edit   attacker: {attacker}")
    print(f"  monitor AUC={cfg.monitor_auc:.2f} (d'={dprime_from_auc(cfg.monitor_auc):.2f})   "
          f"audit budget={cfg.audit_budget:.1%}   defer band={cfg.defer_budget:.1%}")
    print(f"  pause rule: gain jump > {cfg.jump:.0%} or > {cfg.suspicious_max} suspicious edits in a cycle")

    print("\nPROTOCOLS  (safety: attacking U; usefulness: honest U; audits = human audits per run)")
    print(f"  {'protocol':<20} {'safety':>8} {'safe/n':>9} {'caught':>7} {'unsafe':>7} {'useful':>8} "
          f"{'audits':>7} {'pauses':>7} {'med.catch':>10}")
    for p in PROTOCOLS:
        r = res["protocols"][p]
        med = "-" if r["median_catch_cycle"] is None else f"{r['median_catch_cycle']:.0f}"
        print(f"  {p:<20} {r['safety']:>8.1%} {r['safe_count']:>4}/{r['trials']:<4} {r['caught_count']:>7} "
              f"{r['unsafe_count']:>7} {r['usefulness']:>8.1%} {r['audits_honest']:>7.1f} "
              f"{r['pauses_honest']:>7.2f} {med:>10}")
    r0 = res["protocols"]["no-oversight"]
    print(f"  theory for no-oversight: (1 - {cfg.attack_rate})^{n_edits} = {res['theory_no_oversight']:.1%}; "
          f"runs with zero harmful edits: {r0['no_harm_count']}/{r0['trials']}")

    print("\nSAFETY-USEFULNESS FRONTIER across audit budgets  (TM = trusted monitoring, DTT = + defer-to-trusted)")
    print(f"  {'budget':>7} {'TM safety':>10} {'TM useful':>10} {'TM audits':>10} "
          f"{'DTT safety':>11} {'DTT useful':>11} {'DTT audits':>11}")
    for row in res["frontier"]:
        tm, dtt = row["tm"], row["dtt"]
        print(f"  {row['budget']:>7.1%} {tm['safety']:>10.1%} {tm['usefulness']:>10.1%} {tm['audits_honest']:>10.1f} "
              f"{dtt['safety']:>11.1%} {dtt['usefulness']:>11.1%} {dtt['audits_honest']:>11.1f}")

    mine_label = "adaptive" if cfg.adaptive else "non-adaptive"
    other_label = "non-adaptive" if cfg.adaptive else "adaptive"
    print(f"\nMONITOR QUALITY  (trusted monitoring at {cfg.audit_budget:.1%} audit budget; safety)")
    print(f"  {'AUC':>5} {mine_label:>14} {other_label:>14}")
    for row in res["auc_table"]:
        print(f"  {row['auc']:>5.2f} {row['mine']:>14.1%} {row['other']:>14.1%}")

    print_headline(res)


def _first_budget_reaching(frontier: list[dict], key: str, target: float) -> float | None:
    for row in frontier:
        if row[key]["safety"] >= target:
            return row["budget"]
    return None


def print_headline(res: dict) -> None:
    cfg = Config(**res["config"])
    P = res["protocols"]
    s0, s1, s2, s3 = (P[p]["safety"] for p in PROTOCOLS)
    u1, u2 = P["trusted-monitoring"]["usefulness"], P["defer-to-trusted"]["usefulness"]
    a1, a3 = P["trusted-monitoring"]["audits_honest"], P["tm+pause"]["audits_honest"]
    auc_row = next(r for r in res["auc_table"] if abs(r["auc"] - cfg.monitor_auc) < 1e-9)
    non_adaptive, adaptive = (auc_row["other"], auc_row["mine"]) if cfg.adaptive else (auc_row["mine"], auc_row["other"])
    b90 = _first_budget_reaching(res["frontier"], "tm", 0.9)
    b90_txt = f"an audit budget of {b90:.0%}" if b90 is not None else "more than a 100% audit budget (not reached)"
    print()
    print("=" * 78)
    print("HEADLINE")
    print("-" * 78)
    print(f"  No oversight: safety {s0:.1%} (theory {res['theory_no_oversight']:.1%}) at usefulness "
          f"{P['no-oversight']['usefulness']:.1%}; every harmful edit is committed.")
    print(f"  Trusted monitoring with AUC {cfg.monitor_auc:.2f} and a {cfg.audit_budget:.1%} audit budget reaches safety "
          f"{s1:.1%} at usefulness {u1:.1%}, spending {a1:.1f} human audits per run.")
    if cfg.defer_budget > cfg.audit_budget:
        print(f"  Defer-to-trusted ({cfg.defer_budget:.0%} band) trades {u1 - u2:.1%} of usefulness for "
              f"{s2 - s1:+.1%} safety (now {s2:.1%}).")
    else:
        print(f"  Defer-to-trusted changes nothing here: the {cfg.audit_budget:.0%} audit budget already covers the "
              f"{cfg.defer_budget:.0%} suspicious band, so no edit is deferred.")
    labour = f"{a3 / a1:.1f}x the plain-monitoring labour" if a1 > 0 else "with no plain-monitoring audits to compare"
    print(f"  The inter-cycle pause rule lifts safety to {s3:.1%} ({s3 - s1:+.1%}) but costs {a3:.1f} audits per honest run "
          f"({P['tm+pause']['pauses_honest']:.2f} false pauses), {labour}.")
    higher = next((r for r in res["auc_table"] if r["auc"] > cfg.monitor_auc + 1e-9), None)
    tail = (f"; raising AUC to {higher['auc']:.2f} gives {higher['mine']:.1%} against the {mine_label(cfg)} attacker"
            if higher else "")
    print(f"  An adaptive attacker at AUC {cfg.monitor_auc:.2f} cuts trusted-monitoring safety from {non_adaptive:.1%} to "
          f"{adaptive:.1%}{tail}.")
    print(f"  Reaching 90% safety with this monitor needs {b90_txt}: monitor quality, not budget, is the lever.")


def mine_label(cfg: Config) -> str:
    return "adaptive" if cfg.adaptive else "non-adaptive"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycles", type=int, default=Config.cycles, help="improvement cycles per run (default: %(default)s)")
    parser.add_argument("--edits", type=int, default=Config.edits, help="edits proposed per cycle (default: %(default)s)")
    parser.add_argument("--attack-rate", type=float, default=Config.attack_rate,
                        help="probability an edit is harmful (default: %(default)s)")
    parser.add_argument("--monitor-auc", type=float, default=Config.monitor_auc,
                        help="AUC of the trusted monitor, 0.5 = coin flip, 1.0 = perfect (default: %(default)s)")
    parser.add_argument("--audit-budget", type=float, default=Config.audit_budget,
                        help="fraction of benign edits that trigger a human audit (default: %(default)s)")
    parser.add_argument("--defer-budget", type=float, default=Config.defer_budget,
                        help="fraction of benign edits in the suspicious band (default: %(default)s)")
    parser.add_argument("--jump", type=float, default=Config.jump,
                        help="pause when a cycle's accepted gain jumps by more than this (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=Config.trials, help="Monte-Carlo trials (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--adaptive", action="store_true", help="attacker hides harm in edits it expects T to score low")
    parser.add_argument("--out", type=str, default=None, help="optional path to write the full results as JSON")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    cfg = Config(cycles=args.cycles, edits=args.edits, attack_rate=args.attack_rate,
                 monitor_auc=args.monitor_auc, audit_budget=args.audit_budget,
                 defer_budget=args.defer_budget, jump=args.jump, trials=args.trials,
                 seed=args.seed, adaptive=args.adaptive)
    res = simulate(cfg)
    print_report(res)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(f"\n  results written to {args.out}")


if __name__ == "__main__":
    main()
