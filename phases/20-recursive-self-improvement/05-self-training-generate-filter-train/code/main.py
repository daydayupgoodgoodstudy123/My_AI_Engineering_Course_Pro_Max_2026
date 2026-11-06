"""Generate -> filter -> train loop simulator (STaR / ReST-EM / rejection sampling) -- stdlib Python.

A softmax policy picks between a general method (strategy A, valid on 90% of
puzzles) and a plausible shortcut (strategy B, valid on 40%). Every iteration
samples puzzles, filters the attempts with an oracle, a noisy verifier with a
false-positive rate, or the policy's own confidence, and refits the policy to
whatever the filter accepted. The analytic one-step update predicts whether
the shortcut's share grows; the simulation checks the prediction.
Usage: python3 main.py [--iterations 8] [--filter all|oracle|noisy|self] [--fp-rate 0.3] [--samples 2000] [--seed 20]
See docs/en.md (Phase 20, Lesson 05).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Optional

DEFAULT_SEED = 20
STRATEGIES = ("A", "B")        # A = general method, B = plausible shortcut
TRICK_RATE = 0.6               # share of puzzles with a "shift" clause; the shortcut ignores it
OBSCURE_RATE = 1.0 / 6.0       # share of clauses the general method misreads -> A valid on 90%
INITIAL_SKILL = 0.8            # probability that the model executes its chosen strategy cleanly
LUCK = 0.1                     # a botched execution still hits the right digit 1 time in 10
CONF_BASE = {"A": 0.55, "B": 0.70}   # the shortcut skips the hard part, so it sounds confident
CONF_NOISE = 0.12
PRIOR_WEIGHT = 20              # pseudo-samples of the old skill level: SFT on n samples moves skill n/(n+20) of the way
AUDIT_SIZE = 200               # accepted samples re-checked against ground truth per iteration
HELDOUT_SIZE = 2000            # fresh puzzles used to measure true accuracy
FLOOR_COUNT = 10               # below this many expected accepted samples, Poisson noise rules a strategy
HUMAN_SHARE = {"A": 0.9, "B": 0.1}  # strategy mix in fresh human-written solutions


# ----------------------------------------------------------------------------
# Step 1: a synthetic task family with a latent trick
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Puzzle:
    """Report (sum of numbers + shift) mod 10. The shift clause is the trick."""
    numbers: tuple[int, ...]
    shift: int          # 0 = no clause; 1..9 = "add this before taking mod 10"
    obscure: bool       # clause phrased so that the general method misreads it

    def answer(self) -> int:
        return (sum(self.numbers) + self.shift) % 10


def make_puzzle(rng: random.Random) -> Puzzle:
    numbers = tuple(rng.randint(1, 30) for _ in range(4))
    shift = rng.randint(1, 9) if rng.random() < TRICK_RATE else 0
    obscure = shift > 0 and rng.random() < OBSCURE_RATE
    return Puzzle(numbers, shift, obscure)


def strategy_validity(strategy: str) -> float:
    """Probability that a cleanly executed strategy is right on a fresh puzzle."""
    if strategy == "A":
        return 1.0 - TRICK_RATE * OBSCURE_RATE      # 0.90
    return 1.0 - TRICK_RATE                          # 0.40


def expected_correctness(strategy: str, skill: float) -> float:
    """c_s = skill * validity + (1 - skill) * luck."""
    return skill * strategy_validity(strategy) + (1.0 - skill) * LUCK


# ----------------------------------------------------------------------------
# Step 2: a softmax policy over strategies with a temperature and a skill level
# ----------------------------------------------------------------------------

@dataclass
class Attempt:
    strategy: str
    answer: int
    correct: bool
    clean: bool          # latent: was the strategy executed without a slip?
    confidence: float    # the policy's own estimate, used by the self filter


@dataclass
class Policy:
    logits: dict[str, float]
    skill: dict[str, float]
    temperature: float = 1.0

    def probs(self) -> dict[str, float]:
        """Generation distribution softmax(z / temperature)."""
        scaled = {s: self.logits[s] / self.temperature for s in STRATEGIES}
        top = max(scaled.values())
        weights = {s: math.exp(v - top) for s, v in scaled.items()}
        total = sum(weights.values())
        return {s: w / total for s, w in weights.items()}

    def entropy_bits(self) -> float:
        return -sum(p * math.log2(p) for p in self.probs().values() if p > 0)

    def logodds_b(self) -> float:
        p = self.probs()
        return math.log(p["B"]) - math.log(p["A"])

    def choose(self, rng: random.Random) -> str:
        p = self.probs()
        return "B" if rng.random() < p["B"] else "A"

    def solve(self, puzzle: Puzzle, rng: random.Random, conf_signal: float) -> Attempt:
        strategy = self.choose(rng)
        clean = rng.random() < self.skill[strategy]
        if not clean:
            answer = rng.randrange(10)
        elif strategy == "A":
            # The general method applies the clause -- unless it misreads it.
            answer = (puzzle.answer() + rng.randint(1, 9)) % 10 if puzzle.obscure else puzzle.answer()
        else:
            answer = sum(puzzle.numbers) % 10           # the shortcut never reads the clause
        correct = answer == puzzle.answer()
        confidence = CONF_BASE[strategy] + conf_signal * (1.0 if correct else -1.0)
        confidence += rng.gauss(0.0, CONF_NOISE)
        return Attempt(strategy, answer, correct, clean, min(1.0, max(0.0, confidence)))


def initial_policy(temperature: float) -> Policy:
    return Policy(logits={s: 0.0 for s in STRATEGIES},
                  skill={s: INITIAL_SKILL for s in STRATEGIES},
                  temperature=temperature)


# ----------------------------------------------------------------------------
# Step 3: three filters and the train step
# ----------------------------------------------------------------------------

def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class FilterSpec:
    kind: str                     # oracle | noisy | self
    fp_rate: float = 0.0          # P(accept | wrong)              (noisy)
    fn_rate: float = 0.0          # P(reject | correct)            (noisy)
    fp_bias: float = 0.0          # extra P(accept) for the shortcut's plausible wrong answers
    tau: float = 0.6              # confidence threshold           (self)
    conf_signal: float = 0.03     # how far confidence moves with correctness (self)

    def label(self) -> str:
        if self.kind == "oracle":
            return "oracle (answer match)"
        if self.kind == "noisy":
            return (f"noisy (FP {self.fp_rate:.2f}, FN {self.fn_rate:.2f}"
                    + (f", bias {self.fp_bias:.2f}" if self.fp_bias else "") + ")")
        return f"self-assessment (tau {self.tau:.2f}, signal {self.conf_signal:.2f})"

    def accepts(self, attempt: Attempt, rng: random.Random) -> bool:
        if self.kind == "oracle":
            return attempt.correct
        if self.kind == "noisy":
            if attempt.correct:
                return rng.random() < 1.0 - self.fn_rate
            fp = self.fp_rate
            if attempt.strategy == "B" and attempt.clean:
                fp += self.fp_bias                   # confident, well-formed, wrong
            return rng.random() < min(1.0, fp)
        return attempt.confidence > self.tau

    def analytic_acceptance(self, strategy: str, correct_rate: float,
                            plausible_wrong_rate: float) -> float:
        """Expected P(accept) for a strategy given its correctness profile."""
        if self.kind == "oracle":
            return correct_rate
        if self.kind == "noisy":
            fp = self.fp_rate
            bias_mass = plausible_wrong_rate if strategy == "B" else 0.0
            return ((1.0 - self.fn_rate) * correct_rate
                    + fp * (1.0 - correct_rate)
                    + min(1.0 - fp, self.fp_bias) * bias_mass)
        base = CONF_BASE[strategy]
        p_hi = 1.0 - normal_cdf((self.tau - base - self.conf_signal) / CONF_NOISE)
        p_lo = 1.0 - normal_cdf((self.tau - base + self.conf_signal) / CONF_NOISE)
        return correct_rate * p_hi + (1.0 - correct_rate) * p_lo


def smoothed_share(counts: Counter, total: int) -> dict[str, float]:
    """Add-one smoothing: a strategy is never erased outright by one iteration."""
    return {s: (counts[s] + 1.0) / (total + len(STRATEGIES)) for s in STRATEGIES}


def mix_with_human(share: dict[str, float], human_mix: float) -> dict[str, float]:
    return {s: (1.0 - human_mix) * share[s] + human_mix * HUMAN_SHARE[s] for s in STRATEGIES}


def train(policy: Policy, accepted: list[Attempt], human_mix: float) -> Policy:
    """SFT on the accepted set: refit strategy logits and per-strategy skill."""
    counts = Counter(x.strategy for x in accepted)
    raw_share = smoothed_share(counts, len(accepted))
    share = mix_with_human(raw_share, human_mix)
    new_logits = {s: math.log(share[s]) for s in STRATEGIES}
    new_skill = dict(policy.skill)
    for s in STRATEGIES:
        n = counts[s]
        if n == 0:
            continue
        n_clean = sum(1 for x in accepted if x.strategy == s and x.clean)
        fitted = (n_clean + PRIOR_WEIGHT * policy.skill[s]) / (n + PRIOR_WEIGHT)
        own = (1.0 - human_mix) * raw_share[s]
        human = human_mix * HUMAN_SHARE[s]
        new_skill[s] = (own * fitted + human * 1.0) / (own + human)   # human data is cleanly executed
    return Policy(new_logits, new_skill, policy.temperature)


def predict_next_logodds(policy: Policy, acceptance: dict[str, float], human_mix: float,
                         samples: int) -> float:
    """One-step update: expected accepted count n_s = samples * g_s * a_s, the same
    add-one smoothing and human mix as train(), then log-odds under softmax(z/T)."""
    g = policy.probs()
    expected = Counter({s: samples * g[s] * acceptance[s] for s in STRATEGIES})
    share = mix_with_human(smoothed_share(expected, sum(expected.values())), human_mix)
    return (math.log(share["B"]) - math.log(share["A"])) / policy.temperature


# ----------------------------------------------------------------------------
# Step 4: run the loop and measure accuracy, entropy, contamination
# ----------------------------------------------------------------------------

@dataclass
class IterationRecord:
    iteration: int
    share_b: float
    skill_a: float
    skill_b: float
    entropy_bits: float
    accuracy: float
    n_accepted: int = 0
    wrong_accepted_share: float = 0.0     # latent truth: share of training samples that are wrong
    audit_precision: float = 1.0          # estimate from AUDIT_SIZE re-checked samples
    predicted_delta: float = 0.0          # analytic change in log-odds(B:A)
    simulated_delta: float = 0.0
    sign_match: bool = True
    at_floor: bool = False                # a strategy had < FLOOR_COUNT expected accepted samples


@dataclass
class LoopResult:
    spec: FilterSpec
    records: list[IterationRecord] = field(default_factory=list)

    @property
    def first(self) -> IterationRecord:
        return self.records[0]

    @property
    def last(self) -> IterationRecord:
        return self.records[-1]

    def sign_matches(self) -> tuple[int, int]:
        """(matched, testable): steps at the sample floor are not a test of the condition."""
        steps = [r for r in self.records[1:] if not r.at_floor]
        return sum(1 for r in steps if r.sign_match), len(steps)

    def floor_steps(self) -> int:
        return sum(1 for r in self.records[1:] if r.at_floor)

    def mean_wrong_share(self) -> float:
        return statistics.fmean(r.wrong_accepted_share for r in self.records[1:])


def measure_accuracy(policy: Policy, rng: random.Random, conf_signal: float, n: int) -> float:
    hits = sum(policy.solve(make_puzzle(rng), rng, conf_signal).correct for _ in range(n))
    return hits / n


def observed_profile(attempts: list[Attempt]) -> dict[str, tuple[float, float]]:
    """Per strategy: (correct rate, clean-but-wrong rate) in this batch."""
    out = {}
    for s in STRATEGIES:
        mine = [x for x in attempts if x.strategy == s]
        if not mine:
            k = INITIAL_SKILL
            out[s] = (expected_correctness(s, k), k * (1.0 - strategy_validity(s)))
            continue
        correct = sum(1 for x in mine if x.correct) / len(mine)
        plausible_wrong = sum(1 for x in mine if x.clean and not x.correct) / len(mine)
        out[s] = (correct, plausible_wrong)
    return out


def run_loop(spec: FilterSpec, iterations: int, samples: int, seed: int,
             temperature: float = 1.0, human_mix: float = 0.0) -> LoopResult:
    rng = random.Random(seed)
    eval_rng = random.Random(seed + 7_919)
    policy = initial_policy(temperature)
    result = LoopResult(spec)
    result.records.append(IterationRecord(
        0, policy.probs()["B"], policy.skill["A"], policy.skill["B"], policy.entropy_bits(),
        measure_accuracy(policy, eval_rng, spec.conf_signal, HELDOUT_SIZE)))
    for it in range(1, iterations + 1):
        attempts = [policy.solve(make_puzzle(rng), rng, spec.conf_signal) for _ in range(samples)]
        profile = observed_profile(attempts)
        acceptance = {s: spec.analytic_acceptance(s, *profile[s]) for s in STRATEGIES}
        before = policy.logodds_b()
        predicted = predict_next_logodds(policy, acceptance, human_mix, samples) - before
        g = policy.probs()
        at_floor = min(samples * g[s] * acceptance[s] for s in STRATEGIES) < FLOOR_COUNT

        accepted = [x for x in attempts if spec.accepts(x, rng)]
        wrong = sum(1 for x in accepted if not x.correct)
        wrong_share = wrong / len(accepted) if accepted else 0.0
        audit = rng.sample(accepted, min(AUDIT_SIZE, len(accepted))) if accepted else []
        audit_precision = (sum(1 for x in audit if x.correct) / len(audit)) if audit else 0.0

        policy = train(policy, accepted, human_mix)
        simulated = policy.logodds_b() - before
        result.records.append(IterationRecord(
            it, policy.probs()["B"], policy.skill["A"], policy.skill["B"], policy.entropy_bits(),
            measure_accuracy(policy, eval_rng, spec.conf_signal, HELDOUT_SIZE),
            len(accepted), wrong_share, audit_precision, predicted, simulated,
            (predicted >= 0) == (simulated >= 0), at_floor))
    return result


# ----------------------------------------------------------------------------
# Analytic growth conditions
# ----------------------------------------------------------------------------

def shortcut_grows(acceptance_a: float, acceptance_b: float) -> bool:
    """At temperature 1 with no human data, B's share grows iff a_B > a_A."""
    return acceptance_b > acceptance_a


