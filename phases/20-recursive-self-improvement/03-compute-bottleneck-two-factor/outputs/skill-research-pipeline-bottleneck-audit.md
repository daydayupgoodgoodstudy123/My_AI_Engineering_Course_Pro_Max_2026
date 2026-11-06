---
name: research-pipeline-bottleneck-audit
description: Audit a claimed AI research speedup by decomposing the pipeline into stages, computing the Amdahl ceiling, and checking whether the claim's compute assumption is explicit.
version: 1.0.0
phase: 20
lesson: 3
tags: [compute-bottleneck, amdahl, takeoff, ai-rnd-automation, research-pipeline, two-factor]
---

Given a claim that AI is speeding up (or will speed up) AI research by some factor (a forecast such as AI 2027 or Forethought, a lab statement such as "our internal research is X times faster", an internal plan to deploy N agent copies, or a governance threshold such as RSP AI R&D-4), produce a one-page bottleneck audit that says what the claimed number can and cannot mean.

Produce:

1. **Pipeline decomposition.** Split one research cycle into stages (default: ideation, coding, experiment compute, evaluation, decision) and assign each a share of baseline wall-clock `f_i` (sum to 1). Mark each stage `labour` (AI copies can speed it up) or `compute` (needs accelerator time). State where the shares come from: measured, estimated, or copied from the lesson defaults. If a human sign-off stage exists, list it separately with multiplier 1.
2. **Amdahl ceiling.** Compute `speedup(k) = 1 / sum_i f_i / m_i` with `m_i = k` for labour stages and `m_i = g` for the compute stage. Report the software-only ceiling `1 / f_compute` (g = 1), the compute-inclusive ceiling `g / f_compute`, the speedup at the claim's implied k, and the k that reaches 95% of the ceiling. Run `code/main.py --compute-fraction <f_compute> --automation <k> --compute-growth <g>` to get the numbers rather than estimating by eye.
3. **Serial-vs-parallel check.** If the claim is about agent copies (N agents), compute the pool knee `N_knee = (C / E) x single-agent cycle time` for the stated or assumed GPU pool C and experiment duration E. State whether N is below or above the knee. Above the knee, translate "N agents" into "the pool's ceiling plus a queue" and report the per-copy cycle time inflation.
4. **Compute-assumption classification.** Classify the claim as one of:
   - `software-only` (compute explicitly held fixed; e.g. AI 2027's takeoff math "assuming no increases in training compute", Forethought's SIE model);
   - `compute-inclusive` (the yardstick already contains compute growth; e.g. RSP v3.1's "compress two years of 2018-2024 AI progress into a single year");
   - `ambiguous` (the claim gives a multiplier without saying which factor moved).
   For `ambiguous`, write the two readings side by side and say which one the Amdahl ceiling makes plausible.
5. **Escape hatches named.** List which bottleneck escapes the claim relies on, explicitly or implicitly: smaller-scale experiments (lower `f_compute`, extrapolation risk), better experiment design (fewer experiments per decision), compute reallocation from deployment to research, or hardware growth. For each, say what evidence would show it is actually happening.
6. **Observability note.** State what part of the claimed speedup would be visible to an outside party (compute purchases, power, training-run count) and what part would not (algorithmic gains). This feeds Lesson 21's governance analysis.

Hard rejects:
- Any audit that reports a speedup without a compute fraction. "Agents are 30x faster" with no `f_compute` is a labour-stage statement, not a pipeline statement.
- Any claim that N agent copies deliver N times the experiments when N exceeds the pool knee. Throughput above the knee is the pool ceiling, full stop.
- Any comparison of a software-only forecast against a compute-inclusive threshold (or vice versa) without saying so. The two yardsticks differ by the compute-growth factor of the period.
- Any audit that treats company-reported internal speedups (e.g. Anthropic's August 2026 "faster but not yet 2x", as reported by secondary sources) as measured external facts. Label the source class.

Refusal rules:
- If the claimant cannot say whether experiment compute is included in the cycle they measured, refuse to assign a ceiling and return the decomposition template instead. A ceiling computed on a guessed `f_compute` is a rationalisation.
- If the pipeline has no experiment-compute stage at all (pure theory or pure engineering tasks), say the Amdahl framing does not apply and do not force one.
- If the request is to "show the speedup is unbounded", refuse: with any fixed stage the speedup is bounded by 1 over that stage's share.

Output format (one page):
- **Stage table** (stage | share | kind | multiplier used)
- **Ceilings** (software-only | compute-inclusive | at claimed k | k for 95%)
- **Queue knee** (C, E, N_knee, where N sits, per-copy cycle inflation)
- **Classification** (software-only | compute-inclusive | ambiguous, with the one-sentence reason)
- **Escape hatches and evidence**
- **Observability** (visible | invisible)
- **Source classes** (primary paper | company-reported | press | this audit's assumption)
