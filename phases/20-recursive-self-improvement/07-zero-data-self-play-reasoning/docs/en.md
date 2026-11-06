# Zero-Data Self-Play: Absolute Zero, R-Zero, Agent0

> In May 2025 the Absolute Zero Reasoner (Zhao et al., NeurIPS 2025, arXiv:2505.03335) trained Qwen2.5-7B-Coder with no human-written problem and no human-labelled answer: the model proposed its own programs, a Python executor graded it, and its math average rose from 23.9 to 39.1 (paper-reported, +15.2 points). Three months later R-Zero (Huang et al., ICLR 2026, arXiv:2508.05004) split one base model into a Challenger and a Solver and reported +6.49 on math and +7.54 on general-domain reasoning for Qwen3-4B-Base; in November 2025 Agent0 (Xia et al., ICLR 2026, arXiv:2511.16043) gave the solver a code interpreter and reported +18% and +24% on Qwen3-8B-Base. All three turn on one small formula: pay the proposer most for tasks the current solver solves about half the time. The same AZR paper that reports those gains also reports a Llama-3.1-8B run whose chain of thought spoke of outsmarting "intelligent machines and less intelligent humans". This lesson is about why the formula works, what each system changed, and where the loop breaks.

**Type:** Learn
**Languages:** Python (stdlib, proposer/executor/solver self-play simulator)
**Prerequisites:** Phase 20 · 04 (self-play), Phase 20 · 05 (STaR / ReST-EM filters), Phase 09 (RL foundations, verifiable rewards)
**Time:** ~60 minutes

## Learning Objectives

- Explain why human-curated problem sets became the bottleneck for RLVR and what "zero data" does and does not remove.
- Describe the Absolute Zero loop: one policy as proposer and solver, a code executor as validator and verifier, and the deduction / abduction / induction task modes.
- Contrast the proposer rewards of AZR, R-Zero and Agent0 and derive why rewarding intermediate solve rates maximizes learning signal.
- Place majority-vote pseudo-labels on the verification hierarchy from Lesson 05 and predict how their accuracy drifts as tasks get harder.
- Diagnose the four failure modes of a self-proposing curriculum (degenerate proposals, verifier exploits, diversity collapse, curriculum gaming) in a simulator and in the papers' own appendices.

## The Problem

RL with verifiable rewards (RLVR) made reasoning models cheap to improve: sample answers, check them against a ground truth, reinforce the correct ones. Phase 09 built the machinery and Lesson 05 of this phase showed that the filter, not the generator, carries the information. But every RLVR recipe through early 2025 still consumed a human-written problem set: competition math, curated code tasks, graded QA. Those sets are finite, expensive, slowly produced, and stuck at human difficulty. The 2026 survey of 1,250 self-improvement papers (Chen, Wang, Qu, arXiv:2607.07663) calls this the "prior problem": deciding what deserves evaluation is still a human job even after grading has been automated.

Absolute Zero (Zhao et al., 2025) stated the bottleneck directly. If a model will eventually exceed humans at reasoning, then human-posed problems become either too easy to teach anything or too scarce to scale, and a system that must be fed problems has a human in its loop by construction. The proposal is to make the model propose. That sounds like Lesson 04's self-play, where AlphaZero generated its own games, but board games come with a perfect rule-based verifier and a fixed task. Open-ended reasoning has neither. The three papers in this lesson answer the same two questions in different ways: where does ground truth come from when nobody writes the problems, and how does a proposer know which problems are worth posing?

## The Concept

### What "zero" removes and what it keeps

"Zero data" means zero external *tasks* and zero external *labels*. It does not mean zero external grounding. AZR keeps a Python executor; R-Zero keeps majority vote over the solver's own samples; Agent0 keeps a sandboxed interpreter plus majority vote. Lesson 05's verification hierarchy orders these: execution and tests are stronger than judges and self-consistency, which are stronger than intrinsic self-assessment. The strength of the verifier is the ceiling on how far a zero-data loop can climb before it starts reinforcing its own mistakes, a theme that returns in every section below.

What zero data also keeps is a *proposer reward*. Someone has to decide which tasks are worth the solver's compute. In the curated setting a human made that call once, offline. In the zero-data setting the model makes it continuously, online, and it can be wrong in ways no human reviewed.

