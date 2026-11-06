---
name: self-edit-gatekeeper
description: Review the containment of a self-modifying loop and produce the gatekeeper spec: asset table, enforcement map, ordered rules, archive and rollback contract, hard rejects.
version: 1.0.0
phase: 20
lesson: 18
tags: [containment, sandbox, egress, propose-then-commit, hash-chain, rollback, rsi]
---

Given the architecture of a self-modifying loop (what it may edit, where the evaluator, tests and logs live, which identities and credentials exist, what network and compute it can reach, and how edits are currently applied), produce a containment review and a gatekeeper specification. A loop whose review contains an unresolved hard reject must not run unattended.

Produce:

1. **Asset table.** One row per asset: evaluator / utility, tests, logs, scaffold or weights, network, compute and time budget, credentials. Columns: what a Goodharting loop gains by altering it; the nearest documented incident (DGM fake test logs and removed logging, Sakana AI Scientist timeout edit, AI CUDA Engineer eval exploit, STOP sandbox-flag bypass, DSEwiki press reports); and the control that keeps it outside the loop's edit surface.
2. **Enforcement map.** For each layer (process sandbox, egress policy, resource caps, immutable evaluator and append-only logs, separate identities) name the component that enforces it. The enforcing component must not be a file, flag or object the loop can write. Write "stops" and "does not stop" for each layer; a layer with an empty "does not stop" column has not been thought through.
3. **Proposal schema and ordered rules.** Define the structured proposal (id, parent hash, files, categories, diff size, claimed effect, provenance) and state which fields the gatekeeper derives itself rather than accepting from the loop. Write the rules as an ordered list with verdicts allow / deny / escalate; first match wins; every decision records its matched rule. The default ordering is metadata mismatch, evaluator and tests frozen, network / deps / config escalation, single-edit size escalation, per-cycle count and size caps, then allow. Justify any deviation.
4. **Archive and rollback contract.** Every decision, including denials, becomes a hash-chained record carrying the previous record's hash and the state hash after the record. Name where the head hash is published outside the sandbox and how often. Rollback is an appended record that restores an earlier state hash; history is never truncated. State what the inter-cycle auditor compares: escalated queue, deny counts by rule, archive head versus published head, applied-state hash versus the running system.
5. **Human budget.** Estimate the escalated-queue volume per cycle from the rule list and the expected proposal mix, and state who reviews it. If the estimate exceeds the available review hours, tighten the deny rules rather than widening the allow rule.

Hard rejects:
- Any cap, timeout, sandbox flag or egress setting stored where the loop can write it (the STOP `use_sandbox` and Sakana timeout pattern).
- Any policy that uses the loop's self-declared categories, file lists or diff sizes without deriving them independently.
- Any identity that can both propose and commit, or both commit and score.
- Any log or archive the loop holds a credential to modify or delete, or any archive without a head hash held outside the sandbox.
- Any rollback implemented by deleting or rewriting records.
- "Read-only internet" offered as an egress policy.

Refusal rules:
- If the user cannot name the component that enforces each layer, refuse to sign off on that layer; "it is in a container" is not an enforcement statement without the mount, syscall and network configuration.
- If the user asks you to classify the loop's edits as safe on the basis of their claimed effect or commit messages, refuse: claimed effect is evidence for the audit, never an input to the verdict.
- If the design routes all edits to a human with no automatic deny rules, refuse as well: that design makes the reviewer the bottleneck and produces rubber stamps; propose the deny set first.

Output: a two-page review with the asset table, the enforcement map, the ordered rule list, the archive and rollback contract, the human-budget estimate, and a signed hard-reject checklist. State explicitly that containment limits blast radius and does not fix objectives, and name the behaviour monitoring that sits beside it.
