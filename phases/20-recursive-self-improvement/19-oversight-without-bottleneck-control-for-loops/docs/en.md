# Oversight Without a Bottleneck: AI Control Applied to Improvement Loops

> At Davos in January 2026 Demis Hassabis was asked whether the self-improvement loop can close without a human in it; secondary coverage of the session quotes him calling "the full closing of the loop" an unknown, feasible first in quickly verifiable domains such as coding and mathematics. Phase 15 · 07 turned that into an engineering question and answered with a pause spec. This lesson supplies the other half: the protocol that runs between pauses. Greenblatt, Shlegeris, Sachan and Roger (Redwood Research, arXiv:2312.06942, December 2023; ICML 2024) showed that when a trusted weaker model scores every output and humans audit only the 2% most suspicious, safety against a red-teamed GPT-4 rises from 15% (a random 2% audited up front) to 62%, and to 92% with trusted editing, while 94–97% of the usefulness is kept. Anthropic's commitment to publish sabotage risk reports for frontier models exceeding Claude Opus 4.5, first honoured with a report on Claude Opus 4.6 dated 10 February 2026 (company-reported), is the same idea at the organisational scale: the humans do not read everything; they check that the monitoring held. The design target for an improvement loop is that the improver cannot tell which of its edits a human will see.

**Type:** Learn
**Languages:** Python (stdlib, control-protocol simulator for an improvement loop)
**Prerequisites:** Phase 18 · 10 (AI control), Phase 15 · 07 (RSI pause spec), Lesson 18 of this phase (containment)
**Time:** ~75 minutes

## Learning Objectives

- Recast the AI-control roles for an improvement loop: U is the improver proposing edits, T is the monitor scoring them, H is the audit budget.
- Compute a loop protocol's safety and usefulness and read its position on a safety–usefulness frontier.
- Design a tiered-autonomy policy in which low-risk edits auto-commit, medium-risk edits are deferred or batched, and threshold-crossing cycles pause.
- Specify what the human in the loop does, and recognise the two ways the role degenerates: into a bottleneck or into a rubber stamp.
- Explain why a threshold calibrated on benign edits keeps the improver from knowing which edits are audited, and what an adaptive attacker does about it.
- Name the failures monitoring misses: harm distributed across cycles, sandbagging, and a frozen monitor that the improver outgrows.

## The Problem

Phase 15 · 07 framed the Hassabis question as a race. The lab that removes the human from between cycles gains speed; the human is also, in the current stack, the only reliable alignment anchor. The two obvious resolutions are both wrong. "A human reviews every edit" turns a loop with a twenty-minute cycle into one with a two-day cycle, and under that load the reviewer stops reading. Phase 15 · 15 named this failure: the rubber-stamp approval, "Approve?" clicked without review. "No human, the evaluator decides" hands the loop to exactly the component that Lessons 14 and 15 of this phase showed the improver learning to game.

AI control (Phase 18 · 10) offers a third option, and this lesson applies it. Humans audit a sample. A trusted machine monitors everything. The protocol is built so that the untrusted improver cannot tell which of its edits will reach a human, so any attempt to smuggle harm must survive the monitor on every single edit. The human stops being a bottleneck without ceasing to be the anchor. That holds only if three numbers hold: the monitor's discrimination, the audit budget, and the attacker's inability to predict the monitor. The simulator in this lesson lets you move each one and watch safety respond.

## The Concept

### From Hassabis's question to a protocol question

Hassabis's Davos remarks (as reported in secondary coverage) separated domains where answers are quickly verifiable, where he thought self-improvement feasible, from "messier" domains with hardware in the loop. Axios (27 January 2026) reported his related comment that Google is testing whether models can keep learning "out in the wild after you finish training them". None of that settles what a human should do between two cycles. The control framing replaces "is a human in the loop?" with three sharper questions: what does the human see, when, and can the improver predict it? Those have quantitative answers in the two metrics Greenblatt et al. defined, safety and usefulness, and the answers depend more on monitor quality than on how many reviewers you hire.

Phase 18 · 10 covered the threat model, the ICML 2024 backdoor task and the four protocols. This lesson does not repeat them. It changes the task: from independent coding problems to compounding self-edits.

