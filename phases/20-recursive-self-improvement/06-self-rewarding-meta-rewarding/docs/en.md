# Self-Rewarding and Meta-Rewarding: When the Judge Is the Student

> In January 2024 Yuan et al. (Meta) trained Llama 2 70B for three rounds in which the same model wrote the answers, graded them and ran DPO on its own grades: the AlpacaEval 2.0 win rate climbed 9.94% → 15.38% → 20.44%, passing GPT-4 0613 (15.76%), while the average response grew from 1,092 to 2,552 characters (all paper-reported). In July 2024 Wu et al. added a meta-judge that grades the judge and reported Llama-3-8B-Instruct going from 22.9% to 39.4% length-controlled win rate on AlpacaEval 2, while also reporting that the judge "tended to assign higher scores, which accelerated score saturation and reduced its ability to discriminate". This lesson is about the second half of each sentence. A self-rewarding loop is Goodhart's law with the proxy and the optimizer in the same weights, and only something outside the loop can stop the drift.

**Type:** Learn
**Languages:** Python (stdlib, actor/judge co-training simulator)
**Prerequisites:** Phase 10 · 08 (DPO), Phase 18 · 02 (reward hacking & Goodhart), Lesson 05 of this phase
**Time:** ~60 minutes

## Learning Objectives

- Describe the Self-Rewarding loop (actor, LLM-as-a-Judge rubric, best-vs-worst pairs, iterative DPO) and quote its paper-reported gains and side effects.
- Explain why a judge that is not deliberately trained saturates, and why the actor then optimizes the judge's biases rather than quality.
- Describe the Meta-Rewarding additions (meta-judge, joint judge/actor training, length-control rule) and separate what they fixed from what they did not.
- Argue where the recursion "who evaluates the evaluator" must stop and what has to be grounded.
- Instrument a self-rewarding pipeline with four per-iteration drift signals and interpret them on the simulator.

## The Problem

Lesson 05 of this phase ended with a filter that is a program: a unit test, a math checker, a majority vote. STaR and ReST-EM keep a sample only when a verifier says it is right. Move to open-ended tasks — chat, writing, advice, code review without tests — and there is no verifier. Industry's substitute is a reward model trained on human preference pairs, and the Self-Rewarding paper names its two defects in its first paragraph: it is bottlenecked by human performance, and it is frozen while the policy keeps improving against it. Phase 18 · 02 showed what a frozen proxy does under optimization pressure (Gao et al. 2023: proxy reward rises, gold reward peaks and falls).

The self-rewarding proposal removes both defects at once: let the policy be its own reward model. A model that gets better at answering should also get better at judging, so the judge never freezes and never caps at human level. That is the attractive half. The other half is structural: the judge now *is* the student. Whatever the judge rewards for reasons unrelated to quality — length, confident tone, bullet lists, rubric-shaped phrasing — the student will learn, and the student-as-judge will then reward it a little more. Nothing inside the loop can notice, because the loop's only instrument is the thing that is drifting.

## The Concept

### The Self-Rewarding loop (Yuan et al., ICML 2024)

Self-Rewarding Language Models (Yuan et al., ICML 2024, arXiv:2401.10020) starts from Llama 2 70B fine-tuned on a small seed of instruction-following data (IFT) and a small seed of *evaluation* data (EFT: prompts, responses, human-written judgements). Each iteration then:

1. **Generates prompts** by few-shot prompting from the seed set.
2. **Acts**: samples N = 4 candidate responses per prompt.
3. **Judges**: prompts the same model with an additive 0–5 rubric (one point each for relevance, coverage, usefulness, clarity, expertise), averaging three judge samples per response.
4. **Trains**: takes the highest- and lowest-scored responses as a preference pair (equal scores are discarded) and runs DPO (Phase 10 · 08). The result M_{t+1} both acts and judges in the next iteration.

The paper-reported trajectory (Table 1 of the paper; AlpacaEval 2.0 win rate against GPT-4 Turbo, judged by GPT-4):

