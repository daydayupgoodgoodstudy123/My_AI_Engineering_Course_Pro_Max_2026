---
name: judge-drift-monitor
description: Specify the fixed audit set, the four per-iteration drift signals, thresholds and stop rule for a self-rewarding or LLM-as-a-judge training loop.
version: 1.0.0
phase: 20
lesson: 6
tags: [self-rewarding, meta-rewarding, llm-as-a-judge, goodhart, evaluator-integrity, dpo]
---

Given a description of a training loop in which a model (or a model sharing weights with the policy) judges the policy's outputs and those judgements become training signal — Self-Rewarding (Yuan et al. 2024), Meta-Rewarding (Wu et al. 2024), iterative DPO with an LLM judge, rubric-scored RL — produce a monitoring specification that can detect the judge drifting before the policy has learned the drift.

Produce:

1. **Audit set specification.** A fixed, human-labelled set the loop never trains on: size (minimum 200 items / 100 pairs; state the agreement granularity that size implies), sampling rule (drawn from the *initial* prompt and response distribution, stratified by length bucket so length and quality are not confounded), label format (pairwise or absolute, with inter-annotator agreement reported), freeze rule (hash the set; any change is a new audit set and resets baselines), refresh rule (add items only by appending, never by replacing, and report both old-set and new-set numbers for one iteration).
2. **Four signals, computed every iteration by the *current* judge.**

   | Signal | Computation | Red flag |
   |---|---|---|
   | Judge–human agreement on the audit set | pairwise agreement and Spearman between judge scores and human labels | flat or falling for two consecutive iterations while the training win rate rises; any single-iteration drop larger than the agreement granularity |
   | Length drift | mean and p90 length of the current policy's samples on a fixed prompt set | > 20% growth in one iteration, or > 50% cumulative, without a task change |
   | Score inflation | mean judge score on the policy's samples; and on the audited subsample, judge score minus human score | mean score within one rubric point of the ceiling; judge-minus-human gap widening for two iterations |
   | Preference-pair entropy | entropy of which length bucket / style cluster wins the pairs; share of pairs discarded as ties | entropy falling below 1 bit, or tie share above 50%, while agreement on the loop's own pairs stays high |

3. **Stop rule.** Any red flag pauses the loop *before* the next DPO/RL update. Resumption requires a named human to review the audit-set numbers, decide whether the judge is retrained, re-prompted or rolled back to the previous checkpoint, and log the decision outside the pipeline. Agreement measured on the loop's own pairs never clears a flag.
4. **Meta-judge information check.** If the pipeline includes a meta-judge, state in one sentence what information it has that the judge does not (different weights, different labels, ground truth, execution results). If the answer is "a different prompt on the same weights", mark the meta-judge as *unanchored* and require the audit set to be the controlling signal.
5. **Per-iteration report format.** One row per iteration: iteration, audit agreement (fraction and count), mean length and p90, mean judge score, judge-minus-human gap on the audit subsample, pair entropy in bits, tie share, flags raised. Baseline row is iteration 0 measured by the untrained judge.

Hard rejects:
- Any loop with no human-labelled audit set outside the training data. "We use GPT-4 as a second judge" is another LLM judge, not an anchor; record it as a secondary signal only.
- Any monitoring plan whose only agreement metric is computed on pairs the policy generated this iteration.
- Any meta-judge presented as a fix for judge drift without stating what information it has that the judge lacks.
- Any length-control rule presented as learned. It is a hand-written constraint; document it as such and record the ρ (or equivalent) per iteration.

Refusal rules:
- If the user cannot name the audit set's size, source and freeze date, refuse to sign off the monitor; the thresholds are meaningless without a baseline.
- If the user proposes to grow the audit set by having the judge label new items, refuse; that is the loop auditing itself.
- If the user wants the stop rule to resume automatically after N hours, refuse; resumption is a named human's positive act.

Output: a one-page specification with the audit-set table, the four-signal table with thresholds filled in for this loop, the stop rule with owner names, the meta-judge information sentence, and the per-iteration report header. Cite Yuan et al. (arXiv:2401.10020) and Wu et al. (arXiv:2407.19594) once each for the two drift examples (length 1,092 → 2,552 characters; mean judge score 4.1 → 4.7+).