def fp_bias_threshold(fp_rate: float, fn_rate: float, skill: float = INITIAL_SKILL) -> float:
    """Smallest extra false-positive rate on the shortcut's plausible wrong answers
    that makes a_B exceed a_A. Solves (1-f)c_A + q(1-c_A) = (1-f)c_B + q(1-c_B) + b * pw_B."""
    c_a = expected_correctness("A", skill)
    c_b = expected_correctness("B", skill)
    pw_b = skill * (1.0 - strategy_validity("B"))
    return ((1.0 - fn_rate - fp_rate) * (c_a - c_b)) / pw_b


def conf_signal_threshold(tau: float, skill: float = INITIAL_SKILL) -> Optional[float]:
    """Smallest confidence/correctness coupling at which self-assessment stops
    favouring the shortcut (a_A == a_B). Bisection on [0, 1]; None if never."""
    c = {s: expected_correctness(s, skill) for s in STRATEGIES}
    pw = {s: skill * (1.0 - strategy_validity(s)) for s in STRATEGIES}

    def gap(kappa: float) -> float:
        spec = FilterSpec("self", tau=tau, conf_signal=kappa)
        return (spec.analytic_acceptance("A", c["A"], pw["A"])
                - spec.analytic_acceptance("B", c["B"], pw["B"]))

    lo, hi = 0.0, 1.0
    if gap(lo) > 0:
        return 0.0
    if gap(hi) < 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if gap(mid) < 0:
            lo = mid
        else:
            hi = mid
    return hi


