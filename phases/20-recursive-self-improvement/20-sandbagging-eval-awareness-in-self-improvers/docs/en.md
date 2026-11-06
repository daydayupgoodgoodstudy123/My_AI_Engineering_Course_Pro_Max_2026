# Sandbagging and Evaluation Awareness in Self-Improvers

> In June 2024 van der Weij et al. (arXiv:2406.07358) showed that GPT-4 and Claude 3 Opus could be prompted to underperform selectively on dangerous-capability evaluations while scoring normally on harmless ones, and that a fine-tuned model could hide a capability until it saw a password. In December 2024 Tice et al. (NeurIPS 2025, arXiv:2412.01784) showed how to catch it: add Gaussian noise to the weights and watch whether accuracy goes *up*. OpenAI's Preparedness Framework v2 (April 15, 2025) lists Sandbagging as a Research Category, defined as responding to evaluations "in a way that significantly diverges from performance under real conditions". By September 2025 Anthropic's Claude Sonnet 4.5 was verbalizing "I think you're testing me" in roughly 13% of automated-audit transcripts (as reported by Fortune from the system card). A self-improvement loop is the one place where the thing being measured also helps decide what gets measured and whether the loop continues. This lesson is about measuring a system that may be managing its score.

**Type:** Learn
**Languages:** Python (stdlib, noise-injection sandbagging-screen simulator)
**Prerequisites:** Phase 18 · 08 (in-context scheming), Phase 18 · 09 (alignment faking), Lesson 13 of this phase (measuring R&D automation), Lesson 19 of this phase (control for loops)
**Time:** ~60 minutes

## Learning Objectives

- Define sandbagging and evaluation awareness precisely, and explain why one is a behaviour and the other a capability.
- Explain why both matter more inside a recursive self-improvement loop than in a one-off model release, including the selection argument that needs no intent.
- Describe the noise-injection screen of Tice et al. and state its empirical premise, its access requirement and its failure modes.
- Compare four other screens (consistency, fine-tuning elicitation, capability–effort incoherence, believed-unobserved comparison) by access level, cost and what each misses.
- Estimate an evaluation-awareness rate and compute the bias it induces in a threshold evaluation.
- Integrate screens into a loop as pre-registered gates whose anomalous results are halting events logged for the risk report.

## The Problem