| Model | AlpacaEval 2.0 win rate | Pairs used to train it | Mean response length (chars) |
|---|---|---|---|
| M1 (SFT on IFT + EFT) | 9.94% | — | 1,092 |
| M2 | 15.38% | 3,964 | 1,552 |
| M3 | 20.44% | 6,942 | 2,552 |
| GPT-4 0613 (reference) | 15.76% | — | — |
| Claude 2 / Gemini Pro (reference) | 17.19% / 16.85% | — | — |

Two more facts matter. The judge did improve: pairwise agreement with human rankings rose from 65.1% (SFT) to 78.7% (M1), 80.4% (M2) and 81.7% (M3). And the paper flags the length column itself: the model "is learning to generate longer responses", which "may be a factor in relative performance", and it lists reward hacking inside the framework as an open question.

### Why the judge saturates and the actor learns the judge

Look at what trains the judge. The EFT seed is fixed; after M1 the judge changes only because DPO on *actor* pairs happens to move the shared weights. Judging improves incidentally, 78.7% → 81.7%, while the actor's win rate doubles. No outside signal ever tells the judge which of its preferences were wrong. In the verification hierarchy of Chen et al. (arXiv:2607.07663, 2026) — formal verifiers strongest, intrinsic self-assessment weakest — a judge that shares weights with the actor slides toward the bottom rung with every iteration.

Now think about the pairs. Early on, candidates differ a lot in quality, and a judge that is 80% right produces pairs whose chosen side is mostly better. As the actor improves, the four candidates cluster near the top of the rubric, more pairs tie and are discarded, and the surviving score differences are increasingly explained by whatever the judge responds to that is *not* quality. If the judge gives half a point for thoroughness-that-looks-like-length, the pairs now say "longer wins", DPO raises the log-probability of longer, and next iteration the same weights are slightly more convinced that long is good. This is Goodhart's law (Phase 18 · 02) with one twist: in ordinary RLHF the proxy is frozen, so the proxy–gold gap is at least a stationary target; here the proxy co-moves with the policy, so the gap grows without any visible drop in the proxy. Chen et al. call these "self-confirming loops" and list them, beside model collapse (Lesson 16 of this phase), as the characteristic failure of loops that violate their verification requirements.

A one-line model makes the drift quantitative. Let a response have latent quality q and length L, and let the judge score it as s = q + β·L/1000 + ε. A preference is decided by Δs = Δq + β·ΔL/1000 + noise. With β = 0.5 and lengths of 200 versus 1,000 characters, the length term is worth 0.4 quality points — more than the whole spread between a sloppy and an excellent answer in `code/main.py`. The actor need not be adversarial; gradient ascent on Δs finds the length term because it is the biggest term.

### Meta-Rewarding (Wu et al., 2024): grade the grader, cap the length

Meta-Rewarding Language Models (Wu et al., arXiv:2407.19594, July 2024) names the problem — self-rewarding "can quickly saturate — or worse could overfit the reward signal" — and adds three things:

- **A meta-judge.** For each prompt, take the response whose 11 judge samples disagree most. Compare pairs of those judgements with a pairwise meta-judge prompt in both orders (to cancel positional bias), fit Elo scores to the win matrix, and make the highest-Elo judgement chosen and the lowest rejected. The judge is now trained on *judgement* pairs, not only moved incidentally.
- **Joint training.** Iterations 1–2 train on actor pairs and judge pairs; iterations 3–4 on actor pairs only.
- **A length-control rule.** With S_max and S_min the best and worst scores among a prompt's candidates, the chosen response is the *shortest* one with score in [(1−ρ)·S_max + ρ·S_min, S_max], the rejected one the *longest* with score in [S_min, (1−ρ)·S_min + ρ·S_max]. ρ = 0 switches the rule off; the paper used ρ = 0, 0.32, 0.32 and 0.4 across iterations 1–4.

Paper-reported results on Llama-3-8B-Instruct — length-controlled (LC) AlpacaEval 2 win rate (Table 1 of the paper) and Arena-Hard (Table 2):

