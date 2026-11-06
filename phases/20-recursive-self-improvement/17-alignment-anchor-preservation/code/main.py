"""Objective-drift simulator for self-editing systems — stdlib Python.

The system's effective objective is a unit vector in d dimensions; the intended
objective is a fixed anchor vector. Each self-edit adds a random perturbation
(value drift) plus an optional systematic bias (capability-seeking pressure).
A gate then decides: none (ungated), soft (penalize but accept), hard (reject
when the cosine to the anchor or a held-out behaviour probe fails), project
(clip back onto the allowed cone). Reports drift, rejection rates and the
probe's blind spot: edits that pass the behaviour probe while violating the anchor.
Usage: python main.py [--edits 200] [--dims 32] [--bias 0.0] [--gate all]
                      [--probe-size 32] [--trials 20] [--seed 11] [--out f.json]
See docs/en.md (Phase 20 · Lesson 17, Alignment Anchors).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from operator import mul
from typing import Sequence

DEFAULT_SEED = 11
GATES: tuple[str, ...] = ("none", "soft", "hard", "project")
PROBE_ONLY = "probe"  # internal variant: behaviour probe with no oracle cosine check
Vector = list[float]


# ----------------------------------------------------------------------------
# configuration
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Config:
    """All knobs of one simulation. `threshold` is the minimum allowed cosine."""

    edits: int = 200
    dims: int = 32
    step: float = 0.05          # expected norm of the random perturbation per edit
    bias: float = 0.0           # systematic push per edit along a fixed direction
    threshold: float = 0.90     # anchor cone: accepted states must keep cos >= this
    probe_size: int = 32        # held-out behaviour items the probe can see
    probe_noise: float = 0.3    # grader noise (std) added to every item measurement
    soft_penalty: float = 0.5   # soft gate shrinks drift-increasing edits by this factor
    trials: int = 20
    seed: int = DEFAULT_SEED

    def replace(self, **changes: object) -> "Config":
        return dataclasses.replace(self, **changes)

    @property
    def threshold_deg(self) -> float:
        return angle_deg(self.threshold)


# ----------------------------------------------------------------------------
# vector helpers (no numpy)
# ----------------------------------------------------------------------------
def dot(u: Sequence[float], v: Sequence[float]) -> float:
    return sum(map(mul, u, v))


def normalize(v: Sequence[float]) -> Vector:
    n = math.sqrt(dot(v, v))
    return [x / n for x in v]


def clamp_cos(c: float) -> float:
    return max(-1.0, min(1.0, c))


def angle_deg(cos_value: float) -> float:
    return math.degrees(math.acos(clamp_cos(cos_value)))


def random_unit(rng: random.Random, dims: int) -> Vector:
    return normalize([rng.gauss(0.0, 1.0) for _ in range(dims)])


def orthogonal_unit(rng: random.Random, dims: int, ref: Vector) -> Vector:
    """A random unit vector orthogonal to `ref` (one Gram-Schmidt step)."""
    v = random_unit(rng, dims)
    c = dot(v, ref)
    return normalize([vi - c * ri for vi, ri in zip(v, ref)])


def state_at_cosine(anchor: Vector, cos_value: float, rng: random.Random) -> Vector:
    """A random unit vector at exactly the given cosine to the anchor."""
    u = orthogonal_unit(rng, len(anchor), anchor)
    s = math.sqrt(max(0.0, 1.0 - cos_value ** 2))
    return [cos_value * ai + s * ui for ai, ui in zip(anchor, u)]


def project_to_cone(v: Vector, anchor: Vector, cos_threshold: float) -> Vector:
    """Return `v` if it lies inside the cone {cos(v, anchor) >= threshold};
    otherwise the nearest point on the cone boundary (same azimuth, clipped angle)."""
    c = dot(v, anchor)
    if c >= cos_threshold:
        return v
    perp = [vi - c * ai for vi, ai in zip(v, anchor)]
    pn = math.sqrt(dot(perp, perp))
    if pn < 1e-12:
        return list(anchor)
    s = math.sqrt(max(0.0, 1.0 - cos_threshold ** 2))
    return [cos_threshold * ai + s * pi / pn for ai, pi in zip(anchor, perp)]


# ----------------------------------------------------------------------------
# the held-out behaviour probe
# ----------------------------------------------------------------------------
def chord(cos_value: float) -> float:
    """Straight-line distance between two unit vectors at the given cosine: 2 sin(theta/2)."""
    return math.sqrt(max(0.0, 2.0 - 2.0 * clamp_cos(cos_value)))


def probe_pass_threshold(cos_threshold: float, noise: float) -> float:
    """Expected RMS deviation reported by the probe for a system sitting exactly on
    the cone boundary: sqrt(chord^2 + grader-noise^2). Scores above it fail."""
    return math.sqrt(chord(cos_threshold) ** 2 + noise ** 2)


@dataclass
class Probe:
    """K held-out situations q_k. The system's response on item k is <v, q_k>, the
    intended response is <a, q_k>; the probe reports the RMS deviation between
    them (scaled by sqrt(d) so that E[score^2] = |v - a|^2 + noise^2)."""

    items: list[Vector]
    intended: list[float]
    noise: float
    pass_threshold: float
    scale: float

    @classmethod
    def build(cls, anchor: Vector, size: int, noise: float, cos_threshold: float,
              rng: random.Random) -> "Probe":
        d = len(anchor)
        scale = math.sqrt(d)
        items = [random_unit(rng, d) for _ in range(size)]
        intended = [scale * dot(anchor, q) for q in items]
        return cls(items, intended, noise, probe_pass_threshold(cos_threshold, noise), scale)

    def score(self, v: Vector, rng: random.Random) -> float:
        """Lower is better; a finite K and grader noise make it a noisy estimate."""
        total = 0.0
        for q, target in zip(self.items, self.intended):
            m = self.scale * dot(v, q) - target + rng.gauss(0.0, self.noise)
            total += m * m
        return math.sqrt(total / len(self.items))

    def passes(self, v: Vector, rng: random.Random) -> bool:
        return self.score(v, rng) <= self.pass_threshold


@dataclass
class World:
    anchor: Vector
    bias_dir: Vector
    probe: Probe


def build_world(cfg: Config) -> World:
    rng = random.Random(cfg.seed)
    anchor = random_unit(rng, cfg.dims)
    bias_dir = orthogonal_unit(rng, cfg.dims, anchor)
    probe = Probe.build(anchor, cfg.probe_size, cfg.probe_noise, cfg.threshold,
                        random.Random(cfg.seed + 1))
    return World(anchor, bias_dir, probe)


# ----------------------------------------------------------------------------
# one trial = one self-editing run under one gate
# ----------------------------------------------------------------------------
@dataclass
class Trial:
    gate: str
    cosines: list[float] = field(default_factory=lambda: [1.0])
    path_deg: float = 0.0
    rejected: int = 0
    projected: int = 0
    drifted_candidates: int = 0      # candidates with cos < threshold (oracle view)
    probe_misses: int = 0            # drifted candidates the probe still passed
    probe_false_alarms: int = 0      # in-cone candidates the probe rejected
    below_threshold_states: int = 0  # accepted states that sit outside the cone

    @property
    def final_cos(self) -> float:
        return self.cosines[-1]

    @property
    def min_cos(self) -> float:
        return min(self.cosines)

    @property
    def drift_deg(self) -> float:
        return angle_deg(self.final_cos)


def run_trial(gate: str, cfg: Config, world: World, index: int) -> Trial:
    """Common random numbers: every gate sees the same proposal stream for a
    given (seed, index), so differences between gates come from the gate."""
    rng_edit = random.Random(cfg.seed * 7919 + index)
    rng_probe = random.Random(cfg.seed * 104729 + index)
    anchor = world.anchor
    v = list(anchor)
    t = Trial(gate)
    sd = cfg.step / math.sqrt(cfg.dims)
    keep = 1.0 - cfg.soft_penalty
    for _ in range(cfg.edits):
        delta = [rng_edit.gauss(0.0, sd) + cfg.bias * b for b in world.bias_dir]
        cand = normalize([vi + di for vi, di in zip(v, delta)])
        c = dot(cand, anchor)
        probe_ok = world.probe.passes(cand, rng_probe)
        drifted = c < cfg.threshold
        if drifted:
            t.drifted_candidates += 1
            if probe_ok:
                t.probe_misses += 1
        elif not probe_ok:
            t.probe_false_alarms += 1

        if gate == "none":
            new = cand
        elif gate == "soft":
            new = cand if not drifted else normalize(
                [vi + keep * di for vi, di in zip(v, delta)])
        elif gate == "hard":
            if drifted or not probe_ok:
                t.rejected += 1
                new = v
            else:
                new = cand
        elif gate == PROBE_ONLY:
            if not probe_ok:
                t.rejected += 1
                new = v
            else:
                new = cand
        elif gate == "project":
            if drifted:
                new = project_to_cone(cand, anchor, cfg.threshold)
                t.projected += 1
            else:
                new = cand
        else:
            raise ValueError(f"unknown gate {gate!r}")

        t.path_deg += angle_deg(dot(new, v))
        v = new
        cv = dot(v, anchor)
        t.cosines.append(cv)
        if cv < cfg.threshold - 1e-9:
            t.below_threshold_states += 1
    return t


# ----------------------------------------------------------------------------
# aggregation over trials
# ----------------------------------------------------------------------------
def fit_exponent(series: Sequence[float], start: int = 10) -> float:
    """Least-squares slope of log(series[n]) against log(n) for n >= start.
    A random walk gives 0.5; a systematic push gives 1.0; a bounded gate < 0.5."""
    xs: list[float] = []
    ys: list[float] = []
    for n in range(start, len(series)):
        if series[n] > 0.0:
            xs.append(math.log(n))
            ys.append(math.log(series[n]))
    if len(xs) < 2:
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


@dataclass
class GateSummary:
    gate: str
    trials: int
    candidates: int
    rejected: int
    projected: int
    drifted_candidates: int
    probe_misses: int
    probe_false_alarms: int
    below_threshold_states: int
    final_cos_median: float
    min_cos_median: float
    min_cos_overall: float
    drift_deg_median: float
    path_deg_median: float
    exponent: float
    median_cos_curve: list[float]
    rms_angle_curve: list[float]

    @property
    def rejected_rate(self) -> float:
        return self.rejected / self.candidates

    @property
    def projected_rate(self) -> float:
        return self.projected / self.candidates

    @property
    def probe_miss_rate(self) -> float:
        return self.probe_misses / self.drifted_candidates if self.drifted_candidates else float("nan")

    @property
    def false_alarm_rate(self) -> float:
        clean = self.candidates - self.drifted_candidates
        return self.probe_false_alarms / clean if clean else float("nan")

    @property
    def below_threshold_share(self) -> float:
        return self.below_threshold_states / self.candidates

    def to_json(self) -> dict[str, object]:
        d = dataclasses.asdict(self)
        d.update(rejected_rate=self.rejected_rate, probe_miss_rate=self.probe_miss_rate,
                 false_alarm_rate=self.false_alarm_rate,
                 below_threshold_share=self.below_threshold_share)
        return d


def summarize(gate: str, trials: list[Trial]) -> GateSummary:
    n_edits = len(trials[0].cosines)
    median_curve = [statistics.median(t.cosines[i] for t in trials) for i in range(n_edits)]
    rms_curve = [math.sqrt(statistics.fmean(math.radians(angle_deg(t.cosines[i])) ** 2
                                            for t in trials)) for i in range(n_edits)]
    return GateSummary(
        gate=gate,
        trials=len(trials),
        candidates=sum(len(t.cosines) - 1 for t in trials),
        rejected=sum(t.rejected for t in trials),
        projected=sum(t.projected for t in trials),
        drifted_candidates=sum(t.drifted_candidates for t in trials),
        probe_misses=sum(t.probe_misses for t in trials),
        probe_false_alarms=sum(t.probe_false_alarms for t in trials),
        below_threshold_states=sum(t.below_threshold_states for t in trials),
        final_cos_median=statistics.median(t.final_cos for t in trials),
        min_cos_median=statistics.median(t.min_cos for t in trials),
        min_cos_overall=min(t.min_cos for t in trials),
        drift_deg_median=statistics.median(t.drift_deg for t in trials),
        path_deg_median=statistics.median(t.path_deg for t in trials),
        exponent=fit_exponent(rms_curve),
        median_cos_curve=median_curve,
        rms_angle_curve=rms_curve,
    )


def simulate(gate: str, cfg: Config, world: World | None = None) -> GateSummary:
    world = world or build_world(cfg)
    return summarize(gate, [run_trial(gate, cfg, world, i) for i in range(cfg.trials)])


# ----------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------
def print_gate_table(summaries: list[GateSummary], cfg: Config) -> None:
    print(f"\n1. Gate comparison  (medians over {cfg.trials} trials; rates pooled over "
          f"{summaries[0].candidates} candidate edits per gate)")
    print(f"  {'gate':<8} {'rejected':>22} {'final cos':>9} {'min cos':>8} "
          f"{'drift°':>7} {'path°':>7} {'n-exp':>6} {'probe-miss':>11} {'false-alarm':>12}")
    for s in summaries:
        print(f"  {s.gate:<8} {s.rejected_rate:>7.1%} ({s.rejected:>5}/{s.candidates:<5}) "
              f"{s.final_cos_median:>9.3f} {s.min_cos_median:>8.3f} {s.drift_deg_median:>7.1f} "
              f"{s.path_deg_median:>7.0f} {s.exponent:>6.2f} {s.probe_miss_rate:>11.1%} "
              f"{s.false_alarm_rate:>12.1%}")
    print("  drift°  = angle between the final objective and the anchor (net drift)")
    print("  path°   = total angular movement over all edits (movement is not drift)")
    print("  n-exp   = slope of log RMS-drift vs log edits: random walk 0.50, systematic 1.00, bounded < 0.5")
    print(f"  probe-miss  = anchor-violating candidates the {cfg.probe_size}-item behaviour probe still passed")
    print("  false-alarm = in-cone candidates the probe rejected (cost of a noisy probe)")
    print("  (gated runs ride the cone boundary, so their violating candidates sit a hair outside it,")
    print("   where any finite probe is close to a coin flip — see section 3 for resolution vs depth)")


def print_trajectory(summaries: list[GateSummary], cfg: Config) -> None:
    print("\n2. Median cosine to anchor along the run")
    header = "  " + f"{'edits':>6}" + "".join(f"{s.gate:>10}" for s in summaries)
    print(header)
    step = max(1, cfg.edits // 8)
    for n in range(0, cfg.edits + 1):
        if n == 0 or n == cfg.edits or n % step == 0:
            row = f"  {n:>6}" + "".join(f"{s.median_cos_curve[n]:>10.3f}" for s in summaries)
            print(row)
    print(f"  threshold {cfg.threshold:.2f} = {cfg.threshold_deg:.1f}° cone around the anchor")


def probe_resolution(cfg: Config, sizes: Sequence[int], offset: float = 0.05,
                     samples: int = 400) -> list[dict[str, float]]:
    """How often a K-item probe misjudges states a fixed cosine `offset` outside
    (miss) or inside (false alarm) the cone. The probe alone, no gate dynamics."""
    rows: list[dict[str, float]] = []
    for k in sizes:
        c = cfg.replace(probe_size=k)
        world = build_world(c)
        rng = random.Random(c.seed + 2)
        passed: dict[str, int] = {}
        for label, cos_value in (("outside", c.threshold - offset),
                                 ("inside", min(1.0, c.threshold + offset))):
            passed[label] = sum(world.probe.passes(state_at_cosine(world.anchor, cos_value, rng), rng)
                                for _ in range(samples))
        rows.append({"probe_size": k, "offset": offset, "samples": samples,
                     "miss_rate": passed["outside"] / samples,
                     "false_alarm_rate": 1.0 - passed["inside"] / samples})
    return rows


def probe_only_sweep(cfg: Config, sizes: Sequence[int], bias: float) -> list[dict[str, float]]:
    """A gate that has ONLY the behaviour probe (no oracle cosine), under a
    systematic capability push — what a production anchor check actually is."""
    rows: list[dict[str, float]] = []
    for k in sizes:
        c = cfg.replace(probe_size=k, trials=min(cfg.trials, 8), bias=bias)
        s = simulate(PROBE_ONLY, c, build_world(c))
        rows.append({"probe_size": k, "bias": bias, "final_cos": s.final_cos_median,
                     "worst_cos": s.min_cos_overall, "below_share": s.below_threshold_share,
                     "rejected_rate": s.rejected_rate, "probe_miss_rate": s.probe_miss_rate})
    return rows


def print_probe_section(res_rows: list[dict[str, float]], gate_rows: list[dict[str, float]],
                        cfg: Config) -> None:
    off = res_rows[0]["offset"]
    print(f"\n3a. Probe resolution  (probe alone; {int(res_rows[0]['samples'])} random states at "
          f"cosine {cfg.threshold - off:.2f} = outside the cone, {min(1.0, cfg.threshold + off):.2f} = inside)")
    print(f"  {'K':>5} {'miss (passes a drifted state)':>30} {'false alarm (rejects a good one)':>33}")
    for r in res_rows:
        print(f"  {int(r['probe_size']):>5} {r['miss_rate']:>30.1%} {r['false_alarm_rate']:>33.1%}")
    b = gate_rows[0]["bias"]
    print(f"\n3b. Probe-only gate under capability bias {b:.4f}/edit  (no oracle cosine; "
          f"{min(cfg.trials, 8)} trials per K)")
    print(f"  {'K':>5} {'final cos':>10} {'worst cos':>10} {'drifted-but-passing':>20} {'rejected':>9} {'probe-miss':>11}")
    for r in gate_rows:
        print(f"  {int(r['probe_size']):>5} {r['final_cos']:>10.3f} {r['worst_cos']:>10.3f} "
              f"{r['below_share']:>20.1%} {r['rejected_rate']:>9.1%} {r['probe_miss_rate']:>11.1%}")
    print("  drifted-but-passing = share of accepted states outside the cone although every probe check passed")
    print("  worst cos = lowest cosine reached in any trial (the oracle-backed hard gate never goes below the threshold)")


def bias_contrast(cfg: Config, bias_value: float) -> list[tuple[str, float, GateSummary]]:
    rows: list[tuple[str, float, GateSummary]] = []
    for b in (0.0, bias_value):
        c = cfg.replace(bias=b)
        world = build_world(c)
        for gate in ("none", "hard"):
            rows.append((gate, b, simulate(gate, c, world)))
    return rows


def print_bias_contrast(rows: list[tuple[str, float, GateSummary]]) -> None:
    print("\n4. Capability-bias contrast  (systematic push along a fixed direction orthogonal to the anchor)")
    print(f"  {'gate':<6} {'bias':>7} {'rejected':>9} {'final cos':>10} {'drift°':>7} {'n-exp':>6}")
    for gate, b, s in rows:
        print(f"  {gate:<6} {b:>7.4f} {s.rejected_rate:>9.1%} {s.final_cos_median:>10.3f} "
              f"{s.drift_deg_median:>7.1f} {s.exponent:>6.2f}")


def headline(summaries: dict[str, GateSummary], res_rows: list[dict[str, float]],
             gate_rows: list[dict[str, float]],
             bias_rows: list[tuple[str, float, GateSummary]], cfg: Config) -> list[str]:
    lines: list[str] = []
    none, soft = summaries.get("none"), summaries.get("soft")
    hard, proj = summaries.get("hard"), summaries.get("project")
    if none:
        lines.append(f"Ungated: median cosine to anchor falls 1.000 -> {none.final_cos_median:.3f} "
                     f"after {cfg.edits} edits ({none.drift_deg_median:.1f}° drift); RMS drift "
                     f"scales as n^{none.exponent:.2f} (random-walk prediction 0.50).")
    if soft:
        lines.append(f"Soft penalty x{cfg.soft_penalty:.1f}: rejects {soft.rejected_rate:.1%} of edits, "
                     f"yet median final cosine is {soft.final_cos_median:.3f} vs threshold "
                     f"{cfg.threshold:.2f} — a penalty slows drift, it does not bound it.")
    if hard:
        lines.append(f"Hard anchor gate: cosine never below {hard.min_cos_overall:.3f} (threshold "
                     f"{cfg.threshold:.2f}) in {hard.trials} trials, at the price of rejecting "
                     f"{hard.rejected_rate:.1%} of edits ({hard.rejected}/{hard.candidates}).")
    if proj:
        lines.append(f"Projection gate: {proj.rejected_rate:.1%} rejected, min cosine "
                     f"{proj.min_cos_overall:.3f}, but {proj.projected_rate:.1%} of edits landed "
                     f"exactly on the cone boundary — the system rides the wall.")
    if res_rows and gate_rows:
        small, large = res_rows[0], res_rows[-1]
        g_small = gate_rows[0]
        hard_floor = f"{hard.min_cos_overall:.3f}" if hard else f"{cfg.threshold:.2f}"
        lines.append(f"Probe blind spot: a {int(small['probe_size'])}-item behaviour probe passes "
                     f"{small['miss_rate']:.1%} of states {small['offset']:.2f} outside the cone "
                     f"(K={int(large['probe_size'])}: {large['miss_rate']:.1%}); under bias "
                     f"{g_small['bias']:.4f} a probe-only gate with K={int(g_small['probe_size'])} spent "
                     f"{g_small['below_share']:.1%} of its states outside the cone and bottomed out at "
                     f"cosine {g_small['worst_cos']:.3f}, while the oracle-backed hard gate never fell "
                     f"below {hard_floor}. Anchor passing is necessary, not sufficient.")
    if bias_rows:
        by = {(g, b): s for g, b, s in bias_rows}
        b = max(b for _, b, _ in bias_rows)
        n0, nb = by[("none", 0.0)], by[("none", b)]
        h0, hb = by[("hard", 0.0)], by[("hard", b)]
        lines.append(f"Capability bias {b:.4f}/edit: ungated exponent {n0.exponent:.2f} -> {nb.exponent:.2f} "
                     f"(drift becomes systematic), hard-gate rejections {h0.rejected_rate:.1%} -> "
                     f"{hb.rejected_rate:.1%} — the gate pays for pressure it cannot see.")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--edits", type=int, default=200, help="self-edits per run (default: %(default)s)")
    parser.add_argument("--dims", type=int, default=32, help="objective dimensions (default: %(default)s)")
    parser.add_argument("--bias", type=float, default=0.0,
                        help="systematic capability-seeking push per edit (default: %(default)s)")
    parser.add_argument("--gate", choices=GATES + ("all",), default="all",
                        help="which gate(s) to run (default: %(default)s)")
    parser.add_argument("--probe-size", type=int, default=32,
                        help="held-out behaviour items in the probe (default: %(default)s)")
    parser.add_argument("--trials", type=int, default=20, help="Monte-Carlo trials (default: %(default)s)")
    parser.add_argument("--threshold", type=float, default=0.90,
                        help="minimum cosine to the anchor (default: %(default)s)")
    parser.add_argument("--step", type=float, default=0.05,
                        help="random perturbation norm per edit (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional JSON file for the summaries")
    args = parser.parse_args()

    cfg = Config(edits=args.edits, dims=args.dims, step=args.step, bias=args.bias,
                 threshold=args.threshold, probe_size=args.probe_size, trials=args.trials,
                 seed=args.seed)
    gates = list(GATES) if args.gate == "all" else [args.gate]
    world = build_world(cfg)

    print("=" * 96)
    print("OBJECTIVE DRIFT UNDER SELF-EDITS (Phase 20, Lesson 17 — alignment anchors)")
    print("=" * 96)
    print(f"config: edits={cfg.edits} dims={cfg.dims} step={cfg.step:.3f} bias={cfg.bias:.4f} "
          f"threshold={cfg.threshold:.2f} ({cfg.threshold_deg:.1f}°) trials={cfg.trials} seed={cfg.seed}")
    print(f"probe : {cfg.probe_size} held-out items, grader noise {cfg.probe_noise:.2f}, "
          f"pass if RMS deviation <= {world.probe.pass_threshold:.3f} "
          f"(chord at threshold {chord(cfg.threshold):.3f})")

    summaries = {g: simulate(g, cfg, world) for g in gates}
    ordered = [summaries[g] for g in gates]
    print_gate_table(ordered, cfg)
    print_trajectory(ordered, cfg)

    sizes = sorted({4, 16, 64, 256, cfg.probe_size})
    bias_value = cfg.bias if cfg.bias > 0 else 0.005
    res_rows = probe_resolution(cfg, sizes)
    gate_rows = probe_only_sweep(cfg, sizes, bias_value)
    print_probe_section(res_rows, gate_rows, cfg)

    bias_rows = bias_contrast(cfg, bias_value)
    print_bias_contrast(bias_rows)

    print()
    print("=" * 96)
    print("HEADLINE")
    print("-" * 96)
    for line in headline(summaries, res_rows, gate_rows, bias_rows, cfg):
        print(f"  * {line}")

    if args.out:
        payload = {
            "config": dataclasses.asdict(cfg),
            "gates": {g: s.to_json() for g, s in summaries.items()},
            "probe_resolution": res_rows,
            "probe_only_sweep": gate_rows,
            "bias_contrast": [{"gate": g, "bias": b, **s.to_json()} for g, b, s in bias_rows],
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