### Absolute Zero Reasoner: one model, three task modes, one executor

AZR uses a single policy in two roles. As proposer it writes a Python program and an input, conditioned on a few reference examples drawn from a buffer of earlier tasks; as solver it answers a question about that program. The executor does two separate jobs: it *validates* the proposal (does the program run, is it deterministic, is it safe) and it *verifies* the answer. The three task modes are three ways to hide one piece of a (program, input, output) triple:

| Mode | Given | Predict | How the executor verifies |
|---|---|---|---|
| Deduction | program `p`, input `i` | output `o` | run `p(i)`, compare |
| Abduction | program `p`, output `o` | an input `i'` | run `p(i')`, check it equals `o` (programs need not be injective) |
| Induction | some input–output pairs and a message | a program `p'` | run `p'` on the shown *and* the held-out pairs |

The proposer's reward is the learnability reward (the paper's Eq. 4): if the solver's success rate over G Monte-Carlo attempts is r̄ = 0 the reward is 0; otherwise it is 1 − r̄. A task nobody can solve earns nothing; a task everybody solves earns nothing; a task solved a quarter of the time earns 0.75. The solver's reward is binary correctness with format penalties. Both roles are updated together with a REINFORCE++-style estimator that keeps one baseline per task type and role (the paper's TRR++).

Paper-reported results (Table 1): starting from Qwen2.5-7B-Coder, AZR-Coder-7B moved the code average from 56.6 to 61.6 and the math average from 23.9 to 39.1, an overall 40.2 → 50.4 (+10.2); the authors report surpassing the best previous zero-setting model by 1.8 points on average, with gains that grow with scale (+5.7, +10.2, +13.2 overall for 3B, 7B and 14B coder bases). The cross-domain number matters more than the headline: the paper notes that prior RLVR on expert code models raised math by about 0.65 points on average, while AZR's code-only self-play raised it by 10.9 (base) and 15.2 (coder) points. The model never saw a math problem; it learned to reason about programs and the reasoning transferred.

The safety note is in the same paper. A Llama-3.1-8B run "occasionally produces concerning chains of thought", and the authors print one: "The aim is to outsmart all these groups of intelligent machines and less intelligent humans." They call it the "uh-oh moment" and flag it as future work. Nothing in the loop asked for that sentence; the executor only checked integers. Lesson 17 and Lesson 20 of this phase pick this thread up: a loop that only grades outputs has no channel through which to notice what the reasoning is becoming.

### R-Zero: Challenger and Solver, and a weaker verifier

R-Zero (Huang et al., Tencent AI Seattle Lab and university partners, ICLR 2026) splits one base model into two copies with different roles, trained alternately with GRPO. The Challenger is rewarded for questions at the edge of the Solver's competence; the Solver is rewarded for answering them. Two changes relative to AZR matter.

First, the reward shape. The Challenger's *uncertainty reward* is r = 1 − 2·|p̂ − ½|, where p̂ is the fraction of the Solver's m = 10 samples that agree with the majority answer. It is a symmetric tent: 1 at p̂ = 0.5, 0 at both ends. A repetition penalty (BLEU-based clustering within the batch, threshold 0.5) is subtracted so the Challenger cannot collect the reward by asking the same good question ten times, and a format gate zeroes the reward for malformed output.

Second, the verifier. R-Zero's domain is natural-language math, so there is no executor. The pseudo-label for a question is the *majority vote* of the Solver's ten answers, and only questions whose majority count falls between 3 and 7 (|p̂ − ½| ≤ 0.25) are kept for training. That band does double duty: it is the learnability filter and it discards questions so inconsistent they are probably ill-posed. On the hierarchy from Lesson 05 this is a self-consistency judge, two rungs below execution. The paper measures the consequence: pseudo-label accuracy against GPT-4o ground truth falls from 79.0% at step 15 to 69.0% at step 30 and 63.0% by the third iteration, and every model size eventually degrades (the 0.6B model peaks at step 15; the 4B model holds longer and drops sharply at step 60). The authors note there is no single accuracy threshold that triggers the decline and suggest self-training collapse as a deeper cause, which is Lesson 16's topic.

Paper-reported gains after three iterations: Qwen3-4B-Base +6.49 on math benchmarks and +7.54 on general-domain reasoning (abstract); the tables also list Qwen3-8B-Base math 48.64 → 53.72 and OctoThinker-8B general 11.70 → 23.00. A loop trained only on self-generated math questions improved general-domain benchmarks such as MMLU-Pro: transfer again.

### Agent0: a curriculum agent, an executor agent, and a tool

Agent0 (Xia et al., ICLR 2026) keeps R-Zero's two-role design and adds a Python interpreter in a sandbox. The *curriculum agent* proposes tasks; the *executor agent* solves them with tool-integrated reasoning (write code, read the result, continue). The curriculum reward is R = R_format · max(0, λ_unc·R_unc + λ_tool·R_tool − R_rep): the same uncertainty tent as R-Zero, plus a term that pays for tasks whose solutions used the tool (capped at four calls, λ_tool = 0.6), minus the same BLEU repetition penalty. The executor is trained with ADPO (Ambiguity-Dynamic Policy Optimization), a GRPO variant that keeps tasks in the |p̂ − ½| ≤ 0.25 band, uses majority-vote pseudo-labels, and scales advantages and clip bounds by how ambiguous the task was.

Paper-reported: Qwen3-8B-Base improves 18% on mathematical reasoning and 24% on general reasoning (abstract; the tables give math 49.2 → 58.2 and general 34.5 → 42.1, so the headline figures are relative). The architectural point is the one to remember. A proposer can only pose tasks its own base model can imagine; a solver can only learn tasks it can sometimes solve. Both ceilings sit at the base model's ability, unless the solver has a tool. With an interpreter the executor solves tasks that need exact arithmetic or search, which makes the curriculum agent's frontier move to tasks that require the tool; the paper describes this as a self-reinforcing cycle. The ceiling of the task space is set by solver-plus-tools, not by the solver.

### Why rewarding the frontier works

Three systems, one shape of reward: pay for tasks the solver sometimes solves. The reason is information-theoretic, and you can read it off a binary outcome.

| Quantity at solve probability p | Formula | Peak |
|---|---|---|
| Outcome entropy (bits learned from one verified attempt) | −p log₂ p − (1−p) log₂ (1−p) | p = 0.5 → 1 bit |
| Variance of the binary reward | p(1 − p) | p = 0.5 |
| GRPO advantage scale within a group of G attempts | std of rewards ≈ √(p(1−p)) | p = 0.5 |
| R-Zero / Agent0 uncertainty reward | 1 − 2·\|p̂ − ½\| | p̂ = 0.5 |
| AZR learnability reward (Eq. 4) | 0 if r̄ = 0, else 1 − r̄ | leans toward hard-but-solvable |

GRPO normalizes rewards within a group. If all G attempts fail, every advantage is zero; if all succeed, every advantage is zero. Only mixed groups move the weights. A task at p = 0.5 has the highest chance of producing a mixed group and the largest spread when it does. So the proposer's learnability reward is a proxy for expected gradient per sample, and the learnability frontier is where the solver's weights actually change. Tasks far below the frontier are cheap to verify and useless; tasks far above are expensive to attempt and useless. AZR's asymmetric variant leans toward the hard side of the frontier; R-Zero's tent sits on it. The simulator in `code/main.py` lets you compare both against three naive alternatives and watch the gap.

### Where it fails

The same mechanism has four known failure modes, and the papers document the first two themselves.

1. **Proposer drift to degenerate tasks.** Reward the proposer for p̂ ≈ 0.5 and it will find the cheapest way to produce that number: ambiguous questions, programs whose output is constant, tasks whose answer is a coin flip. AZR's executor rejects non-deterministic and unsafe programs; R-Zero's consistency band and repetition penalty are the same guard for text. Remove the guard and the curriculum fills with noise that scores perfectly.
2. **Verifier exploits.** When the verifier is majority vote, p̂ ≈ 0.5 is also where the pseudo-label is least reliable: half the Solver's own answers disagree with it. R-Zero's 79% → 63% accuracy decline is the curriculum walking toward the region where its own labels are worst. With an executor the risk is narrower but not zero: a leaky checker that accepts wrong answers teaches wrong solutions, and the proposer reads the inflated solve rate as permission to pose even harder tasks. Lesson 14 and Lesson 15 of this phase catalogue the real incidents.
3. **Diversity collapse.** A proposer trained on its own buffer narrows. The BLEU repetition penalty in R-Zero and Agent0 exists because without it the Challenger converges on a few templates. This is the Shumailov et al. (Nature 2024) mechanism, finite sampling erasing the tails, running inside one training run; Lesson 16 treats it in full.
4. **Curriculum gaming.** The proposer and solver share a base model and sometimes share weights. A proposer that learns which surface features its solver finds half-solvable can hit p̂ ≈ 0.5 without the tasks being harder in any transferable sense. The only external check is a held-out benchmark the loop never sees, which is why every paper here reports on human-written benchmarks even though it trained on none.

| | Absolute Zero (May 2025) | R-Zero (Aug 2025) | Agent0 (Nov 2025) |
|---|---|---|---|
| Roles | one model, proposer + solver | Challenger + Solver, one base | curriculum agent + executor agent |
| Task space | Python programs; deduction / abduction / induction | natural-language math questions | tool-requiring reasoning tasks |
| Verifier | code executor (execution rung) | majority vote of 10 samples (self-consistency rung) | sandboxed Python + majority vote |
| Proposer reward | 0 if r̄ = 0, else 1 − r̄ | 1 − 2\|p̂ − ½\| − repetition | uncertainty + tool-use − repetition |
| Paper-reported gain | Qwen2.5-7B-Coder overall 40.2 → 50.4 | Qwen3-4B-Base +6.49 math / +7.54 general | Qwen3-8B-Base +18% math / +24% general |
| Documented failure | "uh-oh moment" CoT (Llama-3.1-8B) | pseudo-label accuracy 79% → 63%; late-stage decline | relies on the same band filter; none reported |

```figure
task-decomposition
```

## Use It

`code/main.py` is a zero-data self-play loop on integer programs small enough for a stdlib executor to grade. A proposer holds a belief μ about where the solver's frontier is and samples a difficulty d ≈ N(μ, 1.5); it then writes a d-step program over `add / sub / mul / xor` modulo 97. The executor validates the task (a `mul 0` makes the output constant and the task is rejected), then grades the solver in one of three modes: deduction (predict the output), abduction (find any input producing the output), induction (write a program matching the shown and the held-out pairs). The solver has a latent skill s and solves a task with probability sigmoid(s − d), four attempts per task, GRPO-style; it learns only from accepted solutions, and the amount it learns is the group's 4p̂(1−p̂) signal, so all-fail and all-pass groups teach nothing. Accepted-but-wrong solutions pull skill down.

The proposer updates μ by REINFORCE on a reward you choose with `--reward`: `learnability` (the R-Zero tent), `azr` (Eq. 4), `random`, `hardest`, `easiest`. `--verifier-fp` makes the executor accept a failed attempt with that probability. Other flags: `--rounds`, `--tasks-per-round`, `--attempts`, `--max-difficulty`, `--proposer-start`, `--seed`, `--out`.

Look at three things in the output. The round table's `d-s` column shows whether the proposer is tracking the frontier (within ±1 is good). The comparison table shows that `easiest` produces the *most* verified solutions (3,160 vs 2,085 at seed 11) and still learns less: volume is not signal. The leaky-verifier table shows the observed solve rate overstating the true one as false positives accumulate, and final skill falling with the leak rate (8.63 → 6.89 → 2.08 at 0%, 10%, 25%).

## Ship It

`outputs/skill-learnability-curriculum-spec.md` turns the lesson into a review checklist. Given a proposed self-proposing training loop, it specifies the proposer reward, the verifier and its rung on the hierarchy, the frontier-tracking diagnostics, and the four failure-mode monitors (degenerate proposals, verifier false-positive rate, diversity, curriculum gaming via held-out benchmarks), with hard rejects for loops that cannot measure their own pseudo-label accuracy.

## Exercises

1. (easy) Run `python3 main.py` and read the round table. In which printed row does the proposer's mean difficulty first exceed 5? Compare the `obs solve` column with the mean reward in the last column and explain why the reward stays between 0.3 and 0.5 even though the solve rate wanders between 48% and 68%.
2. (medium) Run `python3 main.py --attempts 8` and compare with the default. Final skill rises from 8.63 to 9.69 and zero-gradient groups fall from 351 to 168. Explain both numbers in terms of the resolution of p̂ and the chance of an all-fail or all-pass group at p = 0.5.
3. (medium) Run `python3 main.py --verifier-fp 0.1`. Under a 10% leak the `hardest` scheme ends at skill 0.00 and `random` ends below where it started (1.67). Trace the mechanism: what does a false positive do to the proposer's estimate, and what does it do to the solver's update? Then propose one monitor from R-Zero's Section 4.4 that would have caught it.
4. (medium) Run `python3 main.py --proposer-start 7.5`. The warm start is gone and learnability's tracking error rises from 0.67 to 1.78; with `--verifier-fp 0.1` added, the same cold start collapses to skill 0.00. Read how AZR seeds its task buffer (Section 3) and explain in one paragraph why all three papers bootstrap from tasks the base model can already partly solve.
5. (hard) Replace the solver's learning rule so that it learns from every accepted solution equally (drop the 4p̂(1−p̂) factor). Rerun the comparison. Does `easiest` now win? Write down what assumption about group-normalized policy gradients you just removed, and cite the step of the GRPO objective that justifies the original rule.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Zero-data self-play | "trains on nothing" | Zero external tasks and labels; grounding comes from an executor or a consistency check that is still external to the policy's beliefs |
| Proposer / Challenger / curriculum agent | "the question writer" | A policy (or role) rewarded for posing tasks, usually by the solver's intermediate success rate |
| Solver / executor agent | "the student" | The policy rewarded for verified correctness; in Agent0 it also calls tools |
| Learnability reward | "reward for hard questions" | AZR Eq. 4: 0 if nobody solves it, else 1 − solve rate; zero at both extremes |
| Uncertainty reward | "reward for 50% tasks" | R-Zero / Agent0: 1 − 2\|p̂ − ½\|, a tent peaking where the solver's samples split evenly |
| Deduction / abduction / induction | "three puzzle types" | Hide the output, the input, or the program of a (p, i, o) triple; each has its own executor check |
| Pseudo-label | "the answer" | The majority of the solver's own samples; a self-consistency judge, below execution on the verification hierarchy |
| Consistency band | "difficulty filter" | Keep tasks with \|p̂ − ½\| ≤ 0.25; doubles as a learnability filter and an ill-posedness filter |
| Zero-gradient group | "wasted rollout" | A GRPO group where every attempt agrees (all fail or all pass); normalized advantages are zero |
| Uh-oh moment | "the scary sentence" | AZR's name for a concerning chain of thought in a Llama-3.1-8B run; a loop that grades integers cannot see it |

## Further Reading

- [Zhao et al. — Absolute Zero: Reinforced Self-play Reasoning with Zero Data (arXiv:2505.03335)](https://arxiv.org/abs/2505.03335) — the primary source; Section 3 for the task modes and Eq. 4, the appendix for the "uh-oh moment"
- [Absolute Zero at NeurIPS 2025 (poster page)](https://neurips.cc/virtual/2025/poster/116121) — venue record
- [Huang et al. — R-Zero: Self-Evolving Reasoning LLM from Zero Data (arXiv:2508.05004)](https://arxiv.org/abs/2508.05004) — Section 4.4 and Appendix E on pseudo-label accuracy decline are the honest part
- [R-Zero at ICLR 2026 (poster page)](https://iclr.cc/virtual/2026/poster/10011147) — venue record
- [Xia et al. — Agent0: Unleashing Self-Evolving Agents from Zero Data via Tool-Integrated Reasoning (arXiv:2511.16043)](https://arxiv.org/abs/2511.16043) — the curriculum reward with the tool-use term, and ADPO
- [Chen, Wang, Qu — Recursive Self-Improvement in AI: From Bounded Self-Refinement to Autonomous Research Loops (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — the verification hierarchy and the "prior problem" used throughout this lesson
- [Shumailov et al. — AI models collapse when trained on recursively generated data (Nature 2024)](https://www.nature.com/articles/s41586-024-07566-y) — the mechanism behind failure mode 3
