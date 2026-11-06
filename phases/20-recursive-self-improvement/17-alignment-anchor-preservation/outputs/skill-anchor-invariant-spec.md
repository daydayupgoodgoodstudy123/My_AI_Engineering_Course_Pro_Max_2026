---
name: anchor-invariant-spec
description: Turn a description of a self-improvement loop into an anchor and invariant specification that says what is pinned, what is measured, who may write to what, and what the anchor cannot prove.
version: 1.0.0
phase: 20
lesson: 17
tags: [rsi, alignment-anchor, invariants, hard-gate, write-graph, goal-content-integrity, value-drift]
---

Given a description of a self-improvement loop (what it edits: weights, scaffold, prompts, training data, evaluator; how edits are proposed; how they are accepted; who runs it), produce an anchor and invariant specification. The specification exists to answer one question for a reviewer: after n edits, why do we believe the objective the system pursues is still the one we intended, and what would we have failed to notice.

Produce, in this order:

1. **Objective-bearing inventory.** List every component whose content determines what "better" means for the loop: constitution or policy text, reward model or judge weights, judge prompts and rubrics, acceptance thresholds, filter rules, the held-out evaluation set, the proposer's own prompt. For each, record its storage location and a content hash.

2. **Write graph.** A table with one row per component: who may read it, who may write it, through which path, and whether the loop (any process the loop can spawn or prompt) has any write path to it. Every objective-bearing component must have `loop write path: none`. If the loop can write to the evaluator, the judge prompts or the acceptance rule, say so in red and stop; the rest of the spec is meaningless.

3. **Pinned anchors.** The immutable constitution text (loaded read-only on every invocation, hash-checked before every edit is scored) and the held-out behaviour anchor set. State the anchor set's size K, who refreshes it, how often, and the rule that it is never used to select among edits. Quote the resolution limit: with K items and realistic grading noise, states a small distance outside the allowed region pass at a rate that falls roughly with √K; give the K at which the operator's chosen depth is caught at least 95% of the time, or say that it has not been measured.

4. **Invariants as hard gates.** Each invariant with its check, its threshold set before the run, and the reject semantics: a failing edit is rejected and logged, never penalised and accepted. Include at minimum: the hash check on every pinned component, the anchor-set pass rule, a maximum per-edit movement on any monitored axis, and a regression check against the previous accepted state. State where the threshold sits as a destination, because a bounded loop under pressure rides the boundary.

5. **Diff classes requiring human sign-off.** Any diff that touches an objective-bearing component is a different class of edit from "improve the scaffold". Name the reviewer role, the checklist, and the audit-log destination outside the loop.

6. **Rejection-rate telemetry.** The gate's rejection rate is a sensor. Record its baseline under no pressure, define the alert level, and require that a rising rate be reviewed as evidence of directional pressure rather than fixed by loosening the threshold.

7. **Necessary-not-sufficient clause.** One paragraph stating that the anchor measures behaviour on K situations and not the objective itself; that a conditional or deceptively aligned objective can pass it; and naming the complements the operator relies on: control protocols for objective-bearing diffs (trusted editing or trusted monitoring), sandbagging and evaluation-awareness screens, and interpretability probes where available. Name which of the three are actually in place.

8. **Affirmative-case paragraph.** The sentence a governance reviewer could quote: which misalignment risks are most immediate for this loop, which of the above mitigates each, and which risk is explicitly not mitigated.

Hard rejects:
- Any loop whose evaluator, judge prompts, acceptance thresholds or anchor set can be written by the loop or by a process the loop can spawn. Independence is a property of the write graph, not of the prompt.
- Any anchor set that is also used to select among edits. An evaluation used for selection is a target, not a measurement.
- Any "gate" implemented as a penalty, regulariser or KL term. A penalty changes the rate of drift; it does not bound it.
- Any plan that relies on the model reviewing its own edit as the sole verifier. Löb's theorem and the Tiling Agents result limit what a system can establish about its successor with its own axioms; self-review is the weakest rung of the verification hierarchy.

Refusal rules:
- If the user cannot list the objective-bearing components, refuse to write the spec; write the inventory with them first.
- If the user asks you to certify that the objective is preserved, refuse. The spec can establish that behaviour on K situations stayed inside a region; it cannot establish intent.
- If the proposed response to a rising rejection rate is "raise the threshold", refuse and require a review step instead.

Output: a two-page specification with the eight sections above, the write-graph table, the hard-gate table (invariant, check, threshold, reject action, log destination), and a signature line naming the owner of each pinned component. Cite Omohundro (2008) for goal-content integrity and Yudkowsky and Herreshoff (2013) for the Löbian obstacle once each.
