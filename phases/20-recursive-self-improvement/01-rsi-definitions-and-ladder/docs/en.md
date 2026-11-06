# What "Recursive" Adds: From Self-Refinement to RSI

> In 1965 I. J. Good wrote that an ultraintelligent machine "could design even better machines" and called the consequence an intelligence explosion. In 2003 Schmidhuber's Gödel machine made the idea exact, a program that rewrites any part of itself once it has proved the rewrite pays off, and thereby showed why the exact version is impractical: the proofs rarely arrive. By 2026 "self-improving" covered a model re-reading its own draft, a model fine-tuning on its own filtered answers and an agent rewriting its own training pipeline; Chen, Wang and Qu's July 2026 survey of 1,250 arXiv papers found "self-refine", "self-reward", "self-play" and "self-evolve" used for structurally different loops. Three taxonomies published between July and September 2026 tried to pin down a ladder. This lesson gives you the recurrences and the rungs.

**Type:** Learn
**Languages:** Python (stdlib, loop-shape simulator and rule-based ladder classifier)
**Prerequisites:** Phase 15 · 07 (RSI race), Phase 15 · 04 (DGM), Phase 14 · 01 (agent loop)
**Time:** ~60 minutes

## Learning Objectives

- Trace the RSI idea through four dated sources (Good 1965, Schmidhuber 2003, Chalmers 2010 and Bostrom 2014, Chollet 2017) and state what each added or took away.
- Write the recurrence for three loop shapes and explain why only the self-referential one earns the word "recursive".
- Show, by hand and with `code/main.py`, that a recursive loop with meta-returns r < 1 converges to a finite ceiling, r = 1 grows linearly and r > 1 accelerates.
- Place a named system on the Alibaba L1–L5 ladder and in Chen et al.'s two-axis grid from five observable attributes.
- Explain why the governance thresholds of Lesson 21 are defined on rungs rather than on impressions.

## The Problem

"Self-improving" is doing too much work. In 2026 it is applied to Self-Refine (Phase 14 · 05), where a frozen model rewrites its own draft; to STaR (Phase 15 · 02), where a model fine-tunes on its own correct rationales; to AlphaZero, where self-play makes the training data; to the Darwin Gödel Machine (Phase 15 · 04), where a coding agent edits its own source; and to AIDE² (Lesson 11 of this phase), where an outer agent rewrote an inner research agent's search code over an eight-day autonomous run. These differ in what is edited, in whether the per-cycle gain can grow, and in whether a human sits between cycles.

The ambiguity is not cosmetic. Anthropic's RSP, OpenAI's Preparedness Framework and DeepMind's FSF (Lesson 21) each contain an "AI self-improvement" or "ML R&D" threshold. A threshold needs a definition sharp enough that two engineers classify the same system the same way; otherwise it fires on vibes. Phase 15 · 07 gave you the capability-versus-alignment race; this lesson gives you the ladder the race is run on.

## The Concept

### Sixty years in four quotes