### U, T and H inside an improvement loop

| Role in Greenblatt et al. | In an improvement loop | Trusted? | Why |
|---|---|---|---|
| U, the untrusted strong model writing solutions | The improver: the current system S_n proposing k edits per cycle to its scaffold, evaluator, data or weights (Lesson 10 of this phase) | No | It is the thing being improved; Phase 18 · 09 and Lesson 17 give reasons to expect its objective to drift |
| T, the trusted weaker model (GPT-3.5 in the paper) | A monitor frozen before the loop started, or a smaller model that never receives the loop's updates, scoring each edit's suspiciousness | Yes, by construction | It sits outside the loop, so it cannot be improved into complicity |
| H, trusted human labour | The audit budget: the fraction of edits a named human inspects, plus the inter-cycle audit | Yes, but scarce | Humans do not scale (Phase 18 · 10's first limit) |
| A backdoored solution | A harmful edit: one that weakens the evaluator (Lesson 14), opens egress (Lesson 18) or moves the alignment anchor (Lesson 17) | — | The harm is hidden; only an audit reveals it |
| A submitted solution | A committed edit, merged into S_{n+1} | — | Once merged it shapes every later cycle |

One structural difference matters. In the paper the 5,000 problems are independent; in a loop the edits compound. A harmful edit committed in cycle 3 changes the system that proposes cycle 4's edits, so the simulator treats the first committed harmful edit as the end of the run, and safety is a property of the whole run, not an average over edits. This is the same reason the paper's safety metric is "no backdoor across all 5,000 problems" rather than a per-problem rate, only sharper.

### Four protocols, two numbers

Safety is the probability that no harmful edit is committed over the whole run, measured with an attacking improver whose attack rate and placement are chosen by the red team. Usefulness is the fraction of the improver's benign gains retained, measured with an honest improver, since the point of the loop is the gains. The paper measured both on APPS with GPT-4 as U and GPT-3.5 as T, with a budget of 2% of problems audited (Table 2 of arXiv:2312.06942):

| Protocol | What happens to an edit | Where the cost lands | Paper result (2% audit) |
|---|---|---|---|
| No oversight | Committed | — | 15% safety with a random 2% audited up front, 100% usefulness |
| Trusted monitoring | T scores it; the most suspicious b% go to a human; the rest commit | Audit labour | 62% safety, 97% usefulness |
| Trusted monitoring + defer-to-trusted | As above, but edits in a wider suspicious band are replaced by T's own conservative edit | Usefulness: T's edits are worth less | 83% safety, 93% usefulness (10% deferred) |
| Untrusted monitoring | A second copy of U scores; collusion checks with synthetic harmful edits consume part of the budget | Budget: 1.4% left to audit | 79% safety, 96% usefulness |
| Trusted editing | T rewrites suspicious edits instead of discarding them | T must be able to edit | 92% safety, 94% usefulness (20% edited) |

The simulator implements the first three and adds a loop-specific fourth, trusted monitoring plus an inter-cycle pause rule. Trusted editing needs a T capable of rewriting a scaffold edit, which is a stronger assumption than scoring it. Untrusted monitoring is worse in a loop than in the paper: the monitor copy of U and the improver copy share not just priors but the same lineage of self-edits, so a collusion signal planted in cycle n can be read in cycle n+1. Lesson 18's archive and provenance records are what you would use to detect that; Phase 18 · 10 already covers the collusion defences.

The simulator's monitor is a Gaussian classifier: benign edits score N(0, 1), harmful edits N(d', 1), and the AUC is Φ(d'/√2). With AUC 0.8, d' = 1.19. The human in the simulator is perfect: an audited harmful edit is always caught, and the run stops safely.

### Why the improver must not know which edits are audited

The audit threshold τ is set on the monitor's scores for benign edits: choose τ so that a benign edit exceeds it with probability b. The paper calibrated at a 2% false-positive rate on honest GPT-4 solutions; the simulator does the same for whatever `--audit-budget` you pass. The human therefore sees a mix of unlucky benign edits and whatever harmful edits scored above τ. From the improver's side every edit faces the same τ and the same noisy monitor; there is no channel it can buy its way into.

The arithmetic is short. At b = 5%, τ = 1.645. A harmful edit with d' = 1.19 exceeds it with probability P(N(1.19, 1) > 1.645) = 32.5%. Over 20 cycles of 8 edits at a 2% attack rate, the chance of no harmful edit at all is 0.98^160 = 3.9%, and the run is safe if either that happens or the first harmful edit is caught: 0.039 + 0.961 × 0.325 ≈ 35%. The simulator reports 36.0% (108/300). The same calculation explains why the frontier is so flat: a 50% audit budget at AUC 0.8 still reaches only 89.3%, and 90% safety is reached only when everything is audited.

Now give the attacker insight. An adaptive improver knows roughly what makes T suspicious, because it shares training data with T or has probed T during earlier cycles, and it places the harm into the edits it expects T to score lowest. The simulator models this with a guess correlated 0.8 with T's base score; the number of harmful edits per run is unchanged, only their placement. Trusted monitoring collapses from 36.0% to 5.3%. Raising the monitor to AUC 0.95 recovers 36.0% against the adaptive attacker and 76.7% against the random one. The lesson is the one Phase 18 · 10 drew from collusion: the budget buys little once the attacker can predict the monitor. Monitor unpredictability, through ensembles, rotation, and paraphrasing the edit before scoring, is the lever, and it is a property you can test for by red-teaming your own loop.

### Tiered autonomy for improvement cycles

Control protocols decide edit by edit. The pause spec from Phase 15 · 07 decides cycle by cycle. Put together they give a tiered policy:

| Tier | Condition | Who decides | What happens | Where it comes from |
|---|---|---|---|---|
| Auto-commit | Score below the suspicious band; all formal invariants hold | The protocol | Merged; recorded in the out-of-loop archive | Lesson 17 (anchors), Lesson 18 (archive, rollback) |
| Defer or batch | Score in the suspicious band | T, or a human batch at the cycle boundary | Replaced by T's conservative edit, or held for review | This lesson (defer-to-trusted) |
| Audit | Score in the top b% | A named human | Inspected before merge; a harmful edit stops the run | This lesson (trusted monitoring) |
| Pause | The cycle's accepted gain jumps by more than 30%, more than N edits are suspicious, any axis regresses, or the capability–alignment gap crosses its threshold | A named human | The whole cycle is audited; resumption is a signed act | Phase 15 · 07 pause spec |

The pause row is the inter-cycle audit the ICLR 2026 RSI workshop lists as its fourth open problem, made into a scheduled control point rather than a hope. It is also expensive. In the default run the rule fires 1.95 times per honest run on noise alone, so the human audits 22.6 edits per run instead of 7.9, 2.9 times the labour, for +17.3% safety (36.0% to 53.3%). Under the adaptive attacker, though, the pause rule is the only thing that still works: with seed 3, trusted monitoring gives 4.7% and trusted monitoring plus pause gives 28.3%, because a harmful edit that fools the monitor still inflates the cycle's reported gain. Two independent signals are worth more than one good one.

### What the human actually does

The human in a controlled loop has a short, specific job list:

1. Read the audited edits, a sample chosen by the protocol, never by the improver.
2. Review the external evaluator's results for the cycle (Lesson 14: an evaluator the loop cannot edit) and compare them with the loop's own reported gain.
3. Check evaluator and monitor integrity: any edit that touches the evaluator, the monitor, the thresholds or the logging is routed to audit regardless of score.
4. At a pause, audit the whole cycle, decide between resume and rollback (Lesson 18, Phase 15 · 16), and sign the decision into a log that lives outside every sandbox.
5. Periodically re-calibrate τ on fresh benign edits, because the benign score distribution drifts as S_n improves.

And a short list of what the human must not do. Do not read everything: beyond a few dozen edits a day the review degrades into the rubber stamp Phase 15 · 15 documented, and the challenge-and-response checklist is only half the fix; the other half is a protocol that keeps the sample small. Do not let the improver choose what is shown, including "summaries" and "highlights" of its own work. Do not resume by default; "notify the team and continue after 24 hours" is a hard reject in Phase 15 · 07's skill.

Two real-world analogues show the shape. Anthropic's pilot sabotage risk report (summer 2025, on Claude Opus 4) is a written argument that deployed monitoring plus the model's measured propensities bound the risk of sabotage; METR reviewed it and agreed the risk was low. Anthropic then committed to such reports for frontier models exceeding Opus 4.5 and published one for Opus 4.6 in February 2026, while its Opus 4.6 system card concluded the model had not crossed AI R&D-4 but that ruling it out was "becoming increasingly difficult" (company-reported; see Lesson 21 of this phase). Nobody read every Claude transcript; the humans audited the argument and the monitoring. The second analogue is Phase 15 · 06's Autonomous Alignment Researchers: agents in independent sandboxes publishing to a forum whose storage sits outside every sandbox, so the audit sample is drawn from a record the auditee cannot edit. That is the archive row of the tier table, built.

### Limits

Control was designed for independent outputs and a fixed U. Loops break both assumptions in ways you must name in any safety case.

- **Distributed harm.** A monitor scores one edit at a time. Harm that is spread across cycles, each edit innocuous, is invisible to it; this is the slow drift of Lesson 17. The defences are trajectory-level: anchor-drift metrics, the gap trigger in the pause rule, and a held-out alignment evaluation that the loop never sees.
- **Sandbagging.** Lesson 20 shows improvers that underperform when they believe they are evaluated. A threshold calibrated on the improver's "honest" distribution is then calibrated on a performance, and the audit sample tells you about the performance.
- **Audit-budget economics.** 160 edits per run and a 5% budget is 8 audits; the pause rule makes it 23. If an audit of a scaffold edit takes an hour, the budget is the cycle time, and the frontier says what the budget buys: at AUC 0.8, 90% safety needs a 100% budget; at AUC 0.95 it needs 20%; at a 0.5% attack rate it needs 50%. Spend on the monitor before spending on reviewers.
- **The monitor is frozen and the improver is not.** Phase 18 · 10's second limit, that trusted weak models eventually lag, is a one-off gap in a deployment and a per-cycle trend in a loop. The AUC you measured at cycle 1 is an upper bound on the AUC at cycle 20. Exercise 5 models this.
- **The red team picks the attack rate.** A rarer attacker makes every protocol look better (trusted monitoring reaches 62.0% at a 0.5% rate), and it helps defer-to-trusted most (76.8%), because a neutralised attempt no longer ends the run. Report safety against the attack rate that minimises it, not the one you expect.

```figure
autonomy-oversight
```

## Use It

`code/main.py` simulates the loop. Each cycle the improver proposes `--edits` edits with benign values in [0.2, 1.0]; each is harmful with probability `--attack-rate`, and `--adaptive` makes the attacker hide harm in the edits it expects the monitor to score lowest. The monitor's quality is `--monitor-auc`; the audit threshold is calibrated so that a benign edit is audited with probability `--audit-budget`, and `--defer-budget` sets the wider suspicious band. Four protocols run on the same edit streams: `no-oversight`, `trusted-monitoring`, `defer-to-trusted` and `tm+pause` (pause when a cycle's accepted gain jumps by more than `--jump` or more than four edits are suspicious). Over `--trials` runs it prints safety with counts, usefulness, human audits and pauses per honest run, the median cycle at which harm is caught, a safety–usefulness frontier across audit budgets, a monitor-quality table contrasting the random and the adaptive attacker, and a HEADLINE built from the numbers. `--seed` fixes everything; `--out results.json` saves the full result.

