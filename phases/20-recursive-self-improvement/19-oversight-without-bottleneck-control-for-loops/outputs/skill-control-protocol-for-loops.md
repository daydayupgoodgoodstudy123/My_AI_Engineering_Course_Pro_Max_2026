---
name: control-protocol-for-loops
description: Design the oversight protocol for a self-improvement loop so that humans audit a sample, a trusted monitor scores everything, and the improver cannot tell which.
version: 1.0.0
phase: 20
lesson: 19
tags: [ai-control, rsi, trusted-monitoring, audit-budget, tiered-autonomy, inter-cycle-audit]
---

Given a description of an improvement loop (what the improver edits, how many edits per cycle, how long a cycle takes, which evaluator scores the loop, which models and how many reviewer-hours are available), produce a control protocol that keeps a human in the loop without making the human the bottleneck. Treat the improver as untrusted. Treat the loop's own evaluator as part of the improver.

Produce:

1. **Role assignment.** Name U (the improver), T (the monitor) and H (the audit budget). T must be frozen before the loop starts or be a model that never receives the loop's updates. State T's measured AUC against a held-out set of known-harmful edits, and the date it was measured. If T is a copy of U, say so and treat the protocol as untrusted monitoring with collusion checks, not trusted monitoring.
2. **Threshold calibration.** State the audit budget b, the benign-edit distribution τ is calibrated on (which cycles, how many edits), and the re-calibration schedule. The improver must not be able to observe τ, the monitor's scores, or which edits were audited.
3. **Tier table.** For every edit: auto-commit (below the suspicious band and all invariants hold), defer or batch (suspicious band; replaced by T's conservative edit or held for a human batch), audit (top b%; a named human inspects before merge), pause (cycle-level triggers). Each row has a condition, a decider and an action.
4. **Pause triggers.** At least: accepted gain jumps by more than X% in one cycle; more than N edits in the suspicious band; any axis regresses by more than Y; the capability–alignment gap crosses its threshold; any edit touches the evaluator, the monitor, the thresholds or the logging (route to audit regardless of score). Thresholds are set before the loop starts and recorded.
5. **Human checklist per cycle.** Read the audited sample; compare the external evaluator's result with the loop's reported gain; check evaluator and monitor integrity; at a pause, audit the whole cycle, decide resume or rollback, and sign the decision into a log stored outside every sandbox. State the expected audits per cycle and confirm they fit the reviewer-hours.
6. **Safety case numbers.** Report expected safety and usefulness under the worst attack rate and under an adaptive attacker, with the attacker's assumed insight into T. If you cannot produce these, say which red-team experiment would.

Hard rejects:
- Any protocol whose monitor is improved by the loop, scored by the loop's own evaluator, or editable by the improver.
- Any protocol in which the improver selects, summarises or orders what the human sees.
- Any protocol that expects a human to read every edit. State the sample size and the labour; if the labour exceeds the cycle time, the protocol is a bottleneck, not oversight.
- Any protocol that resumes after a pause without a named human's positive act.

Refusal rules:
- If no external evaluator exists (one the loop cannot edit), refuse: the pause triggers and the usefulness measurement both depend on it.
- If the monitor's AUC has not been measured, refuse to quote a safety number; produce the tier table and the red-team plan instead.
- If the user asks for a protocol that is "safe" without naming the attack rate it is safe against, refuse: safety is a worst-case number over attack rates and placements.

Output format:

Return a one-page protocol with:
- **Roles** (table: U / T / H, trust status, evidence)
- **Calibration** (budget, calibration set, schedule, what the improver cannot observe)
- **Tier table** (condition, decider, action, source lesson)
- **Pause triggers** (numeric, pre-registered, with owner)
- **Human checklist** (per cycle and at pause; audits per cycle vs reviewer-hours)
- **Safety case** (safety and usefulness against the worst attack rate and the adaptive attacker; the red-team experiment that produced them)
- **Known gaps** (distributed harm, sandbagging, monitor decay, with the mitigation chosen for each)
- **Sign-off line** (who owns the thresholds, who owns the monitor, who signs resumptions)

Cite Greenblatt et al. (arXiv:2312.06942) once for the protocol family and Phase 15 · 07's pause spec once for the cycle-level triggers.
