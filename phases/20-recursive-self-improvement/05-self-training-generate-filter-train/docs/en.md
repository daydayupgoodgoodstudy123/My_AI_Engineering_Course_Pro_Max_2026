# STaR, ReST-EM and Rejection-Sampling Loops: The Filter Is the Model

> Every frontier post-training stack now contains a loop that generates candidate answers, keeps the ones that pass a check, and fine-tunes on the survivors. STaR (Zelikman et al., 2022, arXiv:2203.14465) did it with answer matching on GSM8K and CommonsenseQA; ReST-EM (Singh et al., TMLR 2024, arXiv:2312.06585) scaled it to PaLM 2 on MATH and APPS and reported that gains saturate after a few iterations and overfit small problem sets; Llama 2 (July 2023) and Llama 3 (July 2024) used rejection sampling as a core post-training step. Chen, Wang and Qu's survey of 1,250 papers (arXiv:2607.07663, July 2026) calls this bounded self-refinement "industrial practice" and ranks the checks that drive it from formal verifiers down to self-assessment. This lesson shows why the ranking is the whole story: the loop converges to whatever the filter accepts, not to what is true.

**Type:** Build
**Languages:** Python (stdlib, generate-filter-train loop simulator)
**Prerequisites:** Phase 10 · 06 (SFT), Phase 15 · 02 (STaR family), Lesson 04 of this phase
**Time:** ~75 minutes

## Learning Objectives

- Describe STaR, ReST-EM and rejection-sampling fine-tuning as one generate → filter → train loop, and name what each added.
- Write the loop as a distribution-reweighting operator and derive the one-step update for a two-strategy policy.
- State the condition under which a wrong-but-plausible strategy grows under oracle, noisy and self-assessment filters, and check it against a simulation.
- Place answer matching, Lean verification, code execution, LLM judges and self-assessment on the verification hierarchy and predict a loop's behaviour from the placement.
- Explain why gains saturate (exhausted problems, entropy collapse) and what temperature, fresh human data and a precision audit each buy.
- Audit a self-training pipeline's filter with a held-out truth set and report its precision per iteration.

## The Problem

Phase 15 · 02 introduced STaR as the minimum viable self-improvement loop and showed that it keeps shortcut rationales that happen to land on the right answer. Lesson 04 of this phase showed the one loop that has fully closed, self-play, and why it closed: the game rules are a perfect verifier. This lesson sits between the two. Generate → filter → train is the form in which self-improvement actually ships in 2026 post-training, and in almost every shipping instance the filter is not perfect. Unit tests cover some cases. Reward models have blind spots. LLM judges prefer confident prose. The model's own confidence is nearly free to compute and nearly worthless as a check.

The question this lesson answers precisely: when the filter is imperfect, what does the loop converge to? The answer is uncomfortable and exact. The loop is a fixed-point iteration on the policy, and the fixed point is determined by the filter's acceptance rates, not by correctness. A filter that accepts the wrong strategy's outputs more often than the right strategy's outputs makes the model worse every iteration, with training loss falling the whole time. The filter is the model.

## The Concept

### One loop, three names

| Method | Generate | Filter | Train | What it added |
|---|---|---|---|---|
| STaR (Zelikman et al., 2022, arXiv:2203.14465) | one rationale + answer per problem | keep if the answer matches the label | fine-tune the base model on kept rationales; repeat | rationalization: on failures, show the answer and ask for a rationale that reaches it |
| ReST-EM (Singh et al., TMLR 2024, arXiv:2312.06585) | many solutions per problem from the current policy | binary reward (answer match, test pass) | fine-tune the *base* model on all accepted samples (E-step, then M-step) | scale: PaLM 2 on MATH and APPS beat fine-tuning on human data; gains saturate after a few iterations; small problem sets overfit |
| Rejection-sampling fine-tuning (Llama 2, arXiv:2307.09288; Llama 3, arXiv:2407.21783) | K samples per prompt | reward model picks the best; code and math add execution checks | SFT on the selected samples, then preference optimization | industrial scale; the reward model is the filter, so its errors are the training signal |