| Iteration | Self-Rewarding + length control | Meta-Rewarding | Meta-Rewarding, Arena-Hard |
|---|---|---|---|
| Seed (Llama-3-8B-Instruct) | 22.92% | 22.92% | 20.6% |
| 1 | 26.93% | 27.85% | 25.1% |
| 2 | 30.38% | 32.66% | 27.4% |
| 3 | 34.87% | 35.45% | 27.6% |
| 4 | 35.49% | 39.44% | 29.1% |

Read the middle column carefully: Self-Rewarding *with* length control reaches 35.49%; the extra four points of Meta-Rewarding come from training the judge, and the paper says the baseline "lags behind in later iterations due to its lack of judge training". Judge agreement with GPT-4 on the model's own chosen pairs rose from 61.03% (seed) to 79.33% (iteration 4).

Now the other half. Agreement with *human* judgements on Open Assistant did not follow: Spearman went 0.315 (seed) → 0.210 → 0.382 → 0.329 → 0.326, a gain the paper says "is not sustained over later training iterations". The mean judge score climbed from about 4.1 to above 4.7 within two iterations (Figure 5), so the judge "tended to assign higher scores, which accelerated score saturation and reduced its ability to discriminate between responses". The meta-judge grew its own bias: the share of meta-judgements that simply preferred the higher-scoring judgement went from 63.04% in iteration 1 to 97.68% in iteration 2 (Table 5). And the length-control rule is not learned at all; a human wrote it because the human already knew what the drift would be. Meta-Rewarding is an honest paper: it shows that a layer of self-evaluation buys a few iterations, and it documents the new layer saturating.

### Who evaluates the evaluator, and where the recursion has to stop

The obvious next move is a meta-meta-judge, and the obvious objection is that it is the same model again. Stacking evaluators made of the same weights does not average out their errors; it correlates them. A length bias in the judge becomes a preference for long judgements in the meta-judge — which is why Wu et al. also had to drop chosen judgements longer than 1,100 characters (iteration 1) or 1,000 (iteration 2). Each layer up is another instance of the thing you were trying to check.

So something must be grounded. Chen et al.'s hierarchy is the checklist: formal verifiers where you can have them (Lean, as in AlphaProof — Lesson 04 of this phase), execution and tests where you can (Lesson 05), and where you only have judges, a fixed set of human labels the loop never trains on. This is the recurring question of this phase. Lesson 14 (evaluator integrity) builds the audit harness. Lesson 10 covers the Red Queen Gödel Machine (Iacob et al., arXiv:2606.26294, June 2026), which co-evolves graders with agents and reports co-evolved writers reaching 1.78×–1.86× the baseline acceptance rate under an agent-as-a-judge panel — *and* needs an explicit adversarial objective to keep graders equally strict on AI- and human-written work, because an unanchored co-evolving grader drifts toward self-preference exactly as the judge here drifts toward length. Phase 18 · 11 (scalable oversight) and Phase 15 · 04 (DGM's fake-test-log episode) are the same question in other clothes; Phase 15 · 07 called it "evaluator generalization".

The design rule that falls out: a meta-judge is useful only if it has information the judge does not. In Wu et al. that information is weak (a different prompt, pairwise comparison, Elo). In the simulator below it is strong (a small human-labelled audit set), deliberately: the lesson's claim is that the audit set, not the extra layer, does the work.

### What to log every iteration

Four numbers, all cheap, all of which the two papers either report or wish they had:

| Signal | How to compute it | What it caught in the papers | Red flag |
|---|---|---|---|
| Judge–human agreement on a fixed audit set | Pairwise agreement (or Spearman) between judge and human labels on 100–500 items the loop never trains on, re-scored by the current judge every iteration | Wu et al. Table 7: human Spearman 0.315 → 0.326 after four iterations, gain "not sustained" | Flat or falling while the win rate rises |
| Length drift | Mean and 90th-percentile response length of the current actor's samples | Yuan et al.: 1,092 → 2,552 characters in three iterations | More than 20% growth in one iteration without a task change |
| Score inflation | Mean judge score of the actor's samples, and on the audited subsample the gap between judge score and human score | Wu et al. Figure 5: mean score 4.1 → 4.7+ in two iterations; "reduced its ability to discriminate" | Mean score approaching the top of the scale; judge-minus-human gap widening |
| Preference-pair entropy | Entropy of which style / cluster / length bucket wins the pairs; also the share of ties discarded | Yuan et al. discard equal-score pairs; Wu et al. needed the highest-variance response to find usable judgement pairs | Entropy collapsing toward 0 bits while agreement on the actor's own pairs stays high |

The last column is where practitioners go wrong: agreement measured on the loop's *own* pairs is not a monitor, because once the actor converges to one style the pairs are same-style and the metric measures noise. The audit set has to be fixed and external. Phase 18 · 02's verbosity bias, Lesson 14's harness and this table are one idea at three scales.

```figure
reward-model
```

## Use It

`code/main.py` is a stdlib actor/judge co-training simulator. The actor is a probability distribution over six response styles (`concise`, `standard`, `thorough`, `padded`, `verbose`, `sloppy`), each with a latent true-quality mean and a typical length; the best style is the short one, so length and quality are deliberately anti-correlated at the top. The judge scores a response as true quality plus `length_bias × length/1000` plus noise. Each iteration samples 200 pairs, the judge picks winners, and a DPO-like multiplicative update raises the log-probability of winning styles. Regime `frozen` never changes the judge (Self-Rewarding); regime `meta` lets a grounded meta-judge regress the judge's error against length on a fixed human-labelled audit set and remove half of the estimated bias each iteration.

```bash
python3 main.py                                   # both regimes, bias 0.5, audit set 40, seed 7
python3 main.py --length-bias 0                   # unbiased judge: both regimes converge to "concise"
python3 main.py --length-bias 0.8 --regime frozen # strong bias: true quality falls as length doubles
python3 main.py --audit-size 6                    # a tiny audit set makes the meta-judge noisy
python3 main.py --meta-lr 0.2 --seed 3            # slower judge repair: the actor drifts first, then recovers
```

Columns to watch: `true_q` (exact expected quality of the style mix), `length`, `judge` (mean judge score of the samples), `inflat` (judge mean minus true mean of the same samples), `agr_tr` (judge agrees with truth on its own training pairs), `agr_au` (judge agrees with human labels on the fixed audit set) and `win_H` (entropy of which style wins). In the default run the frozen judge takes true quality from 0.627 to 0.542 while mean length doubles from 502 to 990 characters and the judge's own mean score *rises* by 0.155; the meta-rewarded judge has its bias under 0.10 by iteration 3 and ends at 0.771. `HEADLINE` is generated from those numbers; `--out stats.json` dumps every row.

## Ship It