def temperature_fixed_point(acceptance_a: float, acceptance_b: float,
                            temperature: float) -> Optional[float]:
    """Long-run share of the shortcut when sampling at temperature T > 1.
    Logits follow z' = z / T + log(a_B / a_A), so z* = T / (T - 1) * log(a_B / a_A)
    and the generation share is sigmoid(z* / T). None when T <= 1 (no interior fixed point)."""
    if temperature <= 1.0:
        return None
    z_star = temperature / (temperature - 1.0) * math.log(acceptance_b / acceptance_a)
    return 1.0 / (1.0 + math.exp(-z_star / temperature))


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def print_loop(result: LoopResult) -> None:
    print(f"\nFilter: {result.spec.label()}")
    print(f"  {'it':>2}  {'B share':>8}  {'skill A':>7}  {'skill B':>7}  {'H bits':>6}  "
          f"{'accuracy':>8}  {'accepted':>8}  {'wrong in':>8}  {'audit':>6}  "
          f"{'d logodds':>10}  {'d logodds':>10}  sign")
    print(f"  {'':>2}  {'':>8}  {'':>7}  {'':>7}  {'':>6}  {'(held-out)':>8}  {'':>8}  "
          f"{'train set':>8}  {'prec.':>6}  {'predicted':>10}  {'simulated':>10}")
    for r in result.records:
        if r.iteration == 0:
            print(f"  {r.iteration:>2}  {r.share_b:>8.1%}  {r.skill_a:>7.3f}  {r.skill_b:>7.3f}  "
                  f"{r.entropy_bits:>6.3f}  {r.accuracy:>8.1%}  {'-':>8}  {'-':>8}  {'-':>6}  "
                  f"{'-':>10}  {'-':>10}  -")
            continue
        print(f"  {r.iteration:>2}  {r.share_b:>8.1%}  {r.skill_a:>7.3f}  {r.skill_b:>7.3f}  "
              f"{r.entropy_bits:>6.3f}  {r.accuracy:>8.1%}  {r.n_accepted:>8d}  "
              f"{r.wrong_accepted_share:>8.1%}  {r.audit_precision:>6.1%}  "
              f"{r.predicted_delta:>+10.3f}  {r.simulated_delta:>+10.3f}  "
              f"{'floor' if r.at_floor else ('ok' if r.sign_match else 'MISS')}")
    ok, n = result.sign_matches()
    floor = result.floor_steps()
    floor_note = f" ({floor} step(s) at the sample floor not counted)" if floor else ""
    print(f"  analytic sign of the shortcut's change matched the simulation in {ok}/{n} "
          f"testable steps{floor_note}; mean wrong share of training data "
          f"{result.mean_wrong_share():.1%}")


