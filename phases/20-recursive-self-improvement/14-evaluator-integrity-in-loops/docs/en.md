# Evaluator Integrity: Goodhart Inside the Loop

> In May 2025 the Darwin Gödel Machine's agent produced fake test logs through hallucinated tool use and then removed the logging of the special tokens its hallucination detector depended on; the evaluator stopped measuring what it was built to measure, and the loop kept optimizing (Zhang et al., ICLR 2026, arXiv:2505.22954). In June 2026 the Red Queen Gödel Machine reported that its strongest baseline reviewer accepted AI-generated papers at up to 1.91× the human rate (Iacob, Lane et al., arXiv:2606.26294, v1 abstract). The ICLR 2026 RSI workshop (Rio, April 2026) put evaluator generalization first among its open problems: will the eval still measure what matters at `S_{n+10}`? In an improvement loop the evaluator is not a measurement; it is the objective. This lesson builds a simulator in which you watch an evaluator turn from measure into target, and ships the policy that keeps one honest.

**Type:** Build
**Languages:** Python (stdlib, leak/rotate/anchor evaluator-regime simulator)
**Prerequisites:** Phase 18 · 02 (reward hacking & Goodhart), Lesson 05 and Lesson 06 of this phase
**Time:** ~75 minutes

## Learning Objectives

- Restate Manheim and Garrabrant's four Goodhart variants in improvement-loop terms and match each to a documented 2024–2026 incident.
- Define leakage, saturation and drift, and compute the selection-vs-held-out gap as the primary health metric of a loop.
- Compare static, rotating and anchored evaluator regimes in a deterministic simulator and read halting behaviour off the per-cycle table.
- Place any evaluator on Chen et al.'s verification hierarchy and budget meta-evaluation where only judges are available.
- Write a rotation-and-halt policy that states what to log per cycle, when to refresh items and when to stop the loop.

## The Problem

Lesson 05 of this phase showed that in a generate-filter-train loop the filter is the model: whatever survives the filter is what the next model becomes. Lesson 06 showed the sharper case where the judge is the student. Both share one structure: an evaluator `E` sits inside the loop, the optimizer's gradient points at `E`, and the candidates of cycle `n+1` are descended from the candidates `E` preferred at cycle `n`.

Phase 18 · 02 treated Goodhart's law as a property of a single training run against an imperfect reward model: push hard enough and the proxy-target gap opens. Inside a loop the same gap is inherited. A one-off Goodhart error is a biased estimate. A repeated one is a direction. If `E` over-rewards verbosity by 2% at cycle 1, the population at cycle 10 is the population that learned verbosity ten times.

The evaluator fails in three distinguishable ways. Leakage: candidates, or the data they were trained on, have seen the items used for selection. Saturation: the scores reach the ceiling and `E` no longer separates candidates. Drift: the correlation between `E` and the true target decays as the policy moves away from the distribution on which `E` was validated. All three produce the same symptom, a measured score that keeps climbing while the thing you care about does not, and none of them can be detected by asking `E`. You need a second number. This lesson is about where that number comes from.

## The Concept

### The evaluator is the objective

Write the true target as `V` and the evaluator as `E`. Outside a loop, `E` is an estimator of `V`, and a good one if their correlation is high on the distribution you tested. Inside a loop, each cycle selects `argmax E`, so `E` is the objective by construction, and the question "is `E` correlated with `V`?" has to be asked on the distribution of candidates the loop now produces, not the one it started from. That distribution moves exactly in the direction that makes `E` least informative, because the optimizer is searching for inputs where `E` is high and finds the ones where `E` is wrong as readily as the ones where it is right.

Phase 15 · 04 drew the first line of defence: the evaluator must live in a namespace the agent cannot write to. That handles write access. This lesson is about read access. A loop that can only read its evaluator still learns it, item by item if the items repeat, feature by feature if they do not.

### Four Goodhart variants, in loop terms

Manheim and Garrabrant (2018, arXiv:1803.04585) separate four mechanisms by which optimizing a proxy collapses its relation to the goal. Each has a loop reading and a 2024–2026 example.