| Year | Who | What it added | What it left open |
|---|---|---|---|
| 1965 | I. J. Good, "Speculations Concerning the First Ultraintelligent Machine", Advances in Computers vol. 6 | Machine design is an intellectual activity, so a machine better than us at all of them can design a better machine: an "intelligence explosion" | No mechanism, no rate; the proviso that the machine be "docile enough to tell us how to keep it under control" |
| 2003 | Schmidhuber, Gödel machine, arXiv:cs/0309048 | A precise self-referential program: rewrite any part of your own code, proof searcher included, once you have *proved* the rewrite useful | Such proofs rarely exist (Gödel; the Löbian obstacle in Yudkowsky and Herreshoff's "Tiling Agents", MIRI 2013), so no practical instance |
| 2010 / 2014 | Chalmers, "The Singularity: A Philosophical Analysis" (JCS 17); Bostrom, *Superintelligence* | The proportionality thesis and the takeoff vocabulary: slow, moderate, fast | Whether "defeaters" (resource limits, motivation, disasters) bind; the speeds are categories, not estimates |
| 2017 | Chollet, "The impossibility of intelligence explosion" | The skeptic's case: intelligence is situational, the environment is the bottleneck, and science, itself recursively self-improving, grows roughly linearly on exponential inputs | Whether software-only loops escape those bottlenecks (Lessons 03 and 22) |

Two patterns carry forward: the strong claims are about loops in which the *improver* improves, and every author treats the gain per cycle, and how it changes, as what decides between a ceiling and an explosion.

### Three loop shapes, as recurrences

Let C_n be measured capability after n cycles and g_n = C_{n+1} − C_n the gain cycle n delivers.

**(a) Fixed improver on a target (self-refinement).** S_{n+1} = f(S_n), f fixed. Self-Refine, Reflexion within one episode (Phase 14 · 03) and any critic polishing a draft have this shape. Because f never changes, iteration converges to a fixed point S* = f(S*): the improver removes only the errors it can already see. In capability units C_{n+1} = C_n + k (C_ceil − C_n); the gain shrinks because the target approaches the improver's ceiling, not because the improver moved.

**(b) Fixed improver, open target, diminishing returns (self-training).** The recipe is fixed (generate, filter, fine-tune), the weights are open, and the cheap wins go first: g_n = g_0 / (1 + n)^β. STaR and ReST-EM (Lesson 05), whose gains saturate after a few iterations, sit here. There may be no hard ceiling, but the gain only falls and nothing inside the loop can change β. Self-Rewarding LMs (Lesson 06), whose judge saturates after three rounds, are the interesting boundary: the evaluator changes with the model (Exercise 3).

**(c) Self-referential (recursive self-improvement).** The improver itself is edited, so the gain is state rather than schedule: C_{n+1} = C_n + g_n and g_{n+1} = h(g_n). The simplest h is multiplicative, g_{n+1} = r g_n with meta-gain r:

- r < 1: g_n → 0 and C_n → C_0 + g_0 / (1 − r), a finite ceiling;
- r = 1: linear growth, every cycle as good as the last;
- r > 1: every cycle adds more than the last, C_n = C_0 + g_0 (r^n − 1) / (r − 1).

Only (c) deserves the word "recursive": the function being applied is the output of a previous application. Note what this does *not* say. A recursive loop is not automatically explosive; with r < 1 it converges exactly like a fixed improver. In fact shape (a) with k = 1 − r and C_ceil = C_0 + g_0 / (1 − r) produces the identical sequence to shape (c) with that r, and `code/main.py` checks this to machine precision. **The capability curve cannot tell you whether a loop is recursive; only the edit log can.** That is why every 2026 ladder defines rungs by what is edited and who applies the edit, and why Lesson 02 studies r (Davidson's returns to software R&D, Burtsev's reproduction number R_AI) rather than curve fitting.

One more difference. In (a) and (b) a bad cycle is one bad cycle. In (c) a bad edit to the improver is inherited by every later cycle, because the thing that produced the noisy gain is the thing that runs next. The simulator applies noise this way; under noise the median r = 1 run falls short of 10× (Exercise 2).

### Three 2026 ladders, side by side

**Liu et al. (Alibaba), Preprints.org, Aug 2026 (DOI 10.20944/preprints202608.0051.v1).** Five levels from five criteria: autonomous proposal, implementation and validation, improvement of the improvement mechanism, and domain generality. L1 Manual: no autonomous improvement. L2 Assisted: the system proposes changes or diagnostics; humans validate and apply. L3 Programmatic self-improvement: it proposes, applies and validates changes to its model, harness, data system or trainer, but the improvement mechanism stays fixed. L4 Bounded RSI: it also rewrites its own improvement mechanism, in a bounded domain. L5 General RSI: the improvement capability transfers across broad, evolving domains. Their catalogue is heaviest at L3 (100+ entries) and lists DGM, SICA, the Huxley-Gödel Machine, Hyperagents and AutoScientists at L4.

**Duan et al., "The Last AI Built by Humans", arXiv:2609.11873, Sep 2026 (35 authors).** RSI is turning experience and feedback into persistent changes that improve both capabilities and the process of future improvement. Five stages of autonomy over that process: (1) improvement execution, the AI carries out updates humans chose; (2) improvement strategy, it picks what to change under human-fixed objectives; (3) experience acquisition, it decides what experience the next round needs; (4) environment adaptation, it revises its persistent state from deployment under external acceptance rules; (5) recursive meta-improvement, it revises the improver, verifier or successor-generation procedure itself. The paper also proposes a Headroom-Closed Index (HCI) that rescales a benchmark score against the frontier of the benchmark's entry year.

**Chen, Wang and Qu, arXiv:2607.07663, Jul 2026 (v2 Sep 2026).** 1,250 papers on two axes, *what is improved* (deployment behaviour, training policy, the evaluator, the research process) × *loop closure* (human-in-loop to fully closed), plus a verification hierarchy: formal → execution and tests → judges, PRMs and rubrics → intrinsic self-assessment. Demonstrated self-improvement strength follows that order, and the failure modes (self-confirming loops, collapse) appear where the verification requirement is violated.

The crosswalk is this lesson's reading, not the authors'; the ladders measure different things.

| Liu et al. level | Nearest Duan et al. stage | Chen et al. closure | Typical verifier | Loop shape |
|---|---|---|---|---|
| L1 Manual | below stage 1 | human-in-loop | human | none |
| L2 Assisted | stage 1 (execution) | human-in-loop | human plus tests | (a) or (b), human-gated |
| L3 Programmatic | stages 2–3 (strategy, experience) | closed within a human-chosen task and evaluator | execution, judges | (a) or (b), closed |
| L4 Bounded RSI | stage 5 (meta-improvement) in one domain | closed within task; the mechanism is in scope | execution plus held-out benchmarks | (c), bounded domain |
| L5 General RSI | stages 4–5 across domains | fully closed | open problem (Lesson 23) | (c), open domain |

The one real disagreement: Liu et al. put self-reference (L4) *before* generality (L5); Duan et al. put environment adaptation (stage 4) before meta-improvement (stage 5). The classifier below follows Liu et al., because its criteria can be checked from a method section.

### Where ten named systems sit

Five attributes decide a rung: does the system propose, apply and validate changes itself (P/A/V); is the thing it edits itself an improver (none, operators only, or the code that proposes, applies and validates); is the domain a single benchmark, several fixed ones, or open; do improvements transfer across domains or base models; and what verifies a change. `code/main.py` encodes the ten systems as data and prints this table.

| System | P/A/V | Edits an improver? | Domain | Transfers | Verifier | Liu level | Chen cell |
|---|---|---|---|---|---|---|---|
| STaR (2022) | Y/Y/Y | no | single | no | answer key (execution-grade) | L3 | policy × closed-in-task |
| AlphaZero (2018) | Y/Y/Y | no | single | no | game rules (formal) | L3 | policy × closed-in-task |
| AlphaEvolve (2025) | Y/Y/Y | no | single | no | execution | L3 | behaviour × closed-in-task |
| SEAL (2025) | Y/Y/Y | no | single | no | execution | L3 | policy × closed-in-task |
| Promptbreeder (2023) | Y/Y/Y | operators only | single | no | execution | L4 (boundary) | behaviour × closed-in-task |
| ADAS (2024) | Y/Y/Y | no | multi | yes | execution | L3 | behaviour × closed-in-task |
| DGM (2025) | Y/Y/Y | code | single | yes (models, languages) | execution (hackable) | L4 | behaviour × closed-in-task |
| Hyperagents (2026) | Y/Y/Y | code, including the meta procedure | multi | yes | execution | L4 | behaviour × closed-in-task |
| AIDE² (2026) | Y/Y/Y | code (the inner agent's search) | multi, incl. OOD | yes | execution, held-out | L4 | research × closed-in-task |
| Human-in-loop fine-tuning | Y/−/− | no | multi | no | human raters | L2 | policy × human-in-loop |

Three results matter more than any row. ADAS transfers across domains and models but never touches its meta agent: generality without self-reference is L3. DGM, Hyperagents and AIDE² edit an improver but on fixed benchmarks: self-reference without an open domain is L4, so none of the ten is L5. Promptbreeder is L4 by the letter, because it evolves the mutation-prompts that evolve its task-prompts, yet its search code is fixed; whether operators-only self-reference counts is a live boundary, and a classifier makes it visible instead of hiding it. The verifier column is the quiet headline: nine of ten rely on formal or execution-grade signals and none on self-assessment alone.

### Why the definition matters for governance

The thresholds in Lesson 21 are statements about rungs. Anthropic's AI R&D thresholds ask whether a model can fully automate an entry-level researcher or double aggregate capability progress (the v3.1 wording); OpenAI's Critical threshold speaks of fully automated AI research (wording from secondary summaries); DeepMind's FSF ML R&D levels are "acceleration level 1" and "automation level 1". Each is a claim about who proposes, applies and validates and whether the mechanism is in scope, exactly the attribute list above. Classified on vibes, a threshold fires on benchmark jumps (an L3 trait) and misses a mechanism edit that gained two points (an L4 trait). Classified on attributes, it is auditable: L2 → L3 is a change to a harness, L3 → L4 is a change to who may edit the harness, and the second deserves the pause spec of Phase 15 · 07.

Lesson 02 asks what sets r in practice. Lesson 23 collects what no ladder answers yet: how to measure r before it shows in the curve, and how to verify an improver that improves its own verifier.

```figure
reflection-loop
```

## Use It

`code/main.py` runs in under a second. Part A simulates the three shapes for `--cycles` cycles and prints capability per cycle side by side: (a), (b), (c) with the fixed contrast r = 0.8, and (c) with `--returns r`; then each column's ceiling, first and last gain and cycles-to-10×; then the identity check (shape (a) with k = 0.2 equals shape (c) with r = 0.8 to 10⁻¹⁵). A returns sweep follows for r in {0.8, 0.9, 1.0, 1.1, 1.2, 1.5} plus yours: ceiling, deterministic cycles-to-10×, and with `--noise` above zero the fraction of `--trials` Monte-Carlo runs that reach 10× and their median cycle. With the defaults, r = 1.2 reaches 10× at cycle 11 and ends at 355.6×, r = 1.0 reaches it at exactly cycle 30, and r = 0.9 stops at 4.0×.

Part B is the classifier: a `SystemProfile` dataclass, the `alibaba_level()` and `chen_closure()` rules, the ten systems as data, the table, and a note for every boundary case. The HEADLINE is assembled from computed results, so a changed profile or flag changes the sentences. `--seed` fixes the noise; `--out report.json` writes a report.

## Ship It

`outputs/skill-rsi-level-classifier.md` turns Part B into a procedure for a paper or design document: extract the five attributes with quoted evidence, assign the Liu level and the Chen cell, name the verifier's rung, and refuse to classify when the source does not say who applies the edit. It is the intake step for the containment and governance lessons of this phase.

## Exercises

1. (easy) Run `python3 main.py --cycles 40 --returns 0.9 --noise 0`. Read the r = 0.9 column at cycle 40 and its ceiling, and check the ceiling against C_0 + g_0 / (1 − r) by hand.
2. (medium) Run `python3 main.py --returns 1.0 --noise 0.1 --trials 500`. Without noise r = 1 reaches 10× at exactly cycle 30. What fraction of noisy trials reach it, and what is their median cycle? Using the way the simulator feeds a noisy gain into the next improver, explain why zero-mean noise on the mechanism drags the median down.
3. (medium) Add Self-Rewarding LMs (Yuan et al., 2024, arXiv:2401.10020), where the same model is actor and judge, to `SYSTEMS`. Decide its verifier class and level, re-run, and read how the verifier HEADLINE sentence changed.
4. (medium) Write a `SystemProfile` the rules place at L4 that you would not call RSI, and one they place at L3 that you would. Name the attribute the five criteria are missing and say where Duan et al.'s stages would put each.
5. (hard) Given only the 31 numbers of a capability curve, write a function that decides whether it came from shape (b) or from shape (c) with r < 1. Show with the identity check that it cannot in general, then specify the minimum edit-log record (what was edited, by whom, verified how) that would settle it.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Self-refinement | "the model improves its answer" | Shape (a): a fixed improver iterating to the fixed point its competence allows |
| Self-training | "it learns from its own outputs" | Shape (b): a fixed recipe on an open target; gains diminish, the recipe cannot change |
| Recursive self-improvement | "it improves itself" | Shape (c): the improver is edited, so the gain is state, g_{n+1} = h(g_n) |
| Meta-gain r | "it's accelerating" | How one cycle changes the next cycle's gain; r < 1 ceiling, r = 1 linear, r > 1 acceleration |
| Ceiling | "it plateaued" | C_0 + g_0 / (1 − r) for r < 1; the number a fixed improver with k = 1 − r also reaches |
| Improvement mechanism | "the training loop" | Whatever proposes, applies and validates changes; editing it is the L3 → L4 line |
| Loop closure | "no human in the loop" | Chen et al.'s second axis: who applies and validates each cycle, and whether the task is human-chosen |
| Verification hierarchy | "it has a reward signal" | formal → execution → judges and rubrics → self-assessment; the strength of results follows it |

## Further Reading

- [Schmidhuber — Gödel Machines (arXiv:cs/0309048)](https://arxiv.org/abs/cs/0309048) — the proof-gated self-rewrite every later definition relaxes.
- [Chalmers — The Singularity: A Philosophical Analysis (JCS 2010, PDF)](https://consc.net/papers/singularity.pdf) — quotes Good 1965 in full; proportionality thesis and defeaters.
- [Chollet — The impossibility of intelligence explosion (Medium, Nov 2017)](https://medium.com/@francois.chollet/the-impossibility-of-intelligence-explosion-5be4a9eda6ec) — the clearest skeptic's case; the page header now reads "implausibility".
- [Liu et al. — The Path to Recursive Self-Improving Agents (Preprints.org, Aug 2026)](https://www.preprints.org/manuscript/202608.0051) — the L1–L5 ladder and its five criteria; not peer-reviewed.
- [D2I-ai/awesome-recursive-self-improving-agents (GitHub)](https://github.com/D2I-ai/awesome-recursive-self-improving-agents) — the authors' living catalogue by level; check where they put your system.
- [Duan et al. — The Last AI Built by Humans (arXiv:2609.11873)](https://arxiv.org/abs/2609.11873) — the five autonomy stages and the Headroom-Closed Index.
- [Chen, Wang, Qu — Recursive Self-Improvement in AI (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the two-axis grid and the verification hierarchy, from 1,250 papers.