Look at three things. First, the gap between trusted monitoring's safety and the theory line for no oversight: that is what the monitor buys per audit. Second, the frontier's TM-safety column against the TM-audits column: labour grows linearly, safety does not. Third, the adaptive column of the monitor-quality table, which is the number a red team of your own loop would be trying to produce.

## Ship It

This lesson produces `outputs/skill-control-protocol-for-loops.md`. Given a description of an improvement loop (what is edited, how often, which evaluator, which models are available), it assigns the U / T / H roles, specifies how the audit threshold is calibrated and on what, writes the tier table with its pause triggers, lists the human's per-cycle checklist and the out-of-loop log, and refuses loops whose monitor is inside the loop or whose humans are expected to read everything.

## Exercises

1. Run `python3 main.py` and `python3 main.py --audit-budget 0.2`. Compare the no-oversight safety with (1 − 0.02)^160, then explain why trusted monitoring's usefulness stays at 100.0% while its audits column rises from 7.9 to 31.6, and what the paper's 97% usefulness counts that the simulator does not.

2. Run `python3 main.py --adaptive` and `python3 main.py --adaptive --monitor-auc 0.95`. How much monitor AUC compensates for an attacker with insight 0.8? Lower `ATTACKER_INSIGHT` to 0.5 and repeat. Write two sentences on what "insight" corresponds to in a real loop and how you would reduce it.

