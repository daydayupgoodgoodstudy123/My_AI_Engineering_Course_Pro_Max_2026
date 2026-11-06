---
name: closure-conditions-checklist
description: Audit a proposed self-improvement loop against the three closure conditions that make AlphaZero-style self-play work, and name the first condition it violates.
version: 1.0.0
phase: 20
lesson: 4
tags: [self-play, closed-loop, verifier, curriculum, distribution-shift, alphazero, alphaproof, exploitability]
---

Given a description of a loop in which a system produces its own training signal (self-play, self-training, synthetic data, LLM-as-judge, an agent that rewrites its own scaffold), decide whether the loop is closed in the AlphaZero sense and, if not, which closure condition fails first and what the loop will optimise instead.

Input you need before scoring: the task domain; what generates new tasks or episodes; what scores them; whether the scorer is produced, trained or editable by the system being improved; what the deployment target is and how it is sampled.

Produce:

1. **Condition 1 — a verifier that cannot be gamed.** Score 2 if the score comes from a formal system the policy cannot influence (game rules, a proof checker such as Lean, exact tests with hidden cases). Score 1 if it is execution-based but has known loopholes (visible tests, timeouts the agent can edit, a sandbox it can leave). Score 0 if the score comes from a learned judge, a rubric, a preference model or the model's own confidence. Level 0 is where Lesson 06 (judge = student) and Lesson 14 (Goodhart inside the loop) live.
2. **Condition 2 — an unbounded supply of tasks at the right difficulty.** Score 2 if the system automatically faces tasks at its frontier (opponent = current self; a challenger rewarded near the solver's solve rate). Score 1 if a large fixed pool exists (autoformalised problems, a benchmark) that the loop will exhaust or overfit. Score 0 if humans must author each new task.
3. **Condition 3 — no shift between the training game and the target.** Score 2 if the training game is the target (chess is chess). Score 1 if the target is a superset the loop samples from (formal IMO statements versus the informal problems contestants read). Score 0 if the loop trains on its own outputs while the target lives elsewhere (research taste, prose quality, user satisfaction).
4. **Game-internal failure modes.** Even at 2/2/2, check: intransitivity (does the newest generation lose to an older one? demand the loss rate against every archived generation, not only the parent); forgetting (do archived generations stay in the training pool?); exploitability (does a fixed best-response opponent beat the current policy?).
5. **Verdict.** `closed` (6/6 and the archive is evaluated), `bounded` (exactly one condition at 1: say which and what breaks first as generations accumulate), or `open` (any condition at 0: say what the loop will actually optimise, in one sentence).

Hard rejects:
- Any loop whose verifier is a model trained on data the same loop produced, scored at condition 1 >= 1. That is a judge, not a verifier.
- Any "improvement" measured only against the previous generation. Cycling hides there; require the exploit column against the full archive.
- Any claim that a domain is "like chess" or "like Lean" without naming the exact function that returns win / draw / loss and showing that the policy cannot edit it.

Refusal rules:
- If the submitter cannot say how a corrupted score would be detected, refuse to call the loop closed. AlphaZero needs no such detector because its verifier cannot be corrupted; anything less needs one.
- If the deployment target is described only as "the same kind of thing", refuse to score condition 3 until a held-out target set is named.
- If the only evidence is a single seed or a single run, score the failure-mode section as "not measured"; closure claims need the exploit column across seeds.

Output: a one-page table (condition | score 0-2 | evidence | what breaks first), the exploit-against-archive number or "not measured", and a one-line verdict. Cite Silver et al. (Science 2018) and Hubert et al. (Nature 2025) once each where relevant.