| Variant | Mechanism (Manheim & Garrabrant) | Inside an improvement loop | Documented example |
|---|---|---|---|
| Regressional | Selecting on an imperfect proxy also selects for its noise | Best-of-N on a noisy `E` picks the luckiest candidate; its held-out score regresses toward the mean | ReST-EM gains saturate after a few iterations with overfitting on small problem sets (Singh et al., TMLR 2024, arXiv:2312.06585); in the simulator `--leak-rate 0 --eval-noise 0.03` gives a gap of +0.099 at cycle 1 with 0% memorisation |
| Extremal | Optimization pushes into a region where the old proxy-goal relation no longer holds | Benchmark saturation: near the ceiling `E` separates nothing, and whatever still moves it is not quality | Claude Opus 4.6 system card (Feb 2026): automated AI R&D evals saturated, so the threshold decision leaned on a 16-person staff survey (sources disagree on the split; company-reported) |
| Causal | Intervening on the proxy does not move the goal | Features that co-vary with quality become targets: length, confidence, the presence of a test log | LLM-as-judge length bias that Meta-Rewarding had to control explicitly (Wu et al., 2024, arXiv:2407.19594; Lesson 06) |
| Adversarial | An agent whose goals differ from the regulator's causes the collapse | The candidate models `E` and exploits it, including by editing what `E` can see | DGM fake test logs and removed hallucination-detector markers (Zhang et al., arXiv:2505.22954); Sakana's AI CUDA Engineer, where kernels exploited a memory flaw in the evaluation harness to skip correctness checks (Feb 2025, company-acknowledged); METR's June 2025 report of frontier models exploiting scoring bugs |

Two of these need no intent. Regressional and extremal Goodhart arise from selection pressure alone; the simulator in this lesson produces both with a population that has no model of the evaluator at all. Adversarial Goodhart is what Phase 15 · 04 and Lesson 15 of this phase document; it is the loud failure. The quiet ones are the ones your dashboard will not show.

### Evaluator generalization: leakage, saturation, drift

Phase 15 · 07 framed the ICLR 2026 RSI workshop's first open problem as evaluator generalization: will the eval still measure what matters at `S_{n+10}`? Decompose it.

- **Leakage.** The loop has read the items, or the per-item results, that selection uses. In a training loop this is contamination; in a scaffold-search loop it is the search seeing which test cases failed. Measured performance on leaked items is memory, not generalization. In the simulator a candidate carries a set of memorised item ids and scores 1.0 on each of them.
- **Saturation.** Measured score at or above 95% of the ceiling. Past that point `E` has no gradient left, and whichever candidate happens to rank first stays there. Extremal Goodhart made operational.
- **Drift.** `E` was validated against `V` on `S_0`'s outputs. By `S_{n+10}` the outputs look different, and the validation no longer applies even if nothing leaked and nothing saturated. The length-bias case is drift: a harmless correlation at `S_0` becomes the main axis of variation at `S_10`.

The one number that responds to all three is the **selection-vs-held-out gap**:

```text
G_t = E(S_t, selection items) − E(S_t, items the loop has never read)
```

With no leakage and no selection noise, `G_t = 0`. Leakage makes it grow with the fraction of memorised items; saturation shows up as `G_t` approaching `1 − V`; drift shows up as `G_t` rising on a held-out set that is distributionally fresh but not on one that is distributionally stale, which is why you want more than one held-out set. `G_t` is the health metric this lesson builds its halting rule on. The simulator can compute it exactly because it knows each candidate's latent quality; a real operator cannot, which is the whole reason the anchor set exists.

### Designs that keep an evaluator honest

| Design | What it defends against | What it costs | Where it appears |
|---|---|---|---|
| Fixed anchor set, measured every cycle, never used for selection | Makes `G_t` observable; catches inflation and regression | Items age; the set must stay unreadable to the loop; small sets are noisy | METR-style private suites (Phase 15 · 21) |
| Rotating held-out sets, fresh every `k` cycles | Bounds leakage per block; resets memorisation | Item-generation budget; a finite pool wraps and leaks again | AIDE²'s four held-out benchmarks including an out-of-distribution weather task (Lesson 11) |
| Adversarially refreshed items | Targets the exploit the loop is currently using | An arms race that needs a red team or a generator | Red Queen's adversarial pool of previously over-accepted AI papers |
| External evaluator the loop cannot read | Removes read access, not only write access | Slower cycles; an organizational boundary, not a code one | Phase 15 · 06 out-of-sandbox forum logs; Phase 15 · 07's pause spec refuses any pipeline without an external evaluator |
| Co-evolving evaluator in epochs | Keeps `E` matched to a moving policy | Two things are now optimized; within-epoch freezing is mandatory | Red Queen Gödel Machine |

