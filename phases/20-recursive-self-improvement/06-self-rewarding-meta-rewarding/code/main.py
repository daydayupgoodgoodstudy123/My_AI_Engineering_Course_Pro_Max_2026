"""Actor/judge co-training simulator for self-rewarding loops (stdlib only).

The actor is a distribution over response styles (each with a latent true
quality and a typical length); the judge scores true quality plus a length
bias; each iteration a DPO-like multiplicative update moves the actor toward
judge-preferred styles. Regime "frozen" never corrects the judge (Self-Rewarding
LMs, Yuan et al. 2024); regime "meta" lets a grounded meta-judge shrink the
judge's length bias using a small human-labelled audit set (Meta-Rewarding).
Usage: python3 main.py [--iterations N] [--length-bias B] [--audit-size K] [--regime frozen|meta|both] [--seed S]
See docs/en.md (Phase 20 · Lesson 06).
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Sequence

DEFAULT_SEED = 7
LENGTH_SCALE = 1000.0   # chars; length bias is "quality points per 1,000 characters"
QUALITY_SD = 0.05       # within-style spread of true quality
LENGTH_SD_FRAC = 0.15   # within-style spread of length, fraction of the style mean
JUDGE_NOISE = 0.05      # judge scoring noise, quality points
LABEL_NOISE = 0.10      # noise of the human labels in the audit set, quality points


@dataclass(frozen=True)
class Style:
    """A response style: the actor chooses among these."""

    name: str
    quality: float   # latent true quality mean (0..1)
    length: float    # typical length in characters


STYLES: tuple[Style, ...] = (
    Style("concise", 0.78, 180.0),
    Style("standard", 0.72, 320.0),
    Style("thorough", 0.74, 520.0),
    Style("padded", 0.62, 780.0),
    Style("verbose", 0.50, 1100.0),
    Style("sloppy", 0.40, 110.0),
)
K = len(STYLES)


@dataclass(frozen=True)
class Response:
    style: int
    quality: float
    length: float


@dataclass
class Judge:
    """LLM-as-a-judge: sees true quality through noise, plus a length bias."""

    length_bias: float
    noise: float = JUDGE_NOISE

    def score(self, r: Response, rng: random.Random) -> float:
        return r.quality + self.length_bias * (r.length / LENGTH_SCALE) + rng.gauss(0.0, self.noise)


@dataclass(frozen=True)
class AuditItem:
    response: Response
    label: float   # noisy human quality label


@dataclass
class Config:
    iterations: int = 12
    pairs: int = 200
    length_bias: float = 0.5
    audit_size: int = 40
    lr: float = 0.6
    meta_lr: float = 0.5


@dataclass
class IterStats:
    iteration: int
    length_bias: float      # judge bias used during this iteration
    true_quality: float     # E[q] under the actor (exact, from the style mix)
    mean_length: float      # E[L] under the actor (exact)
    judge_mean: float       # mean judge score on this iteration's samples
    inflation: float        # judge_mean minus mean true quality of the same samples
    agree_train: float      # judge winner == true-quality winner, on training pairs
    agree_audit: float      # judge order == human-label order, on the fixed audit set
    win_entropy: float      # entropy (bits) of which style wins the preference pairs
    probs: tuple[float, ...]


def uniform_probs() -> list[float]:
    return [1.0 / K] * K


def sample_response(probs: Sequence[float], rng: random.Random) -> Response:
    k = rng.choices(range(K), weights=probs, k=1)[0]
    st = STYLES[k]
    q = min(1.0, max(0.0, rng.gauss(st.quality, QUALITY_SD)))
    length = max(20.0, rng.gauss(st.length, LENGTH_SD_FRAC * st.length))
    return Response(k, q, length)


def actor_expectations(probs: Sequence[float]) -> tuple[float, float]:
    tq = sum(p * s.quality for p, s in zip(probs, STYLES))
    ml = sum(p * s.length for p, s in zip(probs, STYLES))
    return tq, ml


def entropy_bits(counts: Sequence[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts if c > 0)


def dpo_like_update(probs: Sequence[float], wins: Sequence[int], losses: Sequence[int],
                    shown: Sequence[int], lr: float) -> list[float]:
    """Exponentiated-gradient step: log p_k += lr * (wins - losses) / shown.

    This is the style-level analogue of DPO raising the log-probability of the
    chosen response and lowering the rejected one.
    """
    logits = []
    for k, p in enumerate(probs):
        adv = (wins[k] - losses[k]) / shown[k] if shown[k] else 0.0
        logits.append(math.log(max(p, 1e-12)) + lr * adv)
    top = max(logits)
    weights = [math.exp(x - top) for x in logits]
    z = sum(weights)
    return [w / z for w in weights]


def make_audit_set(size: int, rng: random.Random, label_noise: float = LABEL_NOISE) -> list[AuditItem]:
    """A FIXED, human-labelled audit set drawn from the initial (uniform) style mix."""
    base = uniform_probs()
    items = []
    for _ in range(size):
        r = sample_response(base, rng)
        items.append(AuditItem(r, r.quality + rng.gauss(0.0, label_noise)))
    return items


def audit_judge(judge: Judge, audit: Sequence[AuditItem],
                rng: random.Random) -> tuple[float, float, int, int]:
    """Grounded meta-judge. Returns (beta_hat, agreement, agree_count, n_pairs).

    beta_hat regresses (judge score - human label) on normalised length: the
    slope is the judge's estimated length bias. Agreement is the share of fixed
    audit pairs the judge orders the same way the human labels do.
    """
    scores = [judge.score(it.response, rng) for it in audit]
    xs = [it.response.length / LENGTH_SCALE for it in audit]
    rs = [s - it.label for s, it in zip(scores, audit)]
    xbar = sum(xs) / len(xs)
    rbar = sum(rs) / len(rs)
    sxx = sum((x - xbar) ** 2 for x in xs)
    sxr = sum((x - xbar) * (r - rbar) for x, r in zip(xs, rs))
    beta_hat = sxr / sxx if sxx > 0 else 0.0
    agree = 0
    n_pairs = 0
    for i in range(0, len(audit) - 1, 2):
        n_pairs += 1
        if (scores[i] - scores[i + 1]) * (audit[i].label - audit[i + 1].label) > 0:
            agree += 1
    return beta_hat, (agree / n_pairs if n_pairs else 0.0), agree, n_pairs


def run_regime(regime: str, cfg: Config, seed: int) -> list[IterStats]:
    """Run one regime ("frozen" or "meta") and return per-iteration statistics.

    Row 0 is the untrained actor measured by the initial judge; rows 1..N follow
    each DPO-like update (and, in regime "meta", each judge correction).
    """
    if regime not in ("frozen", "meta"):
        raise ValueError(f"unknown regime {regime!r}")
    rng = random.Random(seed)
    audit = make_audit_set(cfg.audit_size, random.Random(seed + 1))
    probs = uniform_probs()
    judge = Judge(cfg.length_bias)
    history: list[IterStats] = []
    for it in range(cfg.iterations + 1):
        wins = [0] * K
        losses = [0] * K
        shown = [0] * K
        agree = 0
        score_sum = 0.0
        q_sum = 0.0
        for _ in range(cfg.pairs):
            a = sample_response(probs, rng)
            b = sample_response(probs, rng)
            sa = judge.score(a, rng)
            sb = judge.score(b, rng)
            winner, loser = (a, b) if sa >= sb else (b, a)
            wins[winner.style] += 1
            losses[loser.style] += 1
            shown[a.style] += 1
            shown[b.style] += 1
            if (sa - sb) * (a.quality - b.quality) > 0:
                agree += 1
            score_sum += sa + sb
            q_sum += a.quality + b.quality
        beta_hat, agree_audit, _, _ = audit_judge(judge, audit, rng)
        tq, ml = actor_expectations(probs)
        n_resp = 2 * cfg.pairs
        history.append(IterStats(
            iteration=it,
            length_bias=judge.length_bias,
            true_quality=tq,
            mean_length=ml,
            judge_mean=score_sum / n_resp,
            inflation=(score_sum - q_sum) / n_resp,
            agree_train=agree / cfg.pairs,
            agree_audit=agree_audit,
            win_entropy=entropy_bits(wins),
            probs=tuple(probs),
        ))
        if it == cfg.iterations:
            break
        probs = dpo_like_update(probs, wins, losses, shown, cfg.lr)
        if regime == "meta":
            corrected = judge.length_bias - cfg.meta_lr * beta_hat
            judge.length_bias = max(-2.0, min(2.0, corrected))
    return history


def top_style(probs: Sequence[float]) -> str:
    k = max(range(K), key=lambda i: probs[i])
    return f"{STYLES[k].name} ({probs[k]:.2f})"


def print_styles() -> None:
    print("  style      true_q  length  (judge score at bias b = true_q + b * length/1000)")
    for s in STYLES:
        print(f"  {s.name:<9}  {s.quality:>6.2f}  {s.length:>6.0f}")


def print_history(label: str, hist: Sequence[IterStats]) -> None:
    print(f"\n{label}")
    print(f"  {'it':>2}  {'bias':>6}  {'true_q':>6}  {'length':>6}  {'judge':>6}  {'inflat':>6}  "
          f"{'agr_tr':>6}  {'agr_au':>6}  {'win_H':>5}  top style (p)")
    for h in hist:
        print(f"  {h.iteration:>2}  {h.length_bias:>+6.2f}  {h.true_quality:>6.3f}  {h.mean_length:>6.0f}  "
              f"{h.judge_mean:>6.3f}  {h.inflation:>+6.3f}  {h.agree_train:>6.1%}  {h.agree_audit:>6.1%}  "
              f"{h.win_entropy:>5.2f}  {top_style(h.probs)}")


def first_iteration_below(hist: Sequence[IterStats], level: float) -> int:
    for h in hist:
        if abs(h.length_bias) < level:
            return h.iteration
    return -1


def print_headline(hists: dict[str, list[IterStats]], cfg: Config, seed: int) -> None:
    print()
    print("=" * 96)
    print("HEADLINE")
    print("-" * 96)
    for regime, hist in hists.items():
        h0, hT = hist[0], hist[-1]
        dq = hT.true_quality - h0.true_quality
        dl = hT.mean_length - h0.mean_length
        print(f"  {regime:<6} judge (bias {h0.length_bias:+.2f} -> {hT.length_bias:+.2f}): "
              f"true quality {h0.true_quality:.3f} -> {hT.true_quality:.3f} ({dq / h0.true_quality:+.1%}), "
              f"mean length {h0.mean_length:,.0f} -> {hT.mean_length:,.0f} chars ({dl / h0.mean_length:+.1%}).")
        print(f"         judge mean score moved {hT.judge_mean - h0.judge_mean:+.3f} while truth moved {dq:+.3f}; "
              f"inflation {h0.inflation:+.3f} -> {hT.inflation:+.3f}; "
              f"agreement on own pairs {h0.agree_train:.1%} -> {hT.agree_train:.1%}, "
              f"on the fixed audit set {h0.agree_audit:.1%} -> {hT.agree_audit:.1%}; "
              f"win-entropy {h0.win_entropy:.2f} -> {hT.win_entropy:.2f} bits.")
    if "meta" in hists:
        below = first_iteration_below(hists["meta"], 0.10)
        when = f"by iteration {below}" if below >= 0 else f"never within {cfg.iterations} iterations"
        print(f"  The grounded meta-judge (audit set of {cfg.audit_size} labelled items) pushed |bias| below 0.10 {when}.")
    if "frozen" in hists and "meta" in hists:
        gap = hists["meta"][-1].true_quality - hists["frozen"][-1].true_quality
        verdict = "beats" if gap > 0 else "does not beat"
        print(f"  At seed {seed} the meta regime {verdict} the frozen regime on final true quality "
              f"by {gap:+.3f} points ({hists['meta'][-1].true_quality:.3f} vs {hists['frozen'][-1].true_quality:.3f}).")
    print("=" * 96)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=12, help="DPO-like iterations (default: %(default)s)")
    parser.add_argument("--length-bias", type=float, default=0.5,
                        help="judge's initial length bias, quality points per 1,000 chars (default: %(default)s)")
    parser.add_argument("--audit-size", type=int, default=40,
                        help="human-labelled items the meta-judge may use (default: %(default)s)")
    parser.add_argument("--regime", choices=("frozen", "meta", "both"), default="both",
                        help="frozen judge, meta-rewarded judge, or both (default: %(default)s)")
    parser.add_argument("--pairs", type=int, default=200, help="preference pairs per iteration (default: %(default)s)")
    parser.add_argument("--lr", type=float, default=0.6, help="actor update step (default: %(default)s)")
    parser.add_argument("--meta-lr", type=float, default=0.5,
                        help="fraction of the estimated bias removed per iteration (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional path to write per-iteration stats as JSON")
    args = parser.parse_args()
    if args.audit_size < 2:
        parser.error("--audit-size must be at least 2")
    if args.iterations < 1 or args.pairs < 1:
        parser.error("--iterations and --pairs must be positive")

    cfg = Config(iterations=args.iterations, pairs=args.pairs, length_bias=args.length_bias,
                 audit_size=args.audit_size, lr=args.lr, meta_lr=args.meta_lr)
    regimes = ["frozen", "meta"] if args.regime == "both" else [args.regime]

    print("=" * 96)
    print("SELF-REWARDING vs META-REWARDING: actor/judge co-training (Phase 20, Lesson 06)")
    print("=" * 96)
    print(f"  seed={args.seed}  iterations={cfg.iterations}  pairs/iter={cfg.pairs}  "
          f"length_bias={cfg.length_bias:+.2f}  audit_size={cfg.audit_size}  lr={cfg.lr}  meta_lr={cfg.meta_lr}")
    print_styles()
    tq0, ml0 = actor_expectations(uniform_probs())
    print(f"  untrained actor: uniform over {K} styles -> true quality {tq0:.3f}, mean length {ml0:.0f} chars")
    print("  columns: bias = judge length bias in use; judge = mean judge score of sampled responses;")
    print("           inflat = judge mean - true mean of the same samples; agr_tr = judge agrees with truth on")
    print("           training pairs; agr_au = judge agrees with human labels on the fixed audit set;")
    print("           win_H = entropy (bits) of which style wins the preference pairs.")

    hists: dict[str, list[IterStats]] = {}
    for regime in regimes:
        hists[regime] = run_regime(regime, cfg, args.seed)
        title = {"frozen": "Regime FROZEN — the judge is never corrected (Self-Rewarding)",
                 "meta": "Regime META — a grounded meta-judge shrinks the judge's length bias each iteration"}[regime]
        print_history(title, hists[regime])

    print_headline(hists, cfg, args.seed)

    if args.out:
        payload = {regime: [asdict(h) for h in hist] for regime, hist in hists.items()}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