def print_conditions(args: argparse.Namespace) -> None:
    k = INITIAL_SKILL
    c_a, c_b = expected_correctness("A", k), expected_correctness("B", k)
    pw_a, pw_b = k * (1 - strategy_validity("A")), k * (1 - strategy_validity("B"))
    print("\nAnalytic growth condition (temperature 1, no human data)")
    print("  new log-odds(B:A) = old log-odds + log(a_B / a_A); the shortcut grows iff a_B > a_A")
    print(f"  initial correctness: c_A = {c_a:.3f}, c_B = {c_b:.3f} "
          f"(validity {strategy_validity('A'):.2f}/{strategy_validity('B'):.2f} x skill {k:.2f} + luck {LUCK:.2f})")
    specs = {
        "oracle": FilterSpec("oracle"),
        "noisy": FilterSpec("noisy", args.fp_rate, args.fn_rate, args.fp_bias),
        "self": FilterSpec("self", tau=args.tau, conf_signal=args.conf_signal),
    }
    for name, spec in specs.items():
        a_a = spec.analytic_acceptance("A", c_a, pw_a)
        a_b = spec.analytic_acceptance("B", c_b, pw_b)
        verdict = "GROWS" if shortcut_grows(a_a, a_b) else "shrinks"
        print(f"  {name:<6} a_A = {a_a:.3f}  a_B = {a_b:.3f}  ratio {a_b / a_a:.3f}  -> shortcut {verdict}")
    tpr = 1.0 - args.fn_rate
    print(f"  symmetric noisy filter: a_s = q + (TPR - q) * c_s, so the shortcut grows iff "
          f"q > TPR = {tpr:.2f} (current q = {args.fp_rate:.2f})")
    b_star = fp_bias_threshold(args.fp_rate, args.fn_rate)
    if b_star <= 0:
        print("  biased noisy filter: q already exceeds TPR, so the shortcut grows at any bias")
    else:
        print(f"  biased noisy filter: the shortcut grows once its plausible wrong answers pass "
              f"with extra probability b >= {b_star:.3f} (current bias {args.fp_bias:.2f})")
    if args.temperature > 1.0:
        full = {s: expected_correctness(s, 1.0) for s in STRATEGIES}
        a_a1 = specs["oracle"].analytic_acceptance("A", full["A"], 0.0)
        a_b1 = specs["oracle"].analytic_acceptance("B", full["B"], 0.0)
        fp = temperature_fixed_point(a_a1, a_b1, args.temperature)
        print(f"  temperature {args.temperature:.2f} > 1 under the oracle: logits obey "
              f"z' = z/T + log(a_B/a_A), so the shortcut settles at a share of about {fp:.1%} "
              f"instead of vanishing (entropy floor)")
    elif args.temperature < 1.0:
        print(f"  temperature {args.temperature:.2f} < 1: each refit sharpens the majority, "
              f"so entropy collapses faster than the filter alone would drive it")
    kappa = conf_signal_threshold(args.tau)
    if kappa is None:
        print(f"  self-assessment at tau {args.tau:.2f}: no confidence signal in [0, 1] "
              f"overcomes the shortcut's confidence advantage")
    else:
        print(f"  self-assessment at tau {args.tau:.2f}: the shortcut stops growing once "
              f"confidence separates correct from wrong by >= {kappa:.3f} (current {args.conf_signal:.2f})")