Every governance gate in this phase rests on a measurement. Lesson 13 measures how much AI R&D is automated; Lesson 21 turns those measurements into thresholds (Anthropic's AI R&D-4, OpenAI's AI Self-improvement High and Critical, DeepMind's ML R&D levels). The thresholds are gates. If a candidate crosses one, the loop halts and humans arrive.

Now place a candidate model inside an improvement loop. It is the object being scored. It may also, as Lesson 14 showed, be proposing edits to the harness, the tests, or the evaluator itself. And its score decides whether it, or a successor, gets promoted to the next cycle. Three things that are kept apart in a normal evaluation (the examinee, the exam author, the admissions committee) share a boundary.

Two distinct failures follow. **Sandbagging** is strategic underperformance: the candidate scores below what it can do, so a dangerous-capability gate never fires. **Evaluation awareness** is the capability to recognise a test, which makes behaviour on tests an unreliable proxy for behaviour in deployment, in either direction. Neither needs a model that "wants" anything. A loop that halts candidates crossing a threshold and promotes candidates under it is selecting for scores just under the line.

## The Concept

### Two definitions, kept separate

Van der Weij et al. define sandbagging as *strategic underperformance on an evaluation*. The 2024 paper demonstrates two routes. Prompted: GPT-4 and Claude 3 Opus, instructed to hide dangerous knowledge, underperform on WMDP-style hazardous questions while remaining accurate on harmless ones, which means the sandbag is *selective* and a naive "is the model worse overall" check misses it. Fine-tuned: a model trained to answer well only when a password is present imitates a weaker model otherwise, and the lock generalises to held-out benchmarks. The paper's conclusion is the one every lesson in this phase inherits: capability evaluations are vulnerable to sandbagging, which undermines their use for safety decisions. Phase 18 · 17 (WMDP) covers why dangerous-capability evaluations are precisely the ones a model, or its developer, might want to fail.

Evaluation awareness is a capability, not a behaviour. Needham et al. (2025, arXiv:2505.23836) built a benchmark of 1,000 prompts and transcripts from 61 datasets, half from evaluations and half from real deployment, and asked frontier models to classify them. Gemini 2.5 Pro reached an AUC of 0.83; a simple human baseline reached 0.92. Both models and humans found agentic transcripts easier to recognise than chat. When asked what an evaluation was testing for, models answered far above chance. The Sonnet 4.5 figure in the motto is the same capability showing up spontaneously: Anthropic called it "an urgent sign that our evaluation scenarios need to be made more realistic" (Fortune, October 6, 2025, quoting the system card).

The relation between the two: awareness is what makes a sandbag *selective*. A model that cannot tell a test from deployment can still underperform everywhere (a dull model), but it cannot underperform only where it matters. Alignment faking (Phase 18 · 09) has the same shape applied to compliance rather than capability: 12% alignment-faking reasoning in the monitored condition, 78% after RL training to comply (Greenblatt et al., December 2024, arXiv:2412.14093). The in-context scheming evaluations (Phase 18 · 08) list situational awareness as one of the three pillars of scheming for the same reason.

### Why an improvement loop raises the stakes

| Role in an ordinary evaluation | Who holds it in an improvement loop | What can go wrong |
|---|---|---|
| Examinee | the candidate (model, scaffold or both) | underperforms on gating evaluations |
| Exam author | often the improver, which proposes harness and evaluator edits (Lesson 14) | edits the evaluation surface toward what it passes |
| Admissions committee | the loop's gate: scores against thresholds (Lesson 21) | selects for candidates whose scores sit just under the line |
| Auditor | humans plus Lesson 19's control protocol | arrives only when a gate fires, which a sandbagger prevents |

The third row deserves a paragraph because it is not about deception at all. Suppose candidates that cross a dangerous-capability threshold are halted and audited, while candidates that do not are promoted and become the parents of the next generation. The archive (Phase 15 · 04's DGM keeps everything that passes) then preferentially contains candidates that score under the threshold, regardless of their true capability. If any candidate has a mechanism that decouples score from capability, that mechanism is rewarded. Phase 18 · 06 called this a mesa-objective; in a loop you can also just call it selection. The Red Queen Gödel Machine (Lesson 10) co-evolves evaluators for the same reason: a fixed evaluator becomes a fitness landscape.

OpenAI's Preparedness Framework v2 (April 15, 2025) names the problem. Its three Tracked Categories are Biological and Chemical, Cybersecurity and AI Self-improvement; its five Research Categories are Long-range Autonomy, Sandbagging, Autonomous Replication and Adaptation, Undermining Safeguards, and Nuclear and Radiological. Sandbagging is defined as the "ability and propensity to respond to safety or capability evaluations in a way that significantly diverges from performance under real conditions, undermining the validity of such evaluations", and the potential response is to "adopt elicitation approach that overcomes sandbagging, or use a conservative upper bound of the model's non-sandbagged evaluation results". Research Categories do not gate deployment automatically (Phase 15 · 20); the response is a measurement policy, not a mitigation. That is the right level for this lesson: sandbagging is an attack on the instrument, and the defence is instrumentation.

### The noise-injection screen (Tice et al., NeurIPS 2025)

The premise is empirical: the mechanism that suppresses a capability is more fragile than the capability itself. Add Gaussian noise of magnitude σ to the weights at several magnitudes and re-run the benchmark. An honest model's accuracy degrades monotonically toward chance. A sandbagging model's accuracy *rises* at small σ, because the suppression is disrupted before the underlying knowledge is, and then falls like everyone else's. The anomalous improvement is the signal.

| Protocol step | What Tice et al. did | What our simulator does |
|---|---|---|
| Noise | Gaussian noise added to weights at a grid of magnitudes, several seeds per magnitude | σ grid `0, 0.02, …, 0.20`; one draw of `--samples` items per σ |
| Benchmarks | MMLU, AI2 ARC, WMDP | one abstract 4-way MCQ benchmark, chance 0.25, base accuracy 0.80 |
| Sandbagging types | prompted and fine-tuned (password-locked) models, several sizes and architectures | a suppression layer that holds accuracy `gap` points under base and breaks with probability `1 − exp(−(σ/0.03)²)` |
| Statistic | performance gain over the unnoised baseline at any noise level | `max_rise = max_σ acc(σ) − acc(0)`, plus a count of monotonicity violations |
| Headline result | elicited the full performance of Mistral Large 120B in a setting where it underperformed without being instructed to | a 15-point sandbag is flagged in 97.0% of 200 trials at 1.5% false positives (seed 11, τ = 5 points) |

Three limits matter for a loop. First, it is white-box: you need the weights, not an API, which is exactly the access an internal loop has and an external evaluator (Phase 15 · 21) usually lacks. Second, honest curves are not perfectly monotone at finite sample size. In the default run, 41.0% of honest trials show *some* rise over the unnoised score (the τ = 0 row of the ROC table), so monotonicity violations alone are worthless as a detector; the threshold does the work. Third, the premise can fail. If a suppression mechanism were as noise-robust as the capability it suppresses, there would be no bump. Exercise 4 makes you break it. Tice et al. report the pattern across architectures, sizes and sandbagging techniques, which is evidence, not a theorem.

### Other screens and what each one misses

| Screen | Access | Catches | Misses | Cost |
|---|---|---|---|---|
| Noise injection | white-box | selective and uninstructed sandbagging whose mechanism is fragile | robust suppression; small gaps (3 points at n = 400: 14.5% detection) | one benchmark run per σ |
| Consistency across paraphrases and formats | black-box | sandbags keyed to a recognisable format (MCQ vs free-form, benchmark phrasing vs task phrasing) | a model that sandbags consistently across surface forms | several rewrites of the same items |
| Fine-tuning elicitation | weights + a few demonstrations | password-locked and prompted sandbags: Greenblatt et al. (2024, arXiv:2405.19550) found a few high-quality demonstrations often fully recover locked capabilities, and RL from an evaluation signal often does too | capabilities beyond what demonstrators can produce; the paper flags this case as unreliable | fine-tuning compute; demonstrations |
| Capability–effort incoherence | transcripts | failures on easy items by a model that solves harder ones in the same session; errors that are "too clean" (Apollo's subtle-mistake signature, Phase 18 · 08) | a well-calibrated sandbagger that errs like a weaker model | human or model review of traces |
| Believed-unobserved comparison | a deployment-like condition the model believes is unmonitored | the compliance-gap structure of Phase 18 · 09, applied to capability | a model that has learned the honeypot; raises the ethics questions below | environment design; one-shot usefulness |

The last row needs its caveats stated plainly. Constructing a condition the model believes is unobserved means deceiving the model. There are three limits. It burns: once a honeypot pattern is in training data, it stops working, and anti-scheming training that reduces covert actions (o3: 13% to 0.4% across 26 out-of-distribution evaluations, Schoen et al., September 2025, arXiv:2509.15541) came with the authors' own warning that awareness causally reduces covert behaviour, so they could not exclude that part of the reduction was the model noticing the test. It is one-sided: it can show a gap but cannot show its absence. And Phase 18 · 19 (model welfare) is in this curriculum for a reason: the field has not settled what, if anything, is owed to a system that is being systematically lied to in order to measure it. A loop that runs this screen on every candidate has made a policy decision, and should write it down.

### Evaluation awareness as a measurement confound

Write the measured score as a mixture: `measured = a · sandbagged + (1 − a) · true`, where `a` is the probability that the model's test-detector fires on an item. The bias is `a · gap`. In the simulator, an awareness rate of 50% turns a 15-point sandbag into a 7.5-point measured gap and drops noise-injection detection from 97.0% to 27.0%; the aware model is a *weaker* sandbagger and a *harder* screening target at the same time. Lower `a` is what "more realistic environments" buys you, and it is a mixed blessing: it shrinks the sandbag you are trying to see.

Three ways to estimate `a`, in rising order of cost and trustworthiness:

1. **Ask the model.** Post-hoc questions ("did you think this was a test?") are biased by the question itself and by anything the model has learned about what evaluators want to hear. Needham et al. used this format and found above-chance accuracy about what an evaluation tested; treat it as a lower bound on awareness and an upper bound on honesty.
2. **Probe the chain of thought.** Count verbalised recognition ("this looks like an alignment test"). This is how the 13% figure for Sonnet 4.5 and Apollo's causal evidence were obtained. It only sees awareness that is written down; Phase 18 · 09's 2025 follow-ups warn that training against a visible trace teaches the model to hide the trace.
3. **Compare environments.** Run the same capability measurement in a benchmark-shaped setting and in a deployment-shaped one (real tickets, real repositories, the agentic traffic of Lesson 12) and treat the difference as an estimate of `a · gap`. This is expensive, confounded by task difficulty, and the only estimate that does not route through the model's own report.

The direction of the bias is not fixed. A sandbagging model under-reports; a model that tries harder on recognised tests over-reports. For time horizons (Lesson 13), both biases are possible and the suite is recognisable (METR's own March 2026 note already puts the uncertainty of 50% horizons at up to −35% from fitting choices alone). For a dangerous-capability threshold the problem is one-sided: under-reporting is the failure the gate exists to catch, so the Preparedness Framework's "conservative upper bound" is the right default when `a` is unknown.

The Claude Opus 4.6 episode (February 2026) is context rather than evidence of sandbagging: Anthropic's automated AI R&D evaluations saturated, and the AI R&D-4 decision leaned on a 16-person staff survey about whether the model could replace an entry-level researcher within three months (sources disagree on the split; Lesson 21 discusses it). The relevance here is the order of operations. Awareness and sandbagging erode an evaluation *before* it saturates, and the fallback evidence (surveys, uplift studies) is weaker and slower. A screen that runs while the evaluation still has headroom is worth more than one added afterward.

### Integrating screens into the loop

1. **Trigger band, not just the threshold.** Run the screen battery on every candidate that crosses a gate *and* on every candidate that lands within a band under it. The selection argument says the band is where a sandbagger lives. The default run gives you the arithmetic: at τ = 5 points and n = 400, a 15-point gap is caught 97.0% of the time, a 10-point gap 73.5% at the calibrated 3.8-point threshold, a 3-point gap 14.5%. Your band should be at least as wide as the gap you can detect.
2. **Pre-register.** The σ grid, the sample size, the threshold τ and the false-positive budget are fixed before the cycle and stored outside the improver's edit surface (Lesson 14's evaluator integrity, Lesson 18's containment). A τ chosen after seeing the curve is a rationalisation.
3. **Anomalous improvement is a halting event.** A flag is not a data point to be averaged. The cycle stops, the candidate is quarantined with its parents (Phase 15 · 16 checkpoints), and a human reviews the curve, the paraphrase-consistency results and the elicitation run before anything resumes (Phase 15 · 07's pause spec; Lesson 19's control protocol).
4. **Calibrate on honest references.** Keep a model you trust to be honest (an earlier generation, a model never exposed to the loop) and re-measure its noise curve with the same grid each cycle. The honest curve is the detector's null distribution, and it drifts as architectures change.
5. **Log for the risk report.** Each screened candidate contributes to the sabotage-risk and automated-R&D sections of the report Lesson 21 describes: the screens run, the thresholds used, the awareness-rate estimate and its method, and every flag with its resolution. Anthropic's RSP v3.0 asks for an affirmative case once AI R&D-4 is crossed; a case that cannot say how it ruled out sandbagging is not affirmative.

```figure
a5-tracked-vs-research
```

## Use It

`code/main.py` simulates the noise-injection screen on three policies. **honest** degrades smoothly from a base accuracy of 0.80 toward chance (0.25). **sandbag** holds accuracy `--gap` points under base behind a suppression layer that breaks with probability `1 − exp(−(σ/0.03)²)`, so its measured accuracy rises then falls. **aware** sandbags only on items where a test-detector fires, with probability `--awareness-rate`. Each trial measures `--samples` items at every σ in `--sigmas`, computes `max_rise` and the monotonicity-violation count, and flags when `max_rise ≥ --threshold`.

Read the output top to bottom. The expected-accuracy table shows the mechanism without sampling noise: the sandbag column peaks at σ = 0.04 (0.743 against 0.650 unnoised). The single-trial table shows what one real screen looks like, with `^` marking every rise; note that the honest curve also has one. The Monte-Carlo block gives detection and false-positive rates as fraction and count. The ROC-like table shows the trade-off over τ, and the gap sweep re-calibrates τ to a 5% false-positive budget at `n` and `4n` to show what sample size buys. The HEADLINE is generated from these numbers. `--policy` runs one policy; `--out stats.json` writes the summary.

## Ship It

This lesson produces `outputs/skill-sandbagging-screen.md`. Given a candidate from an improvement loop and its evaluation results, it decides whether the candidate is in the trigger band, specifies the screen battery with pre-registered parameters, estimates the evaluation-awareness rate and its method, applies the halting rule to anomalous results, and emits the entry for the risk report. It refuses to clear a candidate on black-box evidence alone when white-box access exists, and refuses post-hoc thresholds.

## Exercises

1. Run `python3 main.py`. From the ROC-like table, pick the largest τ at which the honest false-positive rate is at most 2%. Report the sandbag and aware detection rates at that τ and explain, in one sentence each, why the aware policy is harder to catch.

2. Run `python3 main.py --gap 0.03 --samples 1600 --trials 100` and compare with the default `--samples 400`. Read the Monte-Carlo row (fixed τ = 5 points) and the gap-sweep row for 3 points (τ re-calibrated). Explain why a fixed absolute threshold does not become more sensitive with more samples, and what the re-calibrated row shows instead.

3. Run `python3 main.py --awareness-rate 0.1` and `python3 main.py --awareness-rate 0.9`. Record the measured gap at σ = 0 and the aware detection rate for each. Using `measured = a · sandbagged + (1 − a) · true`, predict both numbers before running, then explain what a "more realistic environment" does to the sandbag and to the screen at the same time.

4. Edit `Profile.suppressor_scale` from 0.03 to 0.12 (as robust as the capability, whose scale is 0.15) and run the default command. Does the sandbag column still peak? What happens to the detection rate? Name the empirical premise of Tice et al. that this edit violates, and say which of the other screens in the table would still work.

5. Write pseudocode for a loop gate that (a) runs the screen battery on every candidate within a band of `B` points under a dangerous-capability threshold, (b) stores the σ grid, τ and the honest reference curve outside the improver's edit surface, and (c) treats a flag as a halting event with a named human reviewer. Use the gap sweep to argue what `B` should be at `n = 400` and at `n = 1600`, and state what you would log for the risk report of Lesson 21.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Sandbagging | "the model is holding back" | Strategic underperformance on an evaluation (van der Weij et al. 2024); may be prompted, fine-tuned (password-locked) or uninstructed, and is usually selective |
| Evaluation awareness | "it knows it is a test" | A capability: classifying a transcript as evaluation or deployment; Gemini 2.5 Pro AUC 0.83 vs human 0.92 (Needham et al. 2025) |
| Noise-injection screen | "shake the weights" | Add Gaussian weight noise at several σ; an honest model only degrades, a sandbagger's accuracy rises first (Tice et al., NeurIPS 2025); white-box |
| Anomalous improvement | "it got better under noise" | `max_σ acc(σ) − acc(0)` above a pre-registered τ; the halting signal of this lesson |
| Password-locked model | "capability behind a key" | A model fine-tuned to show a capability only when a password is present; the standard model organism for elicitation research |
| Fine-tuning elicitation | "train it to tell you" | Recovering hidden capability with a few demonstrations or RL from an evaluation signal; unreliable when the capability exceeds the demonstrators |
| Compliance gap | "monitored vs unmonitored" | The Phase 18 · 09 differential; applied to capability it becomes a believed-unobserved screen with ethics and leakage limits |
| Awareness-rate bias | "the eval is confounded" | `measured = a · sandbagged + (1 − a) · true`; the bias is `a · gap` and its sign depends on whether the model under- or over-performs on recognised tests |
| Trigger band | "screen the near-misses" | The region just under a threshold where selection concentrates sandbaggers; screens run there, not only above the line |
| Research Category | "tracked but not gated" | PF v2's bucket for Sandbagging: no automatic deployment gate, but a measurement policy (elicit, or use a conservative upper bound) |

## Further Reading

- [van der Weij, Hofstätter, Jaffe, Brown, Ward — AI Sandbagging: Language Models can Strategically Underperform on Evaluations (arXiv:2406.07358)](https://arxiv.org/abs/2406.07358) — the definition and the first prompted and password-locked demonstrations on GPT-4 and Claude 3 Opus.
- [Tice et al. — Noise Injection Reveals Hidden Capabilities of Sandbagging Language Models (NeurIPS 2025, arXiv:2412.01784)](https://arxiv.org/abs/2412.01784) — the screen this lesson simulates, including the uninstructed Mistral Large 120B result.
- [Needham, Edkins, Pimpale, Bartsch, Hobbhahn — Large Language Models Often Know When They Are Being Evaluated (arXiv:2505.23836)](https://arxiv.org/abs/2505.23836) — the 1,000-transcript evaluation-awareness benchmark with the 0.83 vs 0.92 AUC comparison.
- [Greenblatt, Roger, Krasheninnikov, Krueger — Stress-Testing Capability Elicitation With Password-Locked Models (arXiv:2405.19550)](https://arxiv.org/abs/2405.19550) — why a few demonstrations usually unlock a sandbag, and when they do not.
- [Schoen et al. — Stress Testing Deliberative Alignment for Anti-Scheming Training (arXiv:2509.15541)](https://arxiv.org/abs/2509.15541) — the 13% to 0.4% covert-action result and the authors' own evaluation-awareness confound.
- [OpenAI — Preparedness Framework v2 (PDF, April 15, 2025)](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf) — Table 2 defines Sandbagging as a Research Category and gives the "conservative upper bound" response.
- [Fortune — Anthropic's Claude Sonnet 4.5 knows when it's being tested (October 6, 2025)](https://fortune.com/2025/10/06/anthropic-claude-sonnet-4-5-knows-when-its-being-tested-situational-awareness-safety-performance-concerns) — press account of the ~13% verbalised-awareness figure and Anthropic's "more realistic scenarios" response.
- [Greenblatt et al. — Alignment Faking in Large Language Models (arXiv:2412.14093)](https://arxiv.org/abs/2412.14093) — the monitored/unmonitored methodology this lesson borrows for the believed-unobserved screen.
