---
name: filter-quality-audit
description: Audit the filter of a generate-filter-train (STaR / ReST-EM / rejection-sampling) pipeline, place it on the verification hierarchy, compute the growth condition for named failure modes, and return a go / no-go with stop thresholds.
version: 1.0.0
phase: 20
lesson: 5
tags: [self-training, star, rest-em, rejection-sampling, verification-hierarchy, filter-precision, model-collapse]
---

Given a description of a self-training pipeline — what is generated, what filters it, what is trained on the survivors, what ground truth exists and who holds it — produce an audit that answers one question: **does the loop converge toward correct outputs or toward whatever the filter accepts?** The loop multiplies each output mode's probability by its acceptance rate a_s every iteration, so the audit is about acceptance rates, not about aggregate accuracy.

Produce:

1. **Hierarchy placement.** Place the filter on the verification hierarchy (Chen, Wang, Qu, arXiv:2607.07663): tier 1 formal verifier, tier 2 execution / tests / answer match, tier 3 judge / reward model / rubric, tier 4 intrinsic self-assessment. State the tier, the evidence (what the filter actually reads), and the tier's characteristic failure: formalization gaps (1), off-coverage leaks and saturation (2), judge bias and co-evolution (3), convergence to the most confident mode (4). A filter that is a model trained on the same data as the policy is tier 3 at best; a filter that is the policy itself is tier 4.

2. **Precision audit specification.** Define a per-iteration audit: a fixed number of accepted samples (200 unless the owner justifies another size) drawn uniformly from the kept set, labelled against ground truth that the loop cannot see or influence, reported as precision with a binomial confidence interval. Name the truth source, who holds it, and the cadence. State what the audit can and cannot detect at that sample size (200 samples resolve a 20-point contamination, not a 2-point one). Require that the audit set is never used for training and never used to tune the filter.

3. **Growth-condition analysis.** List the output modes the owner is worried about (shortcuts, format exploits, verbose padding, confident wrong answers, test-specific hacks). For each mode m and the intended correct mode, estimate the acceptance rate a_m from the audit sample (or from the filter's confusion matrix if one exists). Report log(a_m / a_correct). Any mode with a positive value grows next iteration regardless of aggregate accuracy. For a symmetric noisy filter state q and TPR and the rule "grows iff q > TPR"; for a biased filter report the extra leak b on the mode's plausible wrong outputs against b* = (TPR − q)(c_correct − c_m) / P(plausible wrong | m).

4. **Saturation and diversity check.** Report accepted-sample count and precision trend across iterations, entropy or distinct-solution count per iteration, and the share of training problems that have never produced an accepted sample. A rising accepted count with falling audit precision is the self-confirming-loop signature. Entropy collapse that outruns audit-measured accuracy gains is the sharpening-not-selecting signature. Name the anchors in use: fresh human data fraction, sampling temperature, retrain-from-base.

5. **Go / no-go with stop thresholds.** Return GO, GO-WITH-CONDITIONS or NO-GO. Attach numeric stop conditions that halt the next iteration automatically: minimum audit precision, maximum positive log(a_m / a_correct) for any listed mode, minimum entropy, maximum iteration-to-iteration drop in audit precision. Thresholds are set before the run and recorded outside the pipeline.

Hard rejects:

- Any pipeline whose only quality signal is the loop's own telemetry (accepted count, training loss, model confidence on its own outputs). These rise under a degenerating loop.
- Any tier 3 or tier 4 filter without a per-iteration audit against truth the filter did not produce. The loop then optimizes the judge, and there is no instrument that can tell.
- Any audit whose labelled sample is drawn from the training problems the model already solves, or whose labels were produced by the policy or the filter.
- Any pipeline that reports aggregate accuracy but cannot report acceptance rates per mode. Aggregate accuracy can rise for several iterations while a wrong mode's share grows.

Refusal rules:

- If the owner cannot name a ground-truth source independent of the policy and the filter, refuse to issue GO. Specify what truth would be needed and at what cadence.
- If the owner asks to raise the filter's acceptance threshold to "fix" a contamination finding without re-estimating per-mode acceptance rates, refuse: a stricter threshold on a biased filter concentrates the kept set on the mode the filter prefers.
- If the proposed stop conditions can be edited by the pipeline or by the agent that runs it, refuse until they are moved outside the loop.

Output: a one-page audit with (a) hierarchy tier and evidence, (b) audit specification table (sample size, truth source, holder, cadence, detectable contamination), (c) growth-condition table (mode, a_m, log(a_m / a_correct), verdict), (d) saturation and diversity readout, (e) decision with the stop thresholds and the name of the person who owns them. Cite STaR (arXiv:2203.14465), ReST-EM (arXiv:2312.06585) and Chen et al. (arXiv:2607.07663) once each where the relevant mechanism is invoked.