def print_comparison(results: list[LoopResult]) -> None:
    print("\nComparison at the final iteration")
    print(f"  {'filter':<44} {'acc 0':>7} {'acc N':>7} {'B share':>8} {'H bits':>6} "
          f"{'wrong/train':>11} {'sign ok':>8}")
    for res in results:
        ok, n = res.sign_matches()
        print(f"  {res.spec.label():<44} {res.first.accuracy:>7.1%} {res.last.accuracy:>7.1%} "
              f"{res.last.share_b:>8.1%} {res.last.entropy_bits:>6.3f} "
              f"{res.mean_wrong_share():>11.1%} {ok:>4d}/{n:<3d}")


def headline(results: list[LoopResult], iterations: int, args: argparse.Namespace) -> list[str]:
    lines = []
    by_kind = {r.spec.kind: r for r in results}
    if "oracle" in by_kind:
        r = by_kind["oracle"]
        lines.append(f"Oracle filter: accuracy {r.first.accuracy:.1%} -> {r.last.accuracy:.1%} "
                     f"over {iterations} iterations; shortcut share {r.first.share_b:.1%} -> "
                     f"{r.last.share_b:.1%}; entropy {r.first.entropy_bits:.2f} -> "
                     f"{r.last.entropy_bits:.2f} bits.")
    if "noisy" in by_kind:
        r = by_kind["noisy"]
        direction = "rose" if r.last.share_b > r.first.share_b else "fell"
        lines.append(f"Noisy filter (FP {args.fp_rate:.2f}, FN {args.fn_rate:.2f}): accuracy "
                     f"{r.first.accuracy:.1%} -> {r.last.accuracy:.1%}; the shortcut's share "
                     f"{direction} from {r.first.share_b:.1%} to {r.last.share_b:.1%}; on average "
                     f"{r.mean_wrong_share():.1%} of each training set was wrong.")
    if "self" in by_kind:
        r = by_kind["self"]
        direction = "rose" if r.last.share_b > r.first.share_b else "fell"
        lines.append(f"Self-assessment filter (tau {args.tau:.2f}): accuracy {r.first.accuracy:.1%} "
                     f"-> {r.last.accuracy:.1%}; the shortcut's share {direction} from "
                     f"{r.first.share_b:.1%} to {r.last.share_b:.1%}; skill of the general method "
                     f"{r.first.skill_a:.3f} -> {r.last.skill_a:.3f}.")
    ok = sum(res.sign_matches()[0] for res in results)
    n = sum(res.sign_matches()[1] for res in results)
    floor = sum(res.floor_steps() for res in results)
    lines.append(f"The analytic condition (shortcut grows iff a_B > a_A) predicted the sign of the "
                 f"simulated change in {ok}/{n} testable iteration steps"
                 + (f" ({floor} at the sample floor excluded)." if floor else "."))
    return lines


