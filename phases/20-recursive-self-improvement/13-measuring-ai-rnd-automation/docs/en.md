# Measuring R&D Automation: RE-Bench, PaperBench, MLE-bench, Time Horizons

> "Automating AI R&D" is a measurement claim before it is a capability claim. METR's RE-Bench (Nov 2024) found agents scoring 4× human experts on seven research-engineering tasks at a 2-hour budget, and humans scoring 2× the best agent at 32 hours — same tasks, opposite verdicts, depending on the budget. OpenAI's PaperBench (ICML 2025) scored its best agent at 21.0% against ML PhDs at 41.4% after 48 hours. METR's Time Horizon 1.1 (Jan 2026) put the post-2023 doubling time at 131 days, and METR's own modelling note of Mar 20, 2026 showed that reasonable alternative fits move recent 50% horizons by up to −35% and 80% horizons by up to +100%. This lesson is about where those numbers come from and how they break.

**Type:** Learn
**Languages:** Python (stdlib, time-horizon estimator with truncation, noise and fit-choice contrasts)
**Prerequisites:** Phase 15 · 21 (METR external evaluation), Phase 02 · 09 (model evaluation), Lesson 11 of this phase
**Time:** ~75 minutes

## Learning Objectives

- Define "automating AI R&D" operationally as a task distribution, a human baseline, a success criterion and a budget, and explain why "intern-level" is undefined without all four.
- Compare RE-Bench, PaperBench, MLE-bench and HCAST/SWAA on what they sample, how they score, and where each saturates.
- Derive the 50% and 80% time horizons from a logistic fit of success against log human time, and attach bootstrap confidence intervals.
- Diagnose three failure modes of horizon measurement — suite truncation, noisy human baselines and fit choice — and quantify each with the simulator.
- Write a time-horizon report that discloses everything a governance threshold (RSP, PF, FSF) will consume.

## The Problem

Lesson 11 of this phase ended on the "intern ladder": Altman's October 2025 target of an intern-level AI research assistant by September 2026, OpenAI's September 2026 statement that the goal had been reached, Anthropic's press-reported rating of Claude at AL4+ for 26% of internal AI R&D work as of August 2026. Each of those is a sentence wrapped around a number, and the number came out of a measurement. If you cannot reconstruct the measurement, you cannot tell whether two such claims agree, contradict, or talk past each other.

Phase 15 · 21 introduced METR and the time horizon as a headline scalar and warned that a horizon is an upper bound, not a deployment prediction. This lesson goes inside the methodology. Four benchmark families (RE-Bench, PaperBench, MLE-bench, HCAST/SWAA) feed one cross-benchmark metric (the time horizon), which feeds three governance frameworks (RSP, PF, FSF — Lesson 21 of this phase). Every link in that chain has known failure modes, and in 2026 the frontier of model capability sits exactly where those failure modes bite: at the ceiling of the task suites.

The engineering stance: a team that cannot say how a horizon was fit cannot say what a threshold crossing means.

## The Concept

### Four things every automation claim must pin down

"Intern-level" has no content until you say what the intern does, who you compare against, how you score, and how long each side gets. Operationally, an "AI R&D automation" claim is a tuple:

| Component | Question it answers | What goes wrong when it is missing |
|---|---|---|
| Task distribution | Which tasks, sampled how? | Cherry-picked tasks; no way to say what fraction of a job is covered |
| Human baseline | Who did the task, under what conditions, how long did it take? | "Expert" could mean a PhD with 48 h or a contractor with 2 h |
| Success criterion | Binary pass/fail, continuous score, judge, medal? | Partial credit inflates; binary thresholds hide near-misses |
| Budget | Wall-clock, tokens, dollars, attempts (best-of-k)? | Agents win at short budgets and lose at long ones; the budget picks the winner |

RE-Bench shows why the budget is not a detail: at 2 hours agents scored 4× humans, at 8 hours humans narrowly exceeded agents, and at 32 hours humans scored 2× the best agent (Wijk et al., arXiv:2411.15114). The same tasks and the same models produce opposite verdicts, because humans keep improving with time and agents plateau.