This lesson produces `outputs/skill-judge-drift-monitor.md`. Given a description of a self-rewarding or LLM-as-a-judge training loop, it specifies the fixed audit set, the four per-iteration signals, their red-flag thresholds, the stop rule, and the hard rejects (no external audit set, agreement measured only on the loop's own pairs, a meta-judge with no information the judge lacks).

## Exercises

1. **(easy)** Run `python3 main.py --length-bias 0` and `python3 main.py --length-bias 0.8`. For each regime record final `true_q`, `length` and `inflat`. In one sentence each, say what the unbiased run proves about the update rule and what the 0.8 run proves about the frozen judge.
2. **(medium)** Run `python3 main.py --length-bias 0.3`. The frozen judge *raises* true quality here (to about 0.725) — to which style does it converge, and why is that still a Goodhart failure? Use the style table and the judge-score formula to show which style wins at β = 0.3 and at β = 0.
3. **(medium)** Run `python3 main.py --audit-size 6` and `python3 main.py --audit-size 200`. Compare the meta regime's `bias` and `agr_au` columns. Explain why the small audit set overshoots to −0.14 and why its agreement jumps between 33.3% and 100.0%. What minimum audit size would you require in production, and why?
4. **(medium)** In the default frozen run `agr_tr` starts near 50% and rises to 64.5% by iteration 12 while true quality falls. Explain the mechanism (what kind of pairs the judge sees by then), then argue why Wu et al.'s Table 3 — agreement with GPT-4 on the model's *own* chosen pairs rising to 79.33% — is weaker evidence than it looks.
5. **(hard)** Implement Wu et al.'s length-control rule: sample N = 4 candidates per prompt, choose the *shortest* response with score in [(1−ρ)S_max + ρS_min, S_max] and reject the *longest* with score in [S_min, (1−ρ)S_min + ρS_max]. Run a frozen judge at β = 0.5 for ρ ∈ {0, 0.3, 0.5}. Does a hand-written rule with no audit set match the meta regime on true quality? Report the ρ at which it stops helping, and say what information the rule encodes that the judge lacks.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Self-Rewarding LM | "The model rewards itself" | One set of weights acts, judges with an LLM-as-a-Judge rubric, and is DPO-trained on the pairs it judged (Yuan et al. 2024) |
| LLM-as-a-Judge | "Ask the model to grade it" | A prompted model that emits a score or a pairwise verdict; a learned proxy with its own biases (length, position, style) |
| Iterative DPO | "DPO in a loop" | Re-collect preference pairs from the current policy each iteration and run DPO again; where the pairs come from is what separates self-rewarding from RLHF |
| Judge saturation | "Scores all end up 4.7" | Candidates cluster at the top of the rubric so score differences stop tracking quality; Wu et al. report mean score 4.1 → 4.7+ |
| Self-confirming loop | "It thinks it is getting better" | Chen et al. 2026: a loop whose evaluation signal co-moves with the policy, so proxy gains persist while gold quality stalls or falls |
| Meta-judge | "A judge of judges" | A model that compares judgements and produces preference pairs for training the judge (Wu et al. 2024); useful only if it has information the judge lacks |
| Length control (ρ) | "Penalize long answers" | Choose the shortest high-scoring and reject the longest low-scoring candidate within score bands set by ρ; a hand-written anchor, not a learned one |
| Score inflation | "The judge got generous" | Rising mean judge score on the policy's samples that is not matched by rising human or gold score |
| Fixed audit set | "Held-out set" | Human-labelled items the loop never trains on and the current judge re-scores every iteration; the only grounded signal in a self-rewarding loop |
| Preference-pair entropy | "Diversity of the data" | Entropy of which style/cluster wins the pairs; collapse toward 0 bits means the pairs no longer carry information about quality |

## Further Reading

- [Yuan et al. — Self-Rewarding Language Models (ICML 2024, arXiv:2401.10020)](https://arxiv.org/abs/2401.10020) — the primary loop; read Table 1, Table 4 and the length paragraph of Section 3.2.1 together.
- [Wu et al. — Meta-Rewarding Language Models (arXiv:2407.19594)](https://arxiv.org/abs/2407.19594) — the fix and its own saturation; Section 5 and Table 7 are the honest part.
- [Chen, Wang, Qu — Recursive Self-Improvement in AI (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the verification hierarchy and "self-confirming loops" as a named failure mode.
- [Iacob et al. — The Red Queen Gödel Machine (arXiv:2606.26294)](https://arxiv.org/abs/2606.26294) — co-evolving evaluators with an explicit anti-self-preference objective.
- [Gao, Schulman, Hilton — Scaling Laws for Reward Model Overoptimization (arXiv:2210.10760)](https://arxiv.org/abs/2210.10760) — the proxy-vs-gold curves this lesson puts inside a loop.
- [Dubois et al. — Length-Controlled AlpacaEval (arXiv:2404.04475)](https://arxiv.org/abs/2404.04475) — why raw AlpacaEval rewards length and why Meta-Rewarding reports LC win rates.
- [Zheng et al. — Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (arXiv:2306.05685)](https://arxiv.org/abs/2306.05685) — position, verbosity and self-enhancement biases of LLM judges, measured.
