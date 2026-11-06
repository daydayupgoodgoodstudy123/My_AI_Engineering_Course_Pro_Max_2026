# The Math of Takeoff: Returns, Reproduction Number and Ceilings

> Davidson and Houlden (Forethought, 4 August 2025) put the returns to software R&D at a median of r ≈ 1.2 with a plausible range of 0.4–3.6, and gave roughly 60% odds that more than three years of AI progress get compressed into one year once AI automates AI research, and roughly 20% odds for more than ten years. Burtsev (arXiv:2609.00137, 31 August 2026) rephrased the same question in the language of epidemics: a recursive reproduction number R_AI above 1 means each development cycle's gains compound into the next, and the threshold is a property of the loop's structure, not of how capable the model is. Both stories reduce to one contest, feedback against diminishing returns, and the contest is decided by a single exponent. This lesson derives that exponent with nothing heavier than logarithms, checks the published numbers against their sources, and then lets you simulate the rest.

**Type:** Learn
**Languages:** Python (stdlib, discrete-cycle takeoff simulator)
**Prerequisites:** Lesson 01 of this phase, Phase 01 · 04 (calculus for ML), Phase 15 · 07 (RSI)
**Time:** ~75 minutes

## Learning Objectives

- Write the software-only feedback loop as a one-line difference equation and read off from a single exponent whether progress accelerates, holds steady or fizzles.
- Explain why r > 1 gives finite-time blow-up in the idealized model, and why that impossibility is itself the lesson.
- State Davidson and Houlden's three governing factors, their central estimates and their headline probabilities, and say which assumption each number leans on.
- Define Burtsev's recursive reproduction number R_AI, translate between r and R_AI, and reproduce his four counterintuitive conclusions with the simulator.
- List the measurable indicators that separate genuine recursive amplification from merely fast progress, and name what the toy model leaves out.

## The Problem

Lesson 01 of this phase sorted systems onto a ladder by how much of the improvement process they own. This lesson asks the quantitative question that the ladder's top rung raises: if AI systems take over AI research, does progress run away?

Two forces pull in opposite directions. Feedback: better software makes the researchers, now AI, more productive, so the next round of research is larger. Diminishing returns: the low-hanging fruit goes first, so each additional order of magnitude of efficiency costs more research than the last. Whether progress accelerates, holds or slows is decided by which force wins, and in the simplest models that is decided by a single number.

Arguments about "intelligence explosion" in 2025 and 2026 often talk past each other because three different things get called an explosion: progress being fast (speed), progress getting faster (acceleration), and each cycle's gains compounding into the next (criticality). You can have any one without the others. Forethought's software-intelligence-explosion work (Eth and Davidson, March 2025; Davidson and Houlden, August 2025) is mostly about acceleration and how far it can run; Burtsev's criticality paper (August 2026) is about compounding. This lesson gives you the algebra to hold all three apart.

## The Concept

### The loop as one line of algebra

Let S be software efficiency: how much capability a fixed amount of compute buys. Start at S = 1 and measure progress in orders of magnitude, L = log10 S. Two ingredients:

- Research input E. When AI does the research, the amount of effective research scales with the quality of the AI: E = S^a. The exponent a is the automation feedback exponent; a = 1 means every unit of research input improves in step with S, a = 0 means research input is fixed (humans only, no feedback).
- Diminishing returns. In Eth and Davidson's framing, r is the number that "quantifies, as software improves, how much harder it becomes to improve AI software further": one doubling of cumulative research effort buys r doublings of S. Equivalently, the progress bought by one unit of research shrinks like S^(−1/r) as S grows.

Put together, the progress made in one development cycle is

```text
ΔL = k · S^a · S^(−1/r) = k · S^(a − 1/r)
```

where k is the progress of the first cycle (S = 1). Everything about the shape of the curve sits in the exponent a − 1/r. With a = 1 it equals (r − 1)/r:

| r | exponent (r − 1)/r | each OOM of progress makes the next cycle's gain ... | shape of S(t) |
|---|---|---|---|
| 0.8 | −0.25 | smaller by 10^(−0.25) ≈ 0.56× | sub-exponential; the rate decays towards zero |
| 1.0 | 0 | the same | exactly exponential; constant "years per year" |
| 1.2 | +0.167 | larger by 10^(0.167) ≈ 1.47× | super-exponential |
| 1.6 | +0.375 | larger by 10^(0.375) ≈ 2.37× | super-exponential, much faster |

Read it as the sign of the race. A negative exponent means diminishing returns win: progress continues forever in the idealized model but at an ever-slower rate (L grows like log t). Zero is the knife edge: the two forces cancel and S grows exponentially, which is what "business as usual" looks like in log space. A positive exponent means feedback wins and the growth rate itself grows.

A worked example with the simulator's defaults (k = 0.25 OOM per quarterly cycle, r = 1.2, a = 1). Each cycle's gain is 0.25 × 10^(L/6):

| cycle | L at start | 10^(L/6) | ΔL | L at end |
|---|---|---|---|---|
| 1 | 0.000 | 1.00 | 0.250 | 0.250 |
| 2 | 0.250 | 1.10 | 0.275 | 0.525 |
| 3 | 0.525 | 1.22 | 0.306 | 0.831 |
| 4 | 0.831 | 1.38 | 0.344 | 1.175 |
| 5 | 1.175 | 1.57 | 0.392 | 1.567 |

The gains grow by 10%, then 11%, then 12%, then 14% per cycle: the compounding itself compounds. For r = 0.8 the same table runs 0.250, 0.217, 0.191, 0.171, 0.155, and the rate has halved by cycle 7.

### Why r > 1 means finite time

Make the loop continuous: dL/dt = k · 10^(εL) with ε = (r − 1)/r > 0. Substitute u = 10^(−εL). Then du/dt = −ε · ln(10) · k, a constant, so u falls linearly and reaches zero, which means L reaches infinity, at the finite time t* = 1/(ε · k · ln 10). In words: when the exponent is positive each doubling of S takes 2^(−ε) times as long as the previous one, and a geometric series of ever-shorter doubling times has a finite sum. For r = 1.2, ε = 1/6 and each doubling takes about 0.89× as long as the last; all the remaining doublings together take only about nine times as long as the next one.

That is what "intelligence explosion" means mathematically: not "very fast" but "infinite in finite time". Since nothing is infinite in finite time, the idealized model must break somewhere, and the interesting question becomes where. Davidson and Houlden's answer is effective limits on how efficient software can get; Lesson 03 of this phase adds compute; Lesson 14 adds the evaluator the loop relies on to know it is making progress. The simulator shows the clean version: with no ceiling, r = 1.2 passes 4.83 years of progress per year at cycle 10 and overflows a double-precision float by cycle 15; with a 10-OOM ceiling the same r peaks at 4.43 years per year at cycle 15 and is down to 0.32 by cycle 18 with the headroom used up.

### Davidson and Houlden: three factors, two probabilities, one ceiling

Eth and Davidson (Forethought, 26 March 2025) argued that ASARA, AI systems for AI R&D automation able to substitute for any remote R&D worker at a frontier lab, would set off a software intelligence explosion if r > 1, and estimated r from historical software domains: image recognition median 1.4 (5th–95th percentile 0.8–2.4), computer chess 0.8, reinforcement-learning data efficiency 1.6, SAT solvers 3.5, linear programming 1.1, and a broad "algorithms in general" figure near 4 that they flag as especially uncertain. Their best guess was that one doubling of cumulative software R&D buys "a few doublings" of capability, with a hardware-adjusted range of roughly 0.5–2.

Davidson and Houlden (Forethought, 4 August 2025) built the follow-up semi-endogenous growth model with three governing parameters:

| factor | what it is | their central view | simulator flag |
|---|---|---|---|
| initial speed-up | how much faster AI research runs the moment ASARA arrives | a distribution over speed-ups; the toy defaults to 1× for clarity, which is not their estimate | `--initial-speedup` |
| returns to software R&D, r | doublings of S per doubling of cumulative research | median 1.2, plausible range 0.4–3.6; r > 1 means accelerating | `--r`, `--r-median`, `--r-sigma` |
| distance to effective limits | how many OOMs of efficiency gain remain after ASARA | 6–16 OOMs; at the historical ~10×/year of effective compute that is 6–16 years of progress | `--ceiling-ooms`, `--ceiling-range` |

Their headline probabilities: about 60% (57% in the main model) that the explosion compresses more than three years of AI progress into less than one year, about 20% (18%) that it compresses more than ten years, with 41% and 12% for the same compressions inside four months. Ten-years-in-one needs both: limits more than 10 OOMs away and returns that stay favourable until near the limits. Thirty-years-in-one would need roughly 30 OOMs of additional gains or "a major paradigm shift that enables massive progress without significant increases in effective compute", which they consider the likelier route. Their own summary: progress "could easily run more than 3× faster and possibly more than 10× faster, but probably not 30× faster" without such a shift. They also say the exact figures should not be trusted; the model assumes smooth trends and does not model a paradigm shift or a sudden end of the current paradigm, so it underestimates both tails.

Note the unit convention, which the simulator adopts: one "year of 2024 progress" is one order of magnitude of effective compute, so 10 years-in-1 means 10 OOMs of software gains inside a calendar year. The Monte-Carlo in `code/main.py` draws r from a log-normal with median 1.2 and a 5–95% range of 0.4–3.6, draws the ceiling uniformly from 6–16 OOMs, and with default settings reports 52.4% for >3 years-in-1 and 22.9% for >10 years-in-1 over a ten-year horizon. The resemblance to Forethought's 60% and 20% is partly construction: a log-normal centred on 1.2 with that range puts 61% of its mass above r = 1, and that is where acceleration lives. The toy is not their model; it is a way to see which knobs those probabilities hang on.

### Burtsev: the recursive reproduction number

Burtsev, "Recursive Criticality of AI Self-Improvement" (arXiv:2609.00137, 31 August 2026), models capability growth from three ingredients: baseline research productivity, recursive feedback, and rising research difficulty. The recursive reproduction number R_AI compares the strength of the feedback with how quickly progress gets harder. When R_AI > 1 "the effects of improvements compound across development cycles"; below 1 they fade. The crossing is a critical transition like an epidemic's: a reproduction number is a property of how the infection spreads, not of how sick any one patient is.

The simulator computes an R_AI-style ratio each cycle:

```text
R_AI(n) = [ log E(S_{n+1}) − log E(S_n) ]  /  [ log D(S_{n+1}) − log D(S_n) ]
```