### The benchmark suite

| Benchmark | Source | Tasks | Human baseline | Score | Headline (as published) |
|---|---|---|---|---|---|
| RE-Bench | METR, Nov 2024, arXiv:2411.15114 | 7 open-ended ML research-engineering environments | 71 eight-hour attempts by 61 experts | Continuous, 0 = starting solution, 1 = reference solution | Agents 4× humans at 2 h; humans 2× agents at 32 h |
| PaperBench | OpenAI, ICML 2025, arXiv:2504.01848 | Replicate 20 ICML 2024 Spotlight/Oral papers; 8,316 rubric leaf nodes | 8 ML PhDs, 4-paper subset, 3 attempts each, 48 h | LLM judge against hierarchical rubrics | Best agent 21.0% (Claude 3.5 Sonnet (New), BasicAgent); humans 41.4% best-of-3 at 48 h vs 26.6% for o1 on the same subset |
| MLE-bench | OpenAI, Oct 2024, arXiv:2410.07095 | 75 Kaggle competitions | Kaggle leaderboards | Medal rate (bronze or better) | o1-preview + AIDE medals in 16.9% of competitions |
| HCAST | METR, Mar 2025, arXiv:2503.17354 | 189 ML, cyber, SWE and reasoning tasks, 1 min to 8+ h | 563 baselines, over 1,500 h | Binary success | Main input to time-horizon estimates |
| SWAA | METR, Mar 2025 | 66 very short software actions | Seconds-scale baselines | Binary success | Anchors the short end of the horizon curve |

Three details matter more than the headline numbers.

**The scaffold moves the number as much as the model.** On PaperBench, o1 scored 13.2% with the BasicAgent scaffold and 24.4% with IterativeAgent, while Claude 3.5 Sonnet went the other way (21.0% → 16.1%). A benchmark score is a (model, scaffold, budget) triple; reporting the model alone is a category error. METR's RE-Bench runs similarly used two scaffolds (AIDE and Modular) and best-of-k sampling.

**The judge is part of the instrument.** PaperBench grades 8,316 leaf nodes with an LLM judge and ships a separate benchmark (JudgeEval) to measure the judge. A judge that is 90% accurate per node is not 90% accurate on the aggregate; errors correlate within papers. Lesson 14 of this phase treats judge integrity inside improvement loops; here the point is only that the judge's error bars belong in the report.

**Continuous scores saturate and plateau differently from binary ones.** RE-Bench reports a normalised score where 1.0 means "matched the reference solution" and more than 1.0 means "beat it". AI 2027 (Kokotajlo et al., Apr 2025) forecast a RE-Bench score of about 1.3 by early 2026 as a milestone on the way to a superhuman coder; a public tracker reports 0.5–0.8 at the 8-hour budget as of June 2026. Both figures are secondary and have not been verified against METR's own published runs; treat the comparison as indicative. The lesson holds regardless: the paper's own data show agent scores plateauing with budget while humans keep climbing, so a budget-fixed score understates the human and a budget-free extrapolation overstates the agent.

### Time horizon as the cross-benchmark metric

A time horizon turns a pile of (task, human time, agent success) triples into one scalar. METR's construction (Kwa et al., arXiv:2503.14499, Mar 2025):

1. Give every task a human completion time `t` (measured baseline or estimate).
2. Run the agent; record success or failure.
3. Fit a logistic curve in log time: `P(success | t) = σ(β · (ln h50 − ln t))`.
4. Report `h50` (the task length at which predicted success is 50%) and `h80 = h50 · 4^(−1/β)` (the 80% point; `ln 4` is the logit of 0.8).

The 50% horizon is a capability number; the 80% horizon is a reliability number, and it is always shorter, by a factor that depends on the slope `β`. A shallow slope (success degrades slowly with task length) makes `h80` far below `h50`; a steep slope brings them together. That dependence is the root of most of the trouble below.