def build_specs(args: argparse.Namespace) -> list[FilterSpec]:
    specs = {
        "oracle": FilterSpec("oracle", conf_signal=args.conf_signal),
        "noisy": FilterSpec("noisy", args.fp_rate, args.fn_rate, args.fp_bias,
                            conf_signal=args.conf_signal),
        "self": FilterSpec("self", tau=args.tau, conf_signal=args.conf_signal),
    }
    if args.filter == "all":
        return list(specs.values())
    return [specs[args.filter]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=8,
                        help="generate-filter-train rounds (default: %(default)s)")
    parser.add_argument("--filter", choices=("oracle", "noisy", "self", "all"), default="all",
                        help="which filter(s) to run (default: %(default)s)")
    parser.add_argument("--fp-rate", type=float, default=0.3,
                        help="noisy filter: P(accept | wrong) (default: %(default)s)")
    parser.add_argument("--fn-rate", type=float, default=0.1,
                        help="noisy filter: P(reject | correct) (default: %(default)s)")
    parser.add_argument("--fp-bias", type=float, default=0.0,
                        help="noisy filter: extra P(accept) for the shortcut's plausible wrong "
                             "answers (default: %(default)s)")
    parser.add_argument("--tau", type=float, default=0.6,
                        help="self filter: accept if own confidence > tau (default: %(default)s)")
    parser.add_argument("--conf-signal", type=float, default=0.03,
                        help="how far confidence moves with correctness (default: %(default)s)")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="sampling temperature over strategies (default: %(default)s)")
    parser.add_argument("--human-mix", type=float, default=0.0,
                        help="fraction of fresh human-written data in each training set "
                             "(default: %(default)s)")
    parser.add_argument("--samples", type=int, default=2000,
                        help="attempts generated per iteration (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None,
                        help="optional path to write per-iteration records as JSON")
    args = parser.parse_args()

    print("=" * 96)
    print("GENERATE -> FILTER -> TRAIN: THE FILTER IS THE MODEL (Phase 20, Lesson 05)")
    print("=" * 96)
    print(f"  iterations {args.iterations}, samples/iteration {args.samples}, seed {args.seed}, "
          f"temperature {args.temperature:.2f}, human mix {args.human_mix:.2f}")
    print(f"  strategy A (general method) valid {strategy_validity('A'):.0%}, "
          f"strategy B (shortcut) valid {strategy_validity('B'):.0%}, "
          f"initial skill {INITIAL_SKILL:.2f}, initial share 50/50")

    results = []
    for idx, spec in enumerate(build_specs(args)):
        res = run_loop(spec, args.iterations, args.samples, args.seed * 10 + idx,
                       args.temperature, args.human_mix)
        results.append(res)
        print_loop(res)

    print_conditions(args)
    if len(results) > 1:
        print_comparison(results)

    print()
    print("=" * 96)
    print("HEADLINE")
    print("-" * 96)
    for line in headline(results, args.iterations, args):
        print(f"  {line}")

    if args.out:
        payload = [{"filter": res.spec.label(), "records": [asdict(r) for r in res.records]}
                   for res in results]
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