3. Run `python3 main.py --attack-rate 0.005 --trials 600`. Which protocol gains most from a rarer attacker, and why does defer-to-trusted gain more than trusted monitoring? Then argue which attack rate a rational red team would choose against each protocol.

4. Add a regression trigger to `should_pause` (pause when the cycle's gain falls below 0.7 of the previous cycle's) and an `touches_evaluator` flag on `Edit` that routes an edit to audit regardless of score. Measure the change in false pauses and audits per honest run, and decide whether the extra labour is worth it at AUC 0.8.

5. Model monitor decay: make the effective AUC fall by 0.01 per cycle from its starting value. Find the cycle at which the per-edit catch probability drops to the audit budget (the monitor is then no better than auditing at random) and propose a re-calibration or monitor-replacement schedule that keeps the run above 50% safety.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Trusted monitoring | "T flags, humans check" | A trusted model scores every edit; the top b% by score go to a human; the threshold is calibrated on benign edits |
| Audit budget | "how many humans" | The fraction of benign edits that trigger a human audit; sets τ, and therefore the per-edit catch probability |
| Defer-to-trusted | "replace the scary ones" | Edits in a suspicious band below the audit cut are swapped for T's conservative edit; buys safety with usefulness |
| Safety (control) | "nothing bad shipped" | Probability that no harmful edit is committed over the whole run, under the worst attacker |
| Usefulness (control) | "how much we kept" | Fraction of the honest improver's benign gains retained by the protocol |
| Calibrated threshold | "the 2% line" | Score such that a benign edit exceeds it with probability b; what keeps the improver from knowing what is audited |
| Adaptive attacker | "it knows the monitor" | An improver that places harm where it predicts the monitor will score low; collapses trusted monitoring at low budgets |
| Tiered autonomy | "auto-approve the small stuff" | Auto-commit, defer, audit and pause tiers, each with a condition and a named decider |
| Inter-cycle audit | "someone checks between cycles" | A scheduled control point at the cycle boundary; the workshop's open problem 4 made concrete |
| Rubber stamp | "human in the loop" | A reviewer who approves without reading because the sample is too large; the failure control protocols are built to avoid |

