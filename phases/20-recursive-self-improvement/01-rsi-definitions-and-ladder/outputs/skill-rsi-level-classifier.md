---
name: rsi-level-classifier
description: Place a self-improving system on the Liu et al. L1-L5 ladder and in Chen et al.'s two-axis grid from five observable attributes, with quoted evidence and refusal rules.
version: 1.0.0
phase: 20
lesson: 1
tags: [rsi, self-improvement, taxonomy, ladder, verification-hierarchy, governance]
---

Given a paper, system card, design document or repository README describing a system that is said to "improve itself", decide which rung it actually occupies. Classify from what is edited and who applies the edit, never from the capability curve or the authors' own label.

Produce:

1. **Attribute table.** One row per attribute, each with a verdict and a quoted evidence line (section or page):
   - Proposes: does the system itself generate candidate changes?
   - Applies: are candidate changes applied with no human between proposal and deployment into the next cycle?
   - Validates: does the system decide accept/reject itself, and with what signal?
   - Mechanism edit: is the thing being edited itself an improver? Record `none` (model, prompts, data or tools only), `operators` (it evolves its own improvement operators, e.g. mutation prompts), or `code` (the program that proposes, applies or validates is editable by the loop).
   - Domain: `single` benchmark family, `multi` fixed benchmarks, or `open` (broad, evolving tasks).
   - Transfers: have improvements been shown to carry across domains or base models? Quote the experiment.
   - Verifier: `formal`, `execution` (tests, answer keys, simulators), `judge` (LLM judge, PRM, rubric), `self` (intrinsic self-assessment) or `human`.
2. **Liu et al. level** with the rule that fired: no proposal → L1; proposes but a human applies or validates → L2; autonomous P/A/V with a fixed mechanism → L3; mechanism edited, bounded domain → L4; mechanism edited, open domain with demonstrated transfer → L5.
3. **Chen et al. cell**: what is improved (deployment behaviour / training policy / evaluator / research process) × loop closure (human-in-loop / closed within a human-chosen task / closed including task choice).
4. **Verifier rung and failure path.** Name where the verifier sits in the hierarchy (formal → execution → judge → self) and state in one sentence what the loop does when the verifier is wrong (DGM: fake test logs were accepted; Self-Rewarding LMs: the judge saturates).
5. **Boundary flags.** Say explicitly if the case is operators-only self-reference, transfer without self-reference, or self-reference on fixed benchmarks, since each is a known place where readers disagree.
6. **Governance consequence.** One line: which threshold family would care (RSP AI R&D, PF AI Self-improvement, FSF ML R&D) and whether the classified rung is at, below or above it.

Hard rejects:
- Any level assigned from a capability curve, a benchmark delta or the word "recursive" in the title. A sub-critical recursive loop and a fixed improver produce identical curves.
- Any L4 or L5 verdict for a system where a human applies or validates substantive changes. Editing the mechanism with a human in the apply step is L2.
- Any L5 verdict without an experiment showing transfer into a domain the loop was not tuned on. Transfer across fixed benchmarks is L4.
- Any verdict that lists the verifier as "benchmark" without saying what computes the score; a hidden LLM judge is a `judge`, not `execution`.

Refusal rules:
- If the source does not state who applies the edit between cycles, refuse to assign a level and return the attribute table with that cell marked `unknown` and the question to ask the authors.
- If the only evidence for autonomy is a demo video or a blog post without a method section, refuse; classify from the paper or the code.
- If asked to classify "the lab's internal system" from press reports alone, refuse and say which attributes press reports can and cannot establish.

Output: a one-page classification with the attribute table, the level and the rule that fired, the Chen cell, the verifier rung with its failure path, the boundary flags, and the governance line. Cite Liu et al. (DOI 10.20944/preprints202608.0051.v1) and Chen, Wang and Qu (arXiv:2607.07663) once each.