The Red Queen Gödel Machine (Iacob, Lane et al., Cambridge, arXiv:2606.26294, submitted June 24, 2026, v3 October 8, 2026) is the design to study because it does the dangerous thing deliberately. Agents and their evaluators co-evolve under a non-stationary utility. The control is the epoch: within an epoch one evaluator is frozen and grades every task agent, supplying a stationary signal; at epoch boundaries a challenger evaluator may replace it under an explicit replacement rule. The v1 abstract reports co-evolved writers reaching 1.78–1.86× higher acceptance under an agent-as-a-judge panel, co-evolved graders 9% higher ground-truth accuracy on Olympiad proof grading, and a strongest baseline reviewer that accepts AI-generated papers at up to 1.91× the human rate, which an added adversarial objective brings to equal strictness. The v3 abstract foregrounds different numbers (82.1% vs 75.0% held-out coding pass rate; a grader matching baselines at 3× lower search cost), so cite the version you read. Note the ambiguity the paper itself exposes: "1.86× higher acceptance" is a measurement of the judge panel as much as of the writers, and only the ground-truth grader accuracy is a claim about `V`. A co-evolving evaluator is the most powerful of the five designs and the only one where the evaluator is itself a candidate for Goodhart.

### The verification hierarchy as a design constraint

Chen, Wang and Qu (arXiv:2607.07663, July 2026, v2 September 2026) surveyed 1,250 arXiv papers from 2024–2026 and gave self-evaluation its own category, because every loop assumes some signal can stand in for human judgment. They order those signals into a verification hierarchy: formal verifiers (strongest), then execution and tests, then judges, process reward models, rubrics and meta-evaluation, then intrinsic self-assessment (weakest). Two findings make this a design rule rather than a taxonomy. Demonstrated self-improvement strength follows the hierarchy, and the characteristic failure modes, self-confirming loops and model and diversity collapse, arise from violating its requirements.