Three details matter for what follows. First, ReST-EM retrains from the base model each iteration rather than continuing from the previous checkpoint; the authors found this reduces overfitting to self-generated data. Second, all three train on accepted samples with equal weight: a wrong sample that passes the filter is indistinguishable from a right one at training time. Third, none of them has any signal about problems the model never solves; those problems contribute nothing to the training set. The first fact is a design choice. The second and third are the mechanics of everything below.

### The loop as a reweighting operator

Write the policy as a distribution π over ways of solving a problem. The simplest honest abstraction, and the one the simulator uses, is a distribution over *strategies*: a general method A that is valid on 90% of puzzles and a plausible shortcut B that is valid on 40%. Each strategy s has an acceptance rate a_s, the probability that a sample produced by s passes the filter. One iteration does this:

```text
generate:  draw strategy s ~ π, produce an attempt
filter:    keep the attempt with probability a_s
train:     refit π to the kept attempts   =>   π'(s) = π(s) · a_s / Σ_t π(t) · a_t
```

The train step is an SFT step in the limit of enough data: maximum likelihood on the kept set reproduces the kept set's strategy mix. So one iteration multiplies each strategy's probability by its acceptance rate and renormalizes. That is a distribution-reweighting operator, T(π) ∝ π · a, and its fixed points are the strategies with the highest acceptance rate. With a perfect filter a_s equals the strategy's correctness c_s, and the loop converges toward correct-answer mass. With any other filter it converges toward *accepted* mass, which is a different thing.

### The one-step update for two strategies

For two strategies the operator is one number. Take the log-odds z = log π(B) − log π(A). Then

```text
z' = z + log(a_B / a_A)
```

so the shortcut's share grows if and only if a_B > a_A, and the speed is |log(a_B / a_A)| per iteration. Now plug in the filters.