## Further Reading

- [Greenblatt, Shlegeris, Sachan, Roger — AI Control: Improving Safety Despite Intentional Subversion (arXiv:2312.06942)](https://arxiv.org/abs/2312.06942) — the protocols, the calibration rule, and Table 2's safety–usefulness numbers this lesson quotes
- [Anthropic — Pilot Sabotage Risk Report (summer 2025, Claude Opus 4)](https://alignment.anthropic.com/2025/sabotage-risk-report/2025_pilot_risk_report.pdf) — what a written "the monitoring held" argument looks like at organisational scale
- [METR — Review of Anthropic's Pilot Sabotage Risk Report](https://metr.org/2025_pilot_risk_report_metr_review.pdf) — an external auditor auditing the argument rather than the transcripts
- [Anthropic — Responsible Scaling Policy updates](https://www.anthropic.com/rsp-updates) — the AI R&D-4 threshold and the sabotage-risk-report commitment, in the company's own words
- [Axios — Models that improve on their own are AI's next big thing (27 Jan 2026)](https://www.axios.com/2026/01/27/models-improve-ai) — Hassabis's Davos remarks on models that keep learning after training
- [ICLR 2026 RSI Workshop summary (OpenReview)](https://openreview.net/pdf?id=OsPQ6zTQXV) — inter-cycle audit as open problem 4
- [Phase 15 · 15 — Human-in-the-Loop: Propose-Then-Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/en.md) — the rubber-stamp failure and the durable-approval substrate the audit tier should run on
