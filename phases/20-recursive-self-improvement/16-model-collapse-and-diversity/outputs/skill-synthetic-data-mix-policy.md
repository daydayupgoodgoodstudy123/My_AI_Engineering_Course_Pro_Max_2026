---
name: synthetic-data-mix-policy
description: Write a provenance-tagged synthetic-data mix policy for a self-training loop — fraction cap, diversity dashboard, regeneration path — and refuse policies that cannot show the tail is alive.
version: 1.0.0
phase: 20
lesson: 16
tags: [model-collapse, synthetic-data, provenance, diversity, pass-at-k, self-training]
---

Given a description of a self-training or data-generation loop (data sources, generation procedure, filters or verifiers, training schedule, sample size per round, number of rounds planned), produce a mix policy that keeps the loop from collapsing onto its own output. The policy is a document the loop's operator signs before round 1, not a knob the loop adjusts for itself.

Produce:

1. **Provenance tag schema.** Every training example carries `source ∈ {real, synthetic}`, `generation` (0 for real; g for data produced by the round-g model), `filter` (name and version of the verifier or judge that admitted it, or `none`) and `origin_id` (a pointer to the real-data archive it was regenerated from, where one exists). Untagged data is treated as synthetic of unknown generation and counts against the cap.
2. **Regime statement.** Say which of replace / accumulate / mix the loop runs. "Replace" (train only on the latest synthetic round) is rejected outright (see hard rejects). For accumulate, state how the real data stays in the pool and how the pool is capped in size. For mix, state ρ, the fraction of fresh real data per round, and how it is enforced from the tags.
3. **Synthetic-fraction cap, with its measurement.** State the maximal synthetic share per round and the experiment that produced it: a sweep over ρ at the loop's own per-round sample size n and its own data distribution, measuring total variation (or a proxy) against a frozen real reference set over at least as many rounds as the loop will run. A number quoted from a paper is not a measurement; Seddik et al. (arXiv:2404.05090) show a maximal fraction exists, not what it is for your n.
4. **Diversity dashboard.** Four monitors, each with a baseline from round 0 and a stop condition:
   - Entropy of the output distribution on a fixed probe set (stop if it falls more than X% below baseline, operator sets X).
   - Newly-missing categories: items, classes, strategies or styles present in the real reference set that the current model has not produced in the last N samples (stop on any sustained loss in a protected category; report count every round).
   - Expected distinct at k, i.e. pass@k-style coverage on held-out prompts at a large k (stop if it falls while pass@1 rises — the sharpening signature).
   - Total variation, or a divergence proxy, between generated samples and the frozen real reference set (stop at the TV level that the cap sweep identified as collapse onset).
   Tail *mass* may be shown but must not be a stop condition on its own: it is preserved in expectation while the categories carrying it die.
5. **Regeneration path.** A procedure, tested at least once before round 1, that rebuilds the training pool from tagged real sources plus re-generation from a named earlier checkpoint. Name who can trigger it and how long it takes. "Irreversible" means no amount of prompting the collapsed model brings the tail back; only re-anchoring to real data does.

Hard rejects:
- Any loop whose next round trains only on the previous round's synthetic output with no real data in the pool and no fresh real fraction.
- Any cap stated without the sweep that produced it, or produced at a different n or a different data distribution than the loop actually uses.
- Any dashboard whose only tail indicator is a mass or share metric.
- Any pipeline in which the loop itself can edit the cap, the reference set or the stop conditions.
- Any reference set that is also used for training or for the verifier's own fine-tuning.

Refusal rules:
- If the operator cannot say how much real data exists and where it is archived, refuse: without a real archive there is no regeneration path and no accumulate regime, only replace with delay.
- If the filter or judge is the same model that generates the data and there is no independent diversity monitor, refuse: judge-induced style collapse (Lesson 06) is invisible to the judge.
- If the planned number of rounds exceeds the number of rounds the cap sweep ran, refuse until the sweep is extended; collapse accelerates late and bounds proven at round 20 say nothing about round 50.

Output format:

Return a two-page policy:
- **Tag schema** (table: field, allowed values, who writes it)
- **Regime and real-data pool** (regime; pool size; ρ or accumulate rule)
- **Synthetic-fraction cap** (value; the sweep: n, ρ values tried, rounds, metric, onset level)
- **Dashboard** (table: monitor, baseline, stop condition, owner)
- **Regeneration procedure** (steps, trigger authority, tested-on date)
- **Signature line** (who owns the cap and the stop conditions)

Cite Shumailov et al. (Nature 631:755–759, 2024) for the mechanism, Gerstgrasser et al. (arXiv:2404.01413) for accumulate and Seddik et al. (arXiv:2404.05090) for the maximal fraction, once each.