Kwa et al. fit this across HCAST, RE-Bench and SWAA and found the 50% horizon doubling roughly every seven months since 2019, with Claude 3.7 Sonnet at about 50 minutes. Time Horizon 1.1 (METR, Jan 29, 2026) grew the suite from 170 to 228 tasks, raised the count of long (8 h+) tasks from 14 to 31, and re-estimated the post-2023 doubling time at 131 days (130.8 days, CI 107–161) against 165 days under TH 1.0; the 2019–2025 trend stays near 196 days (about seven months). Claude Opus 4.5 sits at 320 minutes with a CI of 170–729 minutes. Two caveats from the same post: only 5 of the 31 long tasks have measured human baselines (the rest use estimates), and adding long tasks shrank Opus 4.5's upper CI bound from 4.4× to 2.3× the point estimate — a direct demonstration that the right tail of the suite controls the precision of frontier estimates.

### Three ways the number breaks

METR's note of Mar 20, 2026 (Barry, "Impact of modelling assumptions on time horizon results") is the most candid document on this, and the simulator in this lesson reproduces each mechanism.

**Truncation.** A suite has a longest task. If the agent still succeeds at that length, the curve's descent is never observed and the horizon is an extrapolation. Any suite-bounded estimator — isotonic regression, a rolling average, "longest bin above 50%" — simply cannot return a value above the ceiling, so it is biased down whenever the true horizon exceeds the ceiling. A parametric logistic can extrapolate, but it buys that by trusting the functional form: its confidence interval explodes instead. METR's note says the suite has no task above 30 hours, that the right tail is "not meaningfully constrained", and that measurements above roughly 16 hours are unreliable with the current suite (the 16-hour figure is quoted from METR's model reports by secondary sources). On the simulator's default run, dropping tasks above 8 hours moves the suite-bounded estimate for a 16-hour agent to 7.2 hours and widens the logistic's 95% interval from 3.1× to 9.5×.

**Noise in human times.** METR estimates that 80% of individual baseline attempts fall within about 3× of the true task length. Noise in the x-variable of a regression attenuates the slope (classical errors-in-variables), which rotates the fitted curve around the data's centroid: horizons on the far side of the centroid are pushed outward. METR's SIMEX correction suggests the noise inflates frontier 50% horizons by around 30% (anywhere from 0% to 60% cannot be ruled out) and deflates 80% horizons by around 20%. Capping recorded lengths at 8 hours alone lowers 50% horizons by 10–15%. The simulator's noisy-suite replicates show the same shape: median slope 0.53 against a true 0.6, and the 50% horizon above truth in 14 of 20 replicates.

**Fit choice.** METR tried a logistic with a free slope, a logistic with one slope shared across all models (which won the leave-one-family-out cross-validation), a reliability-ceiling variant, beta-binomial, Cauchy and Weibull curves, and several non-parametric smoothers. For recent models the reasonable alternatives decrease 50% horizons by up to 35% and increase 80% horizons by up to 100%; for Claude Opus 4.6 the spread is about 1.5× on the 50% horizon and 2× on the 80% horizon. A regularisation bug fixed earlier in 2026 had been inflating recent models' 50% horizons by up to 20%. Restricting to METR's private (never-public) tasks cut Opus 4.6's 50% horizon from 11 h 59 min to 7 h 11 min. And the published confidence intervals are "often a factor of 2 in both directions". The note's conclusion is worth quoting in spirit: most reasonable variations lower recent 50% estimates, all stay inside the (very wide) intervals, and task selection matters more than any modelling choice.

### Saturation and evaluator exhaustion

When a model succeeds on nearly every task in a suite, the suite stops producing information. Anthropic's Claude Opus 4.6 system card (Feb 2026) reported that the model had saturated most of its automated AI R&D evaluations, so they could no longer rule out the AI R&D-4 threshold, and the decision leaned on a survey of 16 technical staff asked whether the model could become a drop-in replacement for an entry-level researcher within three months. Secondary summaries disagree on the split of answers (one reports 0 of 16 saying yes; another 11 unlikely, 3 likely with scaffolding, 2 already) — treat the breakdown as unsettled and the fallback itself as the fact that matters.

A saturated benchmark is a worse instrument than a noisy one, because it fails silently: the score stops moving while the capability keeps moving. Extrapolating a doubling trend through saturated points is unsafe for the same reason extrapolating a logistic past the longest task is unsafe. The remedies are structural: new long tasks (TH 1.1's 31 tasks of 8 h+; a reported METR–Epoch collaboration on longer tasks was described by commenters as partially saturated while being built — secondary), held-out and private task pools (METR's private-only estimate is the first public sensitivity check of this kind), and live tasks whose answers did not exist at training time. Lesson 14 of this phase builds the held-out and live-task discipline into the loop.

### From measurement to threshold

Governance thresholds are consumers of these numbers. Anthropic's RSP v3.x AI R&D-4 asks whether a model could fully automate an entry-level researcher or "double the rate of progress", where v3.1 clarified that doubling means compressing two years of 2018–2024 aggregate capability progress into one — a claim about the research process, not about one benchmark score. OpenAI's Preparedness Framework v2 defines High and Critical AI Self-improvement levels in terms of researcher-assistant equivalence and generational-improvement speed (wording from secondary summaries). DeepMind's FSF v3/v3.1 defines "ML R&D acceleration level 1" and "ML R&D automation level 1". None of these is a benchmark number; each is an inference from several. Lesson 21 of this phase takes the frameworks apart. What this lesson supplies is the disclosure list a measurement must carry before it is fit to be consumed:

- the task suite's length distribution and ceiling, and how many tasks lie above the estimated horizon;
- how many human baselines were measured rather than estimated, and their spread;
- the functional form, slope treatment, regularisation and weighting of the fit, with a suite-bounded non-parametric cross-check;
- 50% and 80% horizons with bootstrap intervals, plus a sensitivity table over truncation, noise and fit choice;
- for trend claims, the number of points, the window and the doubling time with its own interval;
- which benchmark scores are saturated and were therefore excluded.

```figure
a5-horizon-fit
```

## Use It

`code/main.py` is a stdlib time-horizon estimator with the three failure modes built in. It generates a suite of tasks with human times log-uniform between 1 minute and 32 hours, samples agent successes from a latent logistic with a true 50% horizon (default 16 h, slope 0.6), then:

- **A** fits the logistic by maximum likelihood (profile likelihood with golden-section search), reports `h50`/`h80` with bootstrap 95% intervals, prints a suite-bounded isotonic estimate as a cross-check, and prints two identifiability diagnostics (tasks longer than the fitted horizon; success rate on the 20 longest tasks);
- **B** drops tasks above `--max-task-hours` (default 8 h) and refits — watch the isotonic estimate pin to the ceiling and the logistic interval widen;
- **C** adds log-normal noise to the recorded human times (`--time-noise`, default 0.85, which puts about 80% of recorded times within 3× of truth, matching METR's estimate), refits, and repeats over 20 replicate suites to separate the systematic effect from one unlucky draw;
- **D** refits the same clean data under four slope assumptions;
- **E** fits a doubling time to a synthetic release series and extrapolates to a 167-hour (one work-month) task.

Flags: `--tasks`, `--true-horizon`, `--max-task-hours`, `--bootstrap`, `--time-noise`, `--seed`. The HEADLINE at the end is composed from the computed numbers. Read the identifiability line in section A before anything else: when the agent still succeeds on a fifth of the longest tasks, every later number is an extrapolation.

## Ship It

`outputs/skill-time-horizon-report.md` turns a set of agent runs with human baselines into a time-horizon report that discloses suite, baseline, fit and sensitivity before it states a number, and refuses to state one when the horizon is above the suite's reliable range. It is the input format Lesson 21 of this phase assumes when a framework threshold is assessed.

## Exercises

1. Run `python3 main.py` and read section A. How many tasks are longer than the fitted horizon, and what is the success rate on the 20 longest? Explain in one sentence why the point estimate (9.8 h) and the isotonic cross-check (18.8 h) can disagree by almost 2× while the bootstrap interval contains the truth.

2. Run `python3 main.py --true-horizon 4 --seed 3`. Compare the truncation section with the default run: why does an 8-hour ceiling barely matter for a 4-hour agent but dominate for a 16-hour one? State the rule in terms of the success rate at the ceiling.

3. Run `python3 main.py --max-task-hours 32 --bootstrap 60` and then `--max-task-hours 8 --bootstrap 60`. Tabulate the logistic `h50`, its interval width and the isotonic estimate for each. Which of the two estimators would you report to a governance process, and what would you disclose alongside it?

4. METR's note says noise correction could reduce frontier 50% horizons by about 30%. Run `python3 main.py --time-noise 0`, `--time-noise 0.85` and `--time-noise 1.2` and record the median slope and median `h50` across the 20 replicates in section C. Derive the attenuation factor `var(ln t) / (var(ln t) + σ²)` for a log-uniform spread of 1 min to 32 h and check it against the observed slope shrinkage.

5. (Hard) Section E fits a doubling time to 13 half-yearly points. Modify `synthetic_release_series` so that the last three points are saturated (capped at the suite ceiling of 32 h) and refit. Report how the all-points and last-5-points doubling times move, then write the two sentences you would add to a time-horizon report to disclose the saturation.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Time horizon (50%) | "The model can do 16-hour tasks" | The human task length at which a fitted logistic predicts 50% agent success on a specific suite, with a specific fit |
| 80% horizon | "The reliable horizon" | The 80% point of the same curve; shorter than the 50% point by `4^(1/β)`, so it depends heavily on the slope |
| Human baseline | "Expert time" | A measured or estimated completion time; METR estimates 80% of individual baselines lie within about 3× of truth |
| Suite ceiling | "The longest task" | The length above which nothing is observed; no suite-bounded estimator can exceed it |
| Identifiability | "Is the number real?" | Whether the data constrain the parameter; low success on the longest tasks is what pins down a horizon |
| Fixed-slope fit | "METR's regularised logistic" | One slope shared across models; best in METR's leave-one-family-out cross-validation but a modelling assumption nonetheless |
| Errors-in-variables | "Noisy x" | Measurement noise in task length attenuates the fitted slope and rotates the curve about the data centroid |
| Saturation | "The benchmark is solved" | The score no longer moves with capability; Opus 4.6's system card fell back to a staff survey for this reason |
| Medal rate | "MLE-bench score" | Fraction of Kaggle competitions where the agent reaches bronze or better; 16.9% for o1-preview + AIDE |
| Doubling time | "Four months" | Slope of a least-squares line through log horizon vs date; 131 days post-2023 in TH 1.1, with CI 107–161 |

## Further Reading

- [METR — Impact of modelling assumptions on time horizon results (Mar 20, 2026)](https://metr.org/notes/2026-03-20-impact-of-modelling-assumptions-on-time-horizon-results/) — the sensitivity analysis this lesson is built around; read it before quoting any horizon.
- [METR — Time Horizon 1.1 (Jan 29, 2026)](https://metr.org/blog/2026-1-29-time-horizon-1-1/) — the suite expansion from 170 to 228 tasks and the 131-day post-2023 doubling time.
- [Kwa et al. — Measuring AI Ability to Complete Long Software Tasks (arXiv:2503.14499)](https://arxiv.org/abs/2503.14499) — the original time-horizon construction and the seven-month doubling.
- [Wijk et al. — RE-Bench (arXiv:2411.15114)](https://arxiv.org/abs/2411.15114) — the budget-dependence result; agents 4× humans at 2 h, humans 2× agents at 32 h.
- [Starace et al. — PaperBench (arXiv:2504.01848)](https://arxiv.org/abs/2504.01848) — rubric-and-judge design, scaffold sensitivity and the 48-hour PhD baseline.
- [Chan et al. — MLE-bench (arXiv:2410.07095)](https://arxiv.org/abs/2410.07095) — medal rate as a success criterion and its leaderboard baseline.
- [Rein et al. — HCAST (arXiv:2503.17354)](https://arxiv.org/abs/2503.17354) — how 563 human baselines were collected for 189 tasks.
- [METR — eval-analysis-public](https://github.com/METR/eval-analysis-public) — the analysis code; compare its fitting choices with `code/main.py`.