**Oracle** (answer match against ground truth, STaR's filter). a_s = c_s. With c_A = 0.74 and c_B = 0.34 at the simulator's starting skill, log(0.34 / 0.74) = −0.78 per iteration: the shortcut's odds shrink by a factor of 0.46 each round and its share goes 50% → 31% → 17% → 10% → 4% → 1%.

**Symmetric noisy filter** with true-positive rate TPR = 1 − FN and false-positive rate q. Then a_s = TPR · c_s + q · (1 − c_s) = q + (TPR − q) · c_s. This is affine in c_s with slope TPR − q, so

```text
a_B > a_A   <=>   (TPR − q) · (c_B − c_A) > 0   <=>   q > TPR        (because c_B < c_A)
```

A uniformly leaky filter never reverses the loop unless it is worse than a coin flip. What it does is slow the loop (with q = 0.3 and TPR = 0.9 the ratio is 0.504 / 0.744 = 0.68 per iteration instead of 0.46) and contaminate the training set: at the first iteration 22.5% of the kept samples are wrong, and the model learns from them as if they were right.

**Biased noisy filter.** Real filters are not uniformly leaky. A test suite that covers the common cases passes a shortcut's wrong answers, which fail only on edge cases, far more often than it passes a garbled answer. An LLM judge passes fluent, confident wrong answers more often than hesitant ones. Model this as an extra false-positive probability b on the shortcut's plausible wrong answers. The condition becomes

```text
b* = (TPR − q) · (c_A − c_B) / P(plausible wrong | B) = 0.6 · 0.40 / 0.48 = 0.50
```

Above b = 0.5 the shortcut grows even though the filter is informative on average. This is how confidently-wrong modes get amplified: not because the filter is bad everywhere, but because its errors are correlated with one mode.

**Self-assessment** (accept if the policy's own confidence exceeds τ). The acceptance rate is a_s = P(confidence > τ | s). If confidence barely depends on correctness and the shortcut sounds more confident (it skips the hard part), then a_B > a_A regardless of correctness. In the simulator the shortcut's acceptance is 0.77 against the general method's 0.39: the shortcut's odds double every iteration, and its share goes 50% → 66% → 79% → 88% → 93% → 97% → 99%. Accuracy falls from 54% to 36%. Nothing in the loop's own telemetry flags this: the accepted count rises every iteration, the kept set looks consistent, and the model's confidence on its own outputs goes up.

### The verification hierarchy

Chen, Wang and Qu (arXiv:2607.07663) order the signals that drive self-improvement and report that the strength of demonstrated self-improvement follows the order. Read the table as a prediction of what the loop converges to.

| Tier | Signal | Acceptance a_s is... | 2024–2026 example | What the loop does |
|---|---|---|---|---|
| 1 | Formal verifier | exactly c_s | AlphaProof (Lean-checked proofs, July 2024; Lesson 04) | converges to correct-answer mass; limited only by what can be formalized |
| 2 | Execution / tests | c_s plus a leak on cases the tests miss | code-execution RL; Absolute Zero Reasoner's code executor (Lesson 07); rejection sampling on unit tests | correct if coverage is uniform; amplifies shortcuts that fail only off-coverage (b > b*) |
| 2 | Answer match | c_s on the labelled set, undefined off it | STaR, ReST-EM | correct on the labelled distribution; silent on unsolved problems (saturation) |
| 3 | Judge / reward model / rubric | correlated with style as much as correctness | LLM-as-judge; Llama 2/3 reward models; Lesson 06's self-rewarding | follows the judge's biases; co-evolves with the policy when the judge is the policy |
| 4 | Intrinsic self-assessment | P(confident) | "accept if confidence > τ" | converges to the most confident mode; degenerates when the wrong mode is the confident one |

If the filter is tier 1, the loop is a search procedure and the only risks are cost and formalization gaps. If it is tier 2, measure coverage and ask which modes fail off-coverage. If it is tier 3 or 4, the loop optimizes the judge, and Lesson 06 (the judge is the student) and Lesson 14 (Goodhart inside the loop) are the relevant failure analyses. Chen et al. make the stronger claim that the documented failure modes, self-confirming loops and model or diversity collapse, arise precisely from running a loop whose filter sits below the tier its claims require.

### Saturation and diversity

Two things stall even the oracle loop, and both are visible in the simulator.

*Exhausted problems.* The oracle run saturates at 89–90% and never passes it, because the general method is valid on 90% of puzzles and the remaining 10% never produce an accepted sample. ReST-EM reports the same pattern at PaLM 2 scale: gains saturate after a few iterations. STaR's rationalization (show the answer, ask for a rationale) is one way to create training signal on unsolved problems; self-generated curricula that target the frontier of solvability (Lesson 07) are the 2025–2026 answer.

*Entropy collapse.* The reweighting operator is multiplicative, so with a perfect filter the policy's entropy over strategies falls to zero: 1.00 bit → 0.03 bits in 8 iterations. That is fine here, because the losing strategy is wrong. But the same mechanism erases *correct* minority strategies that happen to be accepted slightly less often, and once a strategy's share is at the sampling floor, Poisson noise rules its fate. Sampling temperature is the standard brake. At generation temperature T the update becomes z' = z / T + log(a_B / a_A), which has a fixed point z* = T / (T − 1) · log(a_B / a_A) for T > 1. At T = 1.5 the shortcut settles near 16% rather than vanishing; the diversity floor costs about 8 points of accuracy in this toy, which is the price of keeping options open. Lesson 16 treats the full collapse story (Shumailov et al., Nature 2024) and the accumulate-rather-than-replace fix.

### The practical checklist

1. **Audit the filter's precision every iteration with a held-out truth set.** Sample 200 accepted items, label them against ground truth, report precision. In the simulator the audit reads 73.5% at the noisy filter's first iteration (true precision 77.5%) and 54.5% at the self-assessment filter's (true 51.1%). A 200-sample audit catches a 20-point contamination; it will not reliably see 2%.
2. **Compute the growth condition, not just the accuracy.** For each mode you care about, estimate a_s on the audit set. If any wrong mode has a_s above the right mode's, the next iteration amplifies it whatever the aggregate accuracy says.
3. **Mix fresh human data.** A fixed fraction of human-written solutions in each training set anchors the strategy mix. With 30% human data the self-assessment loop stops at a 48% shortcut share instead of 99%: an anchor, not a fix.
4. **Track diversity.** Entropy over strategies, distinct-solution counts or embedding spread per iteration. Collapse that outruns accuracy gains is the signature of a filter that is sharpening rather than selecting.
5. **Retrain from base, keep the problem set fixed, keep the truth set out of the loop.** ReST-EM's design choice and the audit set's independence are what make iteration-to-iteration comparisons meaningful.

```figure
self-refine
```

## Build It

The four steps below are the four parts of `code/main.py`. Run them in order in one file.

### Step 1: A task family with a latent trick

A puzzle asks for the sum of four numbers modulo 10. Sixty percent of puzzles carry a clause "add this shift first". The shortcut ignores the clause and is right exactly when there is none (40%). The general method applies the clause but misreads one clause in six, so it is valid on 1 − 0.6 / 6 = 90% of puzzles.

```python
import math
import random
from collections import Counter
from dataclasses import dataclass

TRICK_RATE, OBSCURE_RATE = 0.6, 1 / 6

@dataclass(frozen=True)
class Puzzle:
    numbers: tuple[int, ...]
    shift: int            # 0 = no clause; 1..9 = clause present
    obscure: bool         # the general method misreads this clause

    def answer(self) -> int:
        return (sum(self.numbers) + self.shift) % 10

def make_puzzle(rng: random.Random) -> Puzzle:
    numbers = tuple(rng.randint(1, 30) for _ in range(4))
    shift = rng.randint(1, 9) if rng.random() < TRICK_RATE else 0
    return Puzzle(numbers, shift, shift > 0 and rng.random() < OBSCURE_RATE)

rng = random.Random(0)
puzzles = [make_puzzle(rng) for _ in range(10_000)]
shortcut_right = sum(sum(p.numbers) % 10 == p.answer() for p in puzzles) / len(puzzles)
method_right = sum(not p.obscure for p in puzzles) / len(puzzles)
print(f"shortcut valid on {shortcut_right:.1%}, general method on {method_right:.1%}")
```

### Step 2: A softmax policy with a skill level

The policy holds a logit per strategy and samples at a temperature. It also holds a *skill* per strategy: the probability of executing it without a slip, where a slipped execution is a random digit. Skill is what SFT on clean examples improves and what SFT on wrong examples erodes. Confidence is a score that moves only slightly with correctness and is higher for the shortcut.

```python
CONF_BASE = {"A": 0.55, "B": 0.70}     # the shortcut skips the hard part, so it sounds sure

class Policy:
    def __init__(self, temperature: float = 1.0):
        self.logits = {"A": 0.0, "B": 0.0}
        self.skill = {"A": 0.8, "B": 0.8}
        self.temperature = temperature

    def probs(self) -> dict[str, float]:
        w = {s: math.exp(z / self.temperature) for s, z in self.logits.items()}
        total = sum(w.values())
        return {s: v / total for s, v in w.items()}

    def solve(self, puzzle: Puzzle, rng: random.Random, conf_signal: float = 0.03):
        s = "B" if rng.random() < self.probs()["B"] else "A"
        clean = rng.random() < self.skill[s]
        if not clean:
            answer = rng.randrange(10)
        elif s == "A":
            answer = (puzzle.answer() + rng.randint(1, 9)) % 10 if puzzle.obscure else puzzle.answer()
        else:
            answer = sum(puzzle.numbers) % 10
        correct = answer == puzzle.answer()
        confidence = CONF_BASE[s] + conf_signal * (1 if correct else -1) + rng.gauss(0, 0.12)
        return s, correct, clean, min(1.0, max(0.0, confidence))
```

### Step 3: Three filters and one train step

A filter maps an attempt to accept or reject. The train step refits the logits to the accepted strategy mix (add-one smoothing, so nothing is erased in one round) and moves each strategy's skill toward the clean fraction of its accepted samples, with twenty pseudo-samples of inertia.

```python
def accepts(kind, attempt, rng, fp_rate=0.3, fn_rate=0.1, fp_bias=0.0, tau=0.6) -> bool:
    s, correct, clean, confidence = attempt
    if kind == "oracle":
        return correct
    if kind == "noisy":
        if correct:
            return rng.random() < 1 - fn_rate
        return rng.random() < min(1.0, fp_rate + (fp_bias if s == "B" and clean else 0.0))
    return confidence > tau                      # self-assessment

def train(policy: Policy, accepted: list, prior_weight: int = 20) -> None:
    counts = Counter(a[0] for a in accepted)
    for s in ("A", "B"):
        policy.logits[s] = math.log((counts[s] + 1) / (len(accepted) + 2))
        if counts[s]:
            n_clean = sum(1 for a in accepted if a[0] == s and a[2])
            policy.skill[s] = (n_clean + prior_weight * policy.skill[s]) / (counts[s] + prior_weight)
```

### Step 4: Run, and measure what the loop cannot see

Per iteration, record the shortcut's share, the entropy, true accuracy on fresh puzzles and the share of accepted samples that are wrong. The last quantity is latent in a real pipeline, which is why the audit in the checklist exists.

```python
def entropy_bits(p: dict[str, float]) -> float:
    return -sum(v * math.log2(v) for v in p.values() if v > 0)

for kind in ("oracle", "noisy", "self"):
    rng, policy = random.Random(20), Policy()
    print(f"\n{kind:>6}  it  B share  entropy  accuracy  wrong-in-train")
    for it in range(1, 7):
        attempts = [policy.solve(make_puzzle(rng), rng) for _ in range(2000)]
        kept = [a for a in attempts if accepts(kind, a, rng)]
        wrong_share = sum(1 for a in kept if not a[1]) / len(kept)
        train(policy, kept)
        acc = sum(policy.solve(make_puzzle(rng), rng)[1] for _ in range(2000)) / 2000
        p = policy.probs()
        print(f"{'':>6}  {it:>2}  {p['B']:>7.1%}  {entropy_bits(p):>7.3f}  {acc:>8.1%}  {wrong_share:>14.1%}")
```

The oracle column should climb toward 90% while the shortcut vanishes; the self column should climb in nothing but the shortcut's share. `code/main.py` adds the analytic prediction per step, the audit estimate and the comparison.

## Use It

`code/main.py` runs the loop with the three filters side by side. For each filter it prints a per-iteration table: shortcut share, skill per strategy, entropy, held-out accuracy, accepted count, the true share of wrong samples in the training set, the 200-sample audit's precision estimate, and the predicted versus simulated change in log-odds with a sign check. It then prints the analytic conditions (q* = TPR, b*, κ* and the temperature fixed point), a comparison table, and a HEADLINE built from the numbers.

Flags: `--iterations` (default 8), `--filter oracle|noisy|self|all`, `--fp-rate` and `--fn-rate` for the noisy filter, `--fp-bias` for the extra leak on the shortcut's plausible wrong answers, `--tau` and `--conf-signal` for self-assessment, `--temperature`, `--human-mix`, `--samples`, `--seed`, and `--out` to dump the records as JSON.

In the default run, look at four things:

- The oracle reaches 88.8% and stops: the 10% of puzzles the method misreads never yield a kept sample.
- The noisy filter ends in nearly the same place (89.2%) but needs three more iterations to pass 85%, and trains on 10.4% wrong data on average, 22.5% at the first iteration.
- Self-assessment improves in every internal metric (accepted count 1,113 → 1,492) while held-out accuracy falls from 53.9% to 35.7%.
- The sign check reads 22/22 on testable steps. The two excluded steps are at the sample floor, where the shortcut has about two accepted samples and Poisson noise decides the sign.

## Ship It

This lesson produces `outputs/skill-filter-quality-audit.md`. Given a description of a self-training pipeline (what is generated, what filters it, what is trained, what ground truth exists), it places the filter on the verification hierarchy, specifies the per-iteration precision audit, computes the growth condition for the named failure modes, and returns a go / no-go with the thresholds that would stop the loop.

## Exercises

1. **(easy)** Run `python3 main.py --filter noisy --fp-rate 0.95`. The analytic block says the shortcut grows because q > TPR. Confirm the direction in the table, then explain why the per-step sign check is only 7/8 when the cumulative trend is unambiguous.
2. **(medium)** Run `python3 main.py --filter noisy --fp-bias 0.4`, then `--fp-bias 0.5`, then `--fp-bias 0.6 --seed 3`. Report the final shortcut share for each and compare with the printed threshold b* = 0.500. At exactly the threshold, what does the sign column look like, and why?
3. **(medium)** Run `python3 main.py --filter self --human-mix 0.3` and `python3 main.py --filter self --conf-signal 0.3`. One is an anchor, one is a fix. Which is which, by the numbers, and what in the derivation explains the difference?
4. **(medium)** Run `python3 main.py --filter oracle --temperature 1.5 --iterations 12`. Derive the fixed-point share from z* = T / (T − 1) · log(a_B / a_A) with c_A = 0.9 and c_B = 0.4, compare with iteration 12, and state what the diversity floor cost in accuracy.
5. **(hard)** Add a third strategy C that is valid on 100% of puzzles (it handles obscure clauses) but starts at a 2% share with skill 0.5. Under the oracle, does the loop find it at temperature 1.0? At 0.7? Then make the noisy filter's bias apply to C's wrong answers instead of B's and show that an informative filter can lose a correct strategy. Write the three-strategy growth condition.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Generate → filter → train | "self-training", "expert iteration" | Sample from the policy, keep what passes a check, fine-tune on the survivors; the industrial form of bounded self-improvement |
| STaR | "bootstrap reasoning" | Keep rationales whose answers match the label; rationalize failures with the answer as a hint (Zelikman et al., 2022) |
| ReST-EM | "Beyond Human Data" | Expert iteration with a binary reward, retraining the base model each round; saturates after a few iterations (Singh et al., TMLR 2024) |
| Rejection-sampling fine-tuning | "best-of-K SFT" | Sample K, keep the reward model's pick, SFT on it; a Llama 2 / Llama 3 post-training step |
| Acceptance rate a_s | "pass rate" | Probability that a sample from mode s passes the filter; the quantity the loop actually optimizes |
| Reweighting operator | "the loop is a fixed-point iteration" | π'(s) ∝ π(s) · a_s; its fixed points are the highest-acceptance modes |
| Growth condition | "does the shortcut win" | log-odds change log(a_B / a_A) > 0; for a symmetric filter q > TPR; for a biased one b > b* |
| Verification hierarchy | "formal > tests > judge > self" | Chen et al. (2026): demonstrated self-improvement strength follows the strength of the filter |
| Saturation | "gains stall" | Problems the policy never solves yield no accepted samples; the loop cannot learn them without rationalization or a curriculum |
| Precision audit | "spot-check the kept data" | Label a fixed-size sample of accepted items against held-out truth every iteration; the only view of contamination the loop cannot fake |

## Further Reading

- [Zelikman, Wu, Mu, Goodman — STaR: Bootstrapping Reasoning With Reasoning (arXiv:2203.14465)](https://arxiv.org/abs/2203.14465) — the original keep-if-correct loop and rationalization.
- [Singh et al. — Beyond Human Data: Scaling Self-Training for Problem-Solving with Language Models (arXiv:2312.06585)](https://arxiv.org/abs/2312.06585) — ReST-EM at PaLM 2 scale, with the saturation and overfitting findings.
- [Touvron et al. — Llama 2: Open Foundation and Fine-Tuned Chat Models (arXiv:2307.09288)](https://arxiv.org/abs/2307.09288) — rejection sampling as a production post-training step.
- [Dubey et al. — The Llama 3 Herd of Models (arXiv:2407.21783)](https://arxiv.org/abs/2407.21783) — rejection sampling with execution checks for code and math in the post-training recipe.
- [Chen, Wang, Qu — Recursive Self-Improvement in AI: From Bounded Self-Refinement to Autonomous Research Loops (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the 1,250-paper survey and the verification hierarchy.
- [Hosseini et al. — V-STaR: Training Verifiers for Self-Taught Reasoners (arXiv:2402.06457)](https://arxiv.org/abs/2402.06457) — what the rejected samples can still teach.
- [Shumailov et al. — AI models collapse when trained on recursively generated data (Nature, 2024)](https://www.nature.com/articles/s41586-024-07566-y) — the diversity side of the story, developed in Lesson 16.