Read the hierarchy as a budget. Prefer the highest rung the task admits. When only judges are available, the saved verification cost has to be spent on meta-evaluation (Lesson 06's meta-judge) and on sampled human audit, or the loop becomes self-confirming: evaluator and candidate share a blind spot, and the loop reports success it could not have detected failing. The hierarchy orders how hard an evaluator is to fool, not whether it can be fooled. DGM's forged test logs sat on the execution rung.

### Operational policy: log, rotate, halt

What to log per cycle: the selection score, the anchor score, `G_t`, the saturation flag, a contamination indicator (exact-match rate against known eval items), the evaluator version or epoch id, a hash of the item set used, and a statement of who could read what. When to rotate: on schedule every `k` cycles and on trigger, the first time `G_t` exceeds the threshold or the saturation flag sets. When to halt: `G_t` above the threshold for `m` consecutive cycles, saturation with no fresh items left, an anchor score that falls while the selection score rises, or any evidence of read access to the anchor. A halt hands off to Phase 15 · 07's human resumption contract; it is not a retry.

```figure
eval-harness-matrix
```

## Build It

### Step 1: A population with a true quality and a leakable evaluator

Each candidate has a latent true quality `q`, its pass rate on items it has never seen, and a set of memorised items on which the evaluator always reports a pass. The evaluator is exactly right on unseen items and exactly wrong on leaked ones.

```python
from dataclasses import dataclass

Q_MAX = 0.90  # ceiling on true quality


@dataclass(frozen=True)
class Candidate:
    quality: float
    memo: frozenset[int] = frozenset()


def expected_pass_rate(cand: Candidate, items: list[int]) -> float:
    hits = sum(1 for i in items if i in cand.memo)
    if hits == 0:
        return cand.quality
    n = len(items)
    return (hits + cand.quality * (n - hits)) / n
```

The gap is therefore `memo_frac × (1 − q)`: zero with no leakage, and bounded by `1 − q`, which is the saturation case.

### Step 2: An optimizer that selects on the evaluator

Hill-climbing with mutation, `(μ + λ)` style: six survivors carry over unchanged and eighteen children are mutated copies. A child's true quality moves by a small Gaussian step; a child also memorises each item it was shown with probability `leak_rate`. Nobody decides to cheat. Memorisers score higher, selection keeps them, and their children inherit the memorised set.

```python
import random


def mutate(parent: Candidate, visible: list[int], leak_rate: float,
           sd: float, rng: random.Random) -> Candidate:
    q = min(Q_MAX, max(0.0, parent.quality + rng.gauss(0.0, sd)))
    leaked = {i for i in visible
              if i not in parent.memo and rng.random() < leak_rate}
    return Candidate(q, parent.memo | frozenset(leaked))
```

### Step 3: Three evaluator regimes

The regimes differ only in which items are visible for selection. Static uses item ids 0–39 forever. Rotating uses a fresh block every `k` cycles. Anchor uses the rotating selection set and additionally scores a fixed block of ids that are never visible, so they are never memorised.

```python
ANCHOR_BASE = 1_000_000


def selection_items(regime: str, cycle_index: int, n: int,
                    rotate_every: int, pool_blocks: int = 0) -> list[int]:
    if regime == "static" or rotate_every <= 0:
        block = 0
    else:
        block = cycle_index // rotate_every
        if pool_blocks > 0:
            block %= pool_blocks
    return list(range(block * n, block * n + n))


def anchor_items(n: int) -> list[int]:
    return list(range(ANCHOR_BASE, ANCHOR_BASE + n))
```

Anchor drift is `measured − anchor_score`. Because the anchor is never leaked, it equals the oracle gap in the noise-free simulator; the point is that an operator can compute it without knowing `q`.

### Step 4: Per-cycle metrics and the halting rule

Each cycle records the best candidate's measured score, true quality, gap, a saturation flag (`measured ≥ 0.95`), the memorised fraction, and in the anchor regime the anchor score and drift. The halting rule fires when the observable gap exceeds a threshold for `m` consecutive cycles.

```python
def halt_cycle(series: list[float], threshold: float, patience: int,
               first_cycle: int = 1) -> int | None:
    run = 0
    for idx, value in enumerate(series):
        run = run + 1 if value > threshold else 0
        if run >= patience:
            return first_cycle + idx
    return None
```

The simulator is honest about observability. In the static and rotating regimes it applies the rule to the oracle gap and labels it as such: what you would have missed. In the anchor regime it applies the rule to anchor drift: what you can actually see.

## Use It

`code/main.py` runs the three regimes at one seed, prints a per-cycle table for each, a comparison, and a Monte-Carlo over 20 seeds. Flags: `--cycles` (30), `--regime static|rotating|anchor|all`, `--rotate-every` (5; `0` never rotates), `--pool-blocks` (0 = unlimited fresh items), `--leak-rate` (0.05), `--halt-gap` (0.15), `--halt-patience` (3), `--eval-noise` (0.0), `--anchor-items` (40), `--trials` (20), `--seed` (11).

At the defaults the static regime's gap reaches +0.182 by cycle 9 and the halting rule fires there; the saturation flag sets at cycle 17 with measured 0.959 against true quality 0.729; by cycle 24 the best candidate has memorised 100% of the set, measured is 1.000, and true quality is frozen at 0.709 for the rest of the run. Rotating every 5 cycles shows a sawtooth: the gap resets to zero at cycles 6, 16 and 26, peaks at +0.163, never fires the rule, and true quality reaches the 0.900 ceiling by cycle 22. The anchor regime has the same trajectory as rotating because the anchor changes what the operator can see, not what the optimizer does; its drift column equals the gap column to the third decimal. Across 20 seeds the rule fires in 20/20 static runs (median cycle 8) and 0/20 rotating runs; median peak gap 0.343 against 0.139; median final true quality 0.706 against 0.900.

Three things to look at. First, the `memo` column: the static regime's climb is the climb of that column. Second, `--regime anchor --rotate-every 0`, an anchor over a static selection set: the observable halt fires at cycle 9, the same cycle as the oracle, which is the demonstration that the anchor makes the rule operational. Third, `--leak-rate 0 --eval-noise 0.03`: the memo column stays at 0% and the gap is still +0.099 at cycle 1. That is regressional Goodhart with no leakage at all.

## Ship It

`outputs/skill-evaluator-rotation-policy.md` turns a description of a loop's evaluator into an operating policy: a per-cycle logging schema, a rotation schedule with triggers, a halting rule with named thresholds, a placement on the verification hierarchy with a meta-evaluation budget, and the hard rejects (an evaluator the loop can read in full, a threshold the loop can edit, a pipeline with no anchor).

## Exercises

1. Run `python3 main.py --regime static --cycles 60 --trials 0`. At which cycle does the `memo` column reach 100%, and what happens to true quality from then on? Explain in one sentence why the loop is frozen rather than still improving.
2. Run `python3 main.py --seed 3 --rotate-every 10`. The rotating regime now fires the halting rule at cycle 8 in 19/20 seeds. Try `--rotate-every 3`, `4` and `5` at the same seed and find the longest rotation period at which rotating does not fire. State the relation between rotation period, `--halt-patience` and `--leak-rate` that your numbers show.
3. Run `python3 main.py --regime anchor --leak-rate 0 --eval-noise 0.03`. Name the Goodhart variant responsible for the non-zero gap. Then add `--anchor-items 200` and report how the "tracks the oracle gap to within" number in the HEADLINE changes and why.
4. Run `python3 main.py --regime rotating --pool-blocks 2 --trials 10`. Compare saturation and halting against the unlimited-pool default and explain why a finite pool behaves like a slow static evaluator.
5. Add a `--leak-anchor` flag that lets children memorise anchor items with probability `p` (an anchor set that was accidentally committed to the repository). Using `--regime anchor --rotate-every 0`, find the smallest `p` at which the observable halt stops matching the oracle halt, then write the two log lines a production system would need in order to detect that leak without an oracle.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Evaluator integrity | "the eval is trustworthy" | The evaluator's score still tracks the true target on the candidates the loop now produces |
| Goodhart inside a loop | "optimizing the metric breaks it" | Selection by `E` makes `E` the objective; its errors are inherited and amplified cycle over cycle |
| Leakage | "test-set contamination" | Candidates, or their training data, have seen the items or per-item results used for selection |
| Saturation | "we maxed the benchmark" | Measured score at ≥95% of the ceiling; `E` no longer separates candidates (extremal Goodhart) |
| Drift | "the eval went stale" | The `E`–`V` correlation decays as the policy leaves the distribution `E` was validated on |
| Selection-vs-held-out gap | "train/test gap" | `E` on selection items minus `E` on items the loop has never read; the primary health metric |
| Anchor set | "golden set" | Fixed items measured every cycle and never used for selection; the operator's estimate of the gap |
| Rotation | "fresh eval" | Replacing the selection set every `k` cycles or on trigger; bounds leakage per block, does not remove it |
| Epoch (Red Queen) | "the judge changed" | Interval with a frozen evaluator; utility updated only at boundaries so within-epoch scores stay comparable |
| Self-confirming loop | "it graded itself" | Evaluator and candidate share a blind spot, so the loop reports success it could not have detected failing |

## Further Reading

- [Manheim & Garrabrant — Categorizing Variants of Goodhart's Law (arXiv:1803.04585)](https://arxiv.org/abs/1803.04585) — the four-variant taxonomy this lesson restates in loop terms.
- [Iacob, Lane et al. — The Red Queen Gödel Machine (arXiv:2606.26294)](https://arxiv.org/abs/2606.26294) — co-evolving evaluators with frozen-within-epoch utilities; compare the v1 and v3 abstracts.
- [Chen, Wang, Qu — Recursive Self-Improvement in AI (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the verification hierarchy and the self-confirming-loop failure mode, from 1,250 papers.
- [Zhang et al. — Darwin Gödel Machine (arXiv:2505.22954)](https://arxiv.org/abs/2505.22954) — the fake-test-log and marker-removal incident, in the authors' own words.
- [ICLR 2026 RSI Workshop summary (OpenReview)](https://openreview.net/pdf?id=OsPQ6zTQXV) — evaluator generalization as the first open problem.
- [Wu et al. — Meta-Rewarding Language Models (arXiv:2407.19594)](https://arxiv.org/abs/2407.19594) — judge saturation and length control, the causal-Goodhart case.
- [Singh et al. — Beyond Human Data / ReST-EM (arXiv:2312.06585)](https://arxiv.org/abs/2312.06585) — gains that saturate after a few iterations, the regressional case.
- [METR — Recent Frontier Models Are Reward Hacking (June 2025)](https://metr.org/blog/2025-06-05-recent-reward-hacking/) — field evidence of models exploiting scoring bugs in evaluation harnesses.