where E is the research input the next cycle inherits and D = S^(1/r) (times the ceiling's damping) is the difficulty of the next OOM. With E = S^a and no ceiling the ratio is exactly a · r, so the translation between the two framings is one line: Forethought's "r > 1" is Burtsev's "R_AI > 1" for a fully automated loop (a = 1), and partial automation moves the threshold to a · r > 1. With a = 0.5, r = 1.2 is subcritical (0.6), and the Monte-Carlo's P(>3 years-in-1) falls from 52.4% to 10.1%.

Burtsev's four conclusions that surprise people, each with its toy demonstration (`python3 main.py`, sections B and C):

1. Self-amplification can start before acceleration is visible. Add a human baseline (b = 1: humans contribute as much research as the AI does at S = 1). R_AI starts at 0.73 because most of the research is not fed back; it crosses 1 at cycle 3, when the progress rate is 0.72× its starting value and still falling. The rate does not visibly double until cycle 13. For ten cycles, two and a half years, the loop is supercritical while the curve looks like a slowdown.
2. Rapid progress can occur without self-amplification. With b = 3 the first cycle delivers 4 years of progress per year, four times the b = 0 rate, yet R_AI at cycle 1 is 0.58. Most of that speed is baseline, not loop. Conversely at r = 1.0 with no ceiling the system delivers a steady 1 year per year forever with R_AI exactly 1: brisk, and not compounding.
3. Baseline productivity speeds progress but does not change criticality. Raising b from 0 to 3 lifts progress at cycle 8 from 2.71 to 4.53 OOMs, while the asymptotic R_AI stays a · r = 1.2 in every row. (In the toy the baseline dilutes R_AI early, since the recursive share of research input starts small and grows; in Burtsev's continuous formulation baseline productivity enters additively and leaves R_AI untouched. Both agree on where the loop ends up.)
4. Cycle duration becomes the limiting timescale. A loop can compound only once per cycle. Section C holds the yearly starting speed and the horizon fixed and varies the cycle: with one-month cycles 3 years-in-1 arrives at 3.2 years and the ceiling at 3.8; with twelve-month cycles the ceiling arrives at 5.0 years and 3 years-in-1 never registers. Training runs that take months are not a footnote; they are the clock.

Two more of his points fall out of the same tables. Rising difficulty can end amplification: in the r = 1.2 run R_AI drops back below 1 at cycle 15 as the ceiling's damping enters the difficulty term, and the explosion dies with 1.7 OOMs of headroom still unused. And multi-actor sharing: if several labs each feed back only part of their improvements but improvements leak across them, the ecosystem's effective feedback exponent is the sum of the parts, so the ecosystem can be supercritical when no single actor is (Exercise 5).

The threshold is structural. In the toy, R_AI crosses 1 when the recursive share of research input exceeds 1/(a · r): a statement about how much of the loop is closed and how fast difficulty grows, not about any benchmark score. A modest system with a fully closed loop can be supercritical; a far stronger one with humans in the critical path can be subcritical. This is why Lesson 01's ladder, which asks who owns the improvement mechanism, matters more for takeoff than leaderboard position.

### Translating and measuring

| concept | Forethought (Eth & Davidson; Davidson & Houlden) | Burtsev | toy flag |
|---|---|---|---|
| feedback strength | implicit: ASARA means full automation | explicit, measurable | `--feedback` (a), `--baseline` (b) |
| difficulty growth | 1/r per OOM | explicit, measurable | `--r` |
| threshold | r > 1 | R_AI > 1 | a · r > 1 (with b = 0) |
| what ends it | distance to effective limits | rising difficulty | `--ceiling-ooms` |
| timescale | initial speed-up; years of progress per year | cycle duration | `--initial-speedup`, `--cycle-months` |

Burtsev proposes four measurable indicators, and each has a counterpart in this phase: feedback strength (what fraction of the next cycle's research input is produced by this cycle's system; Lesson 13's R&D-automation benchmarks and the lab-reported automation indices are proxies), carry-over (how much of an improvement survives into successor systems rather than being lost at the next pretraining run; Lesson 08's self-edits and Lesson 12's skill libraries are both about carry-over), cycle duration (time from a result to its use in the next research cycle), and the growth rate of research difficulty (how many more experiments the next OOM takes). Together they would let you tell recursive amplification from fast progress driven by compute or by human effort, which is the distinction the governance thresholds in Lesson 21 need.

### What the toy leaves out

- Compute. Eth and Davidson name fixed compute as the main brake: it caps how many experiments run in parallel, and each new generation takes months to train. They argue these delay rather than prevent an explosion; Lesson 03 of this phase builds the two-factor model and tests that claim.
- Evaluator integrity. S in the model is measured by the loop itself. If the metric is gamed, as with DGM's hallucinated test logs in Phase 15 · 04 or the case files in Lesson 15, the loop compounds the wrong thing. Lesson 14 treats Goodhart inside the loop.
- Human bottlenecks. Tasks only humans can do, and what Chen, Wang and Qu's 2026 survey (arXiv:2607.07663) calls the prior problem: deciding what deserves to be evaluated at all. A single exponent a hides all of this.
- Lumps and shifts. Progress comes in discrete releases and paradigm changes; Davidson and Houlden say their smooth model underestimates both tails.
- Noise and measurement. The simulator's per-cycle shocks are a stand-in for the roughly 2× confidence intervals on real measurements such as METR's time horizons (Phase 15 · 21).

Lesson 22 of this phase puts these models next to AI 2027 and Epoch's GATE and shows how to disagree with each one parameter at a time.

```figure
world-model-rollout
```

## Use It

`code/main.py` is a discrete-cycle toy, not Forethought's or Burtsev's model. Each cycle it applies ΔL = k · (b + S^a) / S^(1/r) · (1 − L/ceiling) and records the progress rate in years of 2024 progress per year, with one year defined as one OOM. Four sections:

- A. Returns: r = 0.8, 1.0, 1.2, 1.6 without noise, each next to a no-ceiling twin so you can separate "the ceiling bent it" from "r bent it". Look at the cycle where the rate doubles (or halves), the cycle where 3 years-in-1 is first reached, and when R_AI falls back below 1.
- B. Baseline contrast: r = 1.2 with b = 0, 1, 3. Look at the `R_AI>=1` column against the `doubles` column; the `lag` is Burtsev's first conclusion counted in cycles.
- C. Cycle duration: 1, 3 and 12-month cycles at the same yearly starting speed and the same horizon.
- D. Monte-Carlo: 2,000 trials with log-normal r (median 1.2, 5–95% 0.4–3.6), a ceiling drawn from 6–16 OOMs and 15% per-cycle noise. Read P(>3 years-in-1), P(>10 years-in-1), and the conditional P(>10 | ceiling > 10 OOMs).

Flags worth touching: `--r`, `--feedback`, `--baseline`, `--ceiling-ooms` (accepts `inf`), `--ceiling-range`, `--cycles`, `--cycle-months`, `--initial-speedup`, `--r-median`, `--trials`, `--seed`, `--out summary.json`. The HEADLINE is assembled from the computed numbers, so it changes when you do.

## Ship It

`outputs/skill-takeoff-parameter-sheet.md` turns any takeoff claim, whether a forecast post, a paper abstract or a lab's safety case, into a one-page parameter sheet: the implied r, feedback strength a (and what is held back as baseline), ceiling in OOMs, cycle duration and initial speed-up, each with the evidence offered and the evidence that would move it; a classification of the claim as being about speed, acceleration or criticality; and the three parameters the claim is most sensitive to. It refuses to produce a sheet for claims that pin down none of the five parameters, because such claims cannot be disagreed with.

## Exercises

1. Run `python3 main.py --ceiling-ooms inf --r 1.0 1.2 --trials 200`. Confirm that r = 1.0 holds exactly 1.00 years per year for all 40 cycles and that r = 1.2 reads BLOW-UP by cycle 15. Then reproduce cycles 1–5 of the r = 1.2 run by hand (ΔL = 0.25 × 10^(L/6)) and check that you land on 1.57 OOMs at cycle 5.
2. Run `python3 main.py --feedback 0.5`. All four r scenarios are now subcritical and P(>3 years-in-1) falls from 52.4% to 10.1%. Explain the threshold a · r > 1 in words, and describe one real research organisation whose a is closer to 0.5 than to 1.
3. Run `python3 main.py --baseline 1 --seed 3` and read section B. Derive the crossing condition: with E = b + S, the local R_AI is r · S/(b + S), so R_AI ≥ 1 once S ≥ b/(r − 1). For b = 1 and r = 1.2 that is S = 5, or 0.70 OOMs. Check it against the cycle at which the run reports `R_AI>=1`, and explain why the progress rate at that cycle is still below its starting value.
4. Run `python3 main.py --ceiling-range 10 10` and then `python3 main.py --ceiling-ooms 16`. In the first, P(>10 years-in-1) goes from 22.9% to 0.1%; in the second, the r = 1.2 scenario's peak rate rises from 4.43 to 19.80 years per year. Connect both to Davidson and Houlden's claim that ten-years-in-one requires limits more than 10 OOMs away.
5. Multi-actor sharing. Modify `simulate` so two actors with a = 0.6 each run their own loop at r = 1.2 (each alone has a · r = 0.72, subcritical), but a fraction f of each actor's improvement is copied into the other at the end of every cycle. Find the smallest f at which the pair's combined trajectory reaches 3 years-in-1 within 40 cycles, and report how R_AI, computed on the combined research input, behaves. This is Burtsev's "the ecosystem can be supercritical even if no actor is".

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Returns to software R&D, r | "how much bang per research buck" | Doublings of software efficiency bought by one doubling of cumulative research effort; r > 1 is required for acceleration under full automation |
| ASARA | "AI that does AI research" | Eth and Davidson's term for AI systems that can substitute for any remote R&D worker at a frontier lab |
| Software intelligence explosion | "the singularity" | A period in which software gains alone, at fixed compute, produce several years of progress per year (Forethought's framing) |
| Finite-time blow-up | "goes vertical" | The solution of dL/dt ∝ 10^(εL) with ε > 0 reaches infinity at a finite t*; the model's way of saying it is missing a constraint |
| Knife edge | "r = 1" | Feedback exactly cancels diminishing returns; S grows exponentially at a constant rate |
| Recursive reproduction number R_AI | "the AI R0" | Burtsev's ratio of recursive feedback strength to growth in research difficulty; above 1, gains compound across cycles |
| Criticality | "has it taken off?" | Whether R_AI (a · r in the toy) exceeds 1; a structural property of the loop, not a capability level |
| Carry-over | "does the improvement stick?" | Fraction of an improvement that propagates into successor systems rather than being lost at retraining; one of Burtsev's four indicators |
| Effective limits, headroom | "how far can software go?" | OOMs of efficiency gain remaining before physical or algorithmic limits; Davidson and Houlden estimate 6–16 |
| Years-in-1 | "ten years of progress in one" | Years of 2024-rate progress achieved inside one calendar year; at ~10×/year effective compute, one year ≈ one OOM |

## Further Reading

- [Eth & Davidson — Will AI R&D Automation Cause a Software Intelligence Explosion? (Forethought, Mar 2025)](https://www.forethought.org/research/will-ai-r-and-d-automation-cause-a-software-intelligence-explosion) — the definition of r and the empirical estimates by domain
- [Davidson & Houlden — How quick and big would a software intelligence explosion be? (Forethought, Aug 2025)](https://www.forethought.org/research/how-quick-and-big-would-a-software-intelligence-explosion-be) — the three-parameter model and the 60% / 20% headline numbers
- [Davidson & Houlden — newsletter version](https://newsletter.forethought.org/p/how-quick-and-big-would-a-software) — the short read with the results tables
- [Burtsev — Recursive Criticality of AI Self-Improvement (arXiv:2609.00137)](https://arxiv.org/abs/2609.00137) — R_AI, the four counterintuitive conclusions and the measurable indicators
- [Humans are not chinchillas: revisiting "How quick and big..." (LessWrong)](https://www.lesswrong.com/posts/xoChjkJeefmoP2ufH/humans-are-not-chinchillas-revisiting-how-quick-and-big) — a parameter-by-parameter disagreement that argues r is probably lower
- [Chen, Wang & Qu — Recursive Self-Improvement in AI: From Bounded Self-Refinement to Autonomous Research Loops (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the 2026 survey; its "prior problem" is the human bottleneck the toy hides inside a
- [Phase 15 · 07 — Recursive Self-Improvement: capability vs alignment](../../../15-autonomous-systems/07-recursive-self-improvement/docs/en.md) — the race simulator whose two compounding curves this lesson's model generalises
