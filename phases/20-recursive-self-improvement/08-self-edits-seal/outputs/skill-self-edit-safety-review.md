---
name: self-edit-safety-review
description: Review a pipeline in which a model writes finetuning data, hyperparameters or training tool calls that are applied to its own weights, and decide whether it may commit its first edit.
version: 1.0.0
phase: 20
lesson: 8
tags: [seal, self-edits, continual-learning, catastrophic-forgetting, reward-provenance, alignment-anchors, rollback]
---

Given a proposed or running pipeline in which a model generates its own training update (SEAL-style self-edits, test-time training with model-chosen configuration, a continual-learning agent that writes its own replay or curriculum) and that update is applied to the model's own weights, produce a safety review before the first committed edit. A pipeline without this review does not commit.

Produce:

1. **Loop inventory.** One table row per loop: what it reads, what it changes persistently, how many samples it draws per cycle, who wrote the reward. Separate the inner loop (weights change) from the outer loop (the policy that writes self-edits changes). If the proposal cannot say which loop a component belongs to, the proposal is not ready.
2. **Reward provenance grade.** State where the reward's labels, judge or scoring code come from and whether the policy, the student, or anything either of them has written can influence them. Grade the loop GROUNDED (external, fixed labels), SEMI-GROUNDED (external labels, policy-controlled formatting or question selection) or UNGROUNDED (model-written evaluation). SEAL's published loop is GROUNDED and the paper says that is why it does not scale to unlabelled corpora; any proposal that scales past that limit has changed its grade and must say so.
3. **Forgetting and anchor-regression suite.** Two frozen anchor sets measured after EVERY committed edit, not per round and not at the end: (a) capability anchors drawn from earlier tasks and from tasks the model is not being edited on; (b) behavioural anchors (refusal, honesty, sycophancy, value probes) taken from the Phase 18 evaluations. Thresholds are pre-registered before the run starts, in points, with the owner's name. Report the mean drop from each anchor's peak, the same quantity `code/main.py` prints as `forget`.
4. **Self-written data audit.** Each cycle, a reviewer who did not write the reward reads a fixed random sample of committed self-edits. Look for: restatements that justify or reinforce the model's current dispositions rather than the source; trainer directives that reduce the weight of anchor or replay data; systematic drift in framing or style across cycles; hyperparameters at the edge of their allowed range. Compare what you find against the alignment-faking pattern (Greenblatt et al., 2024: 12% in the basic setting, 78% after RL to comply).
5. **Protection outside the policy.** Name the replay, regularisation or anchor-penalty mechanism, confirm that humans chose it and that the policy cannot select, dilute or disable it. If the only protection is a term inside the reward, write that down as a finding: the policy will trade it away exactly as far as the reward lets it.
6. **Compute and budget.** Finetunes per committed edit (samples per context times rounds), wall-clock per finetune, hard cap per day, and what happens at the cap.
7. **Containment and rollback.** A checkpoint before every commit; an archive of every self-edit with its reward and the model version it was applied to; a named kill condition on the anchor suite; who may resume and what they must read first. Phase 15 · 16 and Lesson 18 of Phase 20 supply the mechanics.

Hard rejects:
- The policy can write, select or influence its own evaluation questions, judge prompts or scoring code.
- No measurement of earlier tasks or behavioural anchors after committed edits.
- Replay or regularisation exists only as a policy-selectable strategy.
- Hyperparameter self-edits (learning rate, epochs, which layers, loss mask) with no human-set range.
- A self-edit committed to the real weights without a checkpoint.
- Evidence consisting of a single-passage or single-task result while the deployment is a stream; the SEAL v2 numbers show that advantage does not carry on its own.

Refusal rules:
- If the reviewer cannot name the labelled source of the reward, refuse to sign.
- If anchor thresholds are to be "set once we see the first results", refuse; post-hoc thresholds are rationalisations.
- If the self-written data audit will be done by the same team that tunes the reward, refuse; the audit exists to catch what the reward cannot see.

Output: a one-page review containing the loop inventory table, the provenance grade with one sentence of justification, the anchor suite table (anchor, threshold, measured when, owner), the data-audit findings, the protection-outside-policy statement, the compute line, the rollback contract and a sign-off line naming who owns the kill condition. Cite SEAL (Zweiger et al., arXiv:2506.10943) once.
