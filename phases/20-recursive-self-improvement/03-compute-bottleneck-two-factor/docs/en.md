# Compute Bottlenecks: Why Software-Only Explosions Stall

> AI 2027 (Kokotajlo et al., April 2025) defines its Superhuman Coder as a lab that can run 30× as many agents as it has human research engineers, each 30× faster, on 5% of its compute budget, and its takeoff forecast adds: "These are assuming no increases in training compute." Forethought's software-intelligence-explosion papers (Eth & Davidson, March 2025; Davidson & Houlden, August 2025) freeze hardware the same way. Anthropic's RSP v3.1 (effective April 2, 2026) went the other way: its AI R&D threshold means compressing two years of 2018–2024 progress into one, a period in which Epoch AI measured frontier training compute growing roughly 4–5× per year. These are not the same claim, and this lesson gives you the arithmetic to tell them apart.

**Type:** Learn
**Languages:** Python (stdlib, research-pipeline speedup and GPU-queue simulator)
**Prerequisites:** Lesson 02 of this phase (takeoff math), Phase 17 · 02 (inference platform economics), Phase 10 · 05 (scaling)
**Time:** ~60 minutes

## Learning Objectives

- Decompose "effective compute" into physical compute and software efficiency, and state which factor a software-only explosion can move.
- Model an AI R&D cycle as stages and derive the Amdahl ceiling `1 / f_compute` for software-only automation.
- Distinguish parallel labour from serial experiment latency, and compute the agent count at which a fixed GPU pool saturates.
- Classify 2025–2026 takeoff claims (AI 2027, Forethought, Epoch's GATE, RSP v3.1) by the compute assumption each makes.
- Explain why the compute bottleneck is also a governance handle (Lessons 13 and 21).

## The Problem

Lesson 02 of this phase gave you the growth equations: returns to software R&D `r`, Burtsev's reproduction number `R_AI`, and ceilings. Their input is something the older RSI literature waved past: how fast one cycle of research runs when the researcher is itself software. An AI researcher does not only think. It writes code, launches a training run, waits, reads the curves, and decides. Four of those steps are thinking and typing; one is a GPU doing arithmetic for hours or weeks, and no cleverness in the thinker makes it finish sooner.

That makes "AI automates AI research" a pipeline question, and pipelines obey Amdahl's law (Amdahl, AFIPS 1967): the part you did not speed up bounds the total. Forecasters know this. AI 2027's takeoff appendix holds "the FLOPs used for experimentation, training, etc." constant; Forethought lists "computationally expensive experiments" as a bottleneck and argues for workarounds. The 2025–2026 disagreement is not whether the bottleneck exists but how large the compute share of a cycle is, how far small-scale experiments can shrink it, and whether the yardsticks labs commit to (Lesson 21) hold compute fixed.

## The Concept

### Two factors: effective compute = physical compute × software efficiency

Epoch AI's compute-centric models, most explicitly the GATE integrated assessment model (Erdil, Potlogea, Besiroglu et al., arXiv:2503.04941, March 2025), write capability as a function of *effective compute*: physical compute (FLOP spent) times software efficiency (capability per FLOP). Both factors grew through 2024: Epoch puts frontier training compute at roughly 4–5× per year over 2010–2024, with algorithmic gains on top (their size is contested; Lesson 22).

A *software-only* explosion moves one factor: make training 10× more efficient and effective compute rises 10× with no new chips. That is Eth & Davidson's ASARA loop (AI systems for AI R&D automation) feeding back into itself. The narrower question here: can the loop that produces those gains run faster when its researchers are software?

### The research pipeline as stages

Model one research cycle (one idea proposed, tested, decided) as five stages with baseline wall-clock shares `f_i` summing to 1:

| Stage | Share `f_i` | Kind | Effect of AI copies |
|---|---|---|---|
| Ideation | 0.15 | labour | more and faster copies |
| Coding | 0.25 | labour | more and faster copies |
| Experiment compute | 0.40 | compute | none: a GPU-hour is a GPU-hour |
| Evaluation | 0.15 | labour | faster reading |
| Decision | 0.05 | labour, or human | faster, unless a human signs |

The shares are illustrative (`--compute-fraction` moves them). Automate stage `i` by a multiplier `m_i` and the cycle time becomes `Σ f_i / m_i`, so

```text
S = 1 / Σ_i (f_i / m_i)
```

With one multiplier `k` on every labour stage and a compute-growth multiplier `g` on the experiment stage:

```text
S(k, g) = 1 / (f_labour / k + f_compute / g)
```

As `k → ∞`, `S → g / f_compute`. With compute fixed (`g = 1`) the ceiling is `1 / f_compute`: **2.5×** for the shares above, however many agents you run and however fast they think. The mirror holds: with human labour fixed and unbounded compute, `S → 1 / f_labour = 1.67×`. Each factor is the other's bottleneck.

### Worked example

`code/main.py` with default shares and `g = 1` prints:

| `k` | cycle time | speedup | share of ceiling |
|---|---|---|---|
| 1× | 1.000 | 1.00× | 40.0% |
| 2× | 0.700 | 1.43× | 57.1% |
| 10× | 0.460 | 2.17× | 87.0% |
| 30× | 0.420 | 2.38× | 95.2% |
| 100× | 0.406 | 2.46× | 98.5% |
| 1000× | 0.401 | 2.50× | 99.9% |

AI 2027's "30× faster" labour lands at 2.38×, already 95.2% of everything software-only can give; the exact `k` for 95% of the ceiling is `19 × f_labour / f_compute = 28.5`. Going from 30× to 1000× buys 0.12× more. For 10× the compute term must move: with `g = 4` the ceiling is `g / f_compute = 10×`, and at `k = 30` the pipeline runs 8.33× faster, 3.5× more than software alone.

### Serial versus parallel: copies share the GPUs

Amdahl describes one agent; AI 2027's Superhuman Coder is many copies. Thirty agents can explore thirty ideas at once; they cannot run thirty training runs on eight GPUs. `code/main.py` models this as a closed queue: `N` copies, `C` GPUs, and each agent loops *think* (`f_labour / k`), *submit one experiment* (duration `E = f_compute / g`), *wait for a GPU*, *read the result*, *repeat*; the next idea depends on the current result. Throughput is bounded twice:

```text
X(N) ≤ min( N × S(k, g),  C / E )
```

The bounds cross at the knee `N* = (C / E) × (single-agent cycle time)`. With `C = 8`, `k = 30`, compute fixed: ceiling `8 / 0.40 = 20` experiments per cycle, knee 8.4 agents. The default run shows the far side: 8 agents complete 19.04 experiments per cycle with zero wait; 128 agents complete 19.84 with a mean wait of 5.60 cycles, and each copy's cycle time stretches from 0.42 to 6.40 cycles, 15× slower per copy.

Two consequences follow. *Faster thinkers saturate a pool sooner*: with human-speed labour (`--automation 1`) the knee moves from 8.4 to 20 agents, because slow thinkers leave GPUs idle between submissions. And the loop's *cycle time* is set by experiment latency plus queueing, not by reasoning speed: this is Burtsev's limiting timescale (arXiv:2609.00137, August 2026; Lesson 02). Whatever `R_AI` is, compounding happens once per cycle, and the cycle is as long as its slowest experiment.

The standard escape is to shrink `E`: run small-scale experiments and extrapolate. `--compute-fraction 0.20` doubles the software-only ceiling to 5× and pushes the 95% point to `k = 76`. The catch is that a small-scale result is only as good as its extrapolation to frontier scale (Phase 10 · 05); AI Scientist v2's out-of-distribution collapse (Phase 15 · 05) is small-scale confidence that did not transfer. A 10× software-only speedup needs the compute share down to 10%; 30× needs about 3%.

### Where the 2025–2026 debate stands

| Source | Compute assumption | Claim | Read it with |
|---|---|---|---|
| Eth & Davidson, Forethought, Mar 2025 | fixed hardware | software-only explosion possible; expensive experiments a bottleneck with "possible workarounds" | how far `f_compute` must fall |
| Davidson & Houlden, Forethought, Aug 2025 | software only | ~60% that >3 years of progress compress into 1; ~20% for >10 years; sensitive to "diminishing returns to parallel labour" | the queue knee |
| AI 2027 (Apr 2025; revamped Dec 2025) | "no increases in training compute" | SC = 30× agents at 30× speed on 5% of compute; median SC → ASI about one year | `S(30, 1) = 2.38×` |
| Epoch AI GATE (arXiv:2503.04941, Mar 2025) | both factors endogenous | effective compute drives capability, automation, reinvestment; outputs conditional, not forecasts | both factors at once |
| Anthropic RSP v3.1 (Apr 2, 2026) | compute-inclusive | "doubling the rate of progress in aggregate AI capabilities", two years of 2018–2024 progress in one, not "the productivity of researchers"; v3.4 (Jul 8, 2026) revised the wording | `g` is inside the baseline |

The trap is comparing a software-only forecast against a compute-inclusive threshold. AI 2027's one-year SC → ASI path holds hardware frozen. RSP v3.1's bar is two years of 2018–2024 progress, when compute grew 4–5× per year, so doubling aggregate progress at fixed compute would require software to cover the hardware factor's missing contribution too. A lab reporting a speedup has said nothing about which bar it is approaching until it says what happened to its compute. Anthropic's August 2026 Risk Report, as relayed by secondary sources, says internal research is "significantly faster" but not yet 2×, with Claude rated AL4+ for 26% of internal AI R&D work: company-reported data points, not measurements (Lesson 13).

### Why the bottleneck is also a safety handle

A software-only explosion is hard to see from outside: efficiency gains live in code and weights. Compute is the opposite. Chips come from a handful of fabs, sit in datacenters that draw megawatts, and are spent in training runs that take weeks; export controls, compute accounting and reporting thresholds (Phase 18 · 24) attach to that trail. The Amdahl ceiling makes the trail informative: if a loop cannot run more than `1 / f_compute` faster without more experiment compute, sustained acceleration beyond that ceiling implies the compute factor moved, and compute leaves receipts. Phase 15 · 13's cost governors apply the same reasoning one level down: a cap on the stage that cannot be parallelised is a cap on the loop. Lesson 21 picks this up.

```figure
cost-governor-stack
```

## Use It

`code/main.py` has two parts. The first sweeps `k` from 1× to 1000× under Amdahl's law while the compute stage is capped by `--compute-growth g`; `--scenario software-only` holds `g = 1`, `--scenario compute-growth` sweeps `g` with `k = 1`, and the default `both` prints them side by side. The second is a closed queue: `N` agents (up to `--agents`) submit experiments to `--gpus` GPUs over `--cycles` baseline cycles, deterministic by default, lognormal-jittered under `--jitter` (seeded by `--seed`); it reports throughput, utilisation, mean wait, per-copy cycle time, the pool ceiling `C / E` and the analytic knee. `--compute-fraction` moves the compute share; `--human-decision` keeps the decision stage at human speed. Every HEADLINE sentence is generated from computed numbers.

## Ship It

This lesson produces `outputs/skill-research-pipeline-bottleneck-audit.md`. Given a claimed research speedup (a forecast, a lab statement, or a governance threshold), it decomposes the pipeline into stages, computes the software-only and compute-inclusive ceilings, locates the claim relative to the GPU-pool knee, and classifies its compute assumption as software-only, compute-inclusive or ambiguous.

## Exercises

1. Run `python3 main.py --scenario software-only` and verify by hand that the asymptote equals `1 / f_compute`. Then run `python3 main.py --scenario compute-growth` and verify the compute-only asymptote equals `1 / f_labour`. One sentence: why are they mirror images?

2. Run `python3 main.py --compute-fraction 0.20 --scenario software-only`. Record the ceiling, the speedup at `k = 30`, and the `k` for 95% of the ceiling. Then write a paragraph on what must be true of small-scale experiments for this ceiling to be real, using Phase 10 · 05 and Phase 15 · 05 as evidence.

3. Run `python3 main.py --automation 1 --agents 256 --scenario software-only` and compare the knee with the default (`k = 30`). Explain why human-speed thinkers can share eight GPUs at 20 agents while 30× thinkers saturate them at 8.4, and what this implies for the "30× as many agents" half of AI 2027's SC definition.

4. Run `python3 main.py --seed 3 --jitter 0.5 --scenario software-only`. The 128-agent throughput (20.30) exceeds the printed ceiling (20.00). Explain why this is not a bug. Repeat for seeds 1 to 5 and report the range of throughputs and mean waits at 16 agents.

5. (Hard) In `simulate_queue`, compute growth makes each experiment shorter (`E / g`, "faster chips"). Add a mode that adds GPUs instead (`C × g`, "more chips") with `E` unchanged. At `k = 30`, `g = 4`, compare the two modes' ceiling, knee and per-copy cycle time at 128 agents. Which mode shortens the loop's cycle time, and why is that the one that matters for `R_AI`?

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Effective compute | "how much compute a model really has" | Physical compute × software efficiency; what compute-centric models map to capability |
| Software-only intelligence explosion (SIE) | "AI improves AI without new chips" | A loop in which only the software factor moves; hardware fixed by assumption |
| Amdahl's law | "the serial part limits you" | Speedup `1 / Σ f_i / m_i`; the un-accelerated stage's share bounds the total |
| `f_compute` | "how long experiments take" | Share of a baseline cycle spent on experiment compute; software-only ceiling is `1 / f_compute` |
| Pool ceiling | "the GPUs are full" | `C / E` experiments per cycle; the most `C` GPUs can finish |
| Knee | "where more agents stop helping" | `(C / E) × single-agent cycle time`; above it, extra copies only lengthen the queue |
| Cycle time | "how fast the loop turns" | Think + wait + experiment per agent; Burtsev's limiting timescale for compounding |
| Compute-inclusive yardstick | "two years of progress in one" | A threshold (RSP v3.1) whose baseline already contains compute growth; not a software-only bar |

## Further Reading

- [Eth & Davidson — Will AI R&D Automation Cause a Software Intelligence Explosion? (Forethought, March 2025)](https://www.forethought.org/research/will-ai-r-and-d-automation-cause-a-software-intelligence-explosion) — the software-only framing.
- [Davidson & Houlden — How Quick and Big Would a Software Intelligence Explosion Be? (Forethought, August 2025)](https://www.forethought.org/research/how-quick-and-big-would-a-software-intelligence-explosion-be) — three governing factors; the 60% / 20% probabilities.
- [AI 2027 — Takeoff Forecast (Kokotajlo & Lifland, April 2025)](https://ai-2027.com/research/takeoff-forecast) — the SC definition and the fixed-compute assumption.
- [Erdil et al. — GATE: An Integrated Assessment Model for AI Automation (arXiv:2503.04941)](https://arxiv.org/abs/2503.04941) — the compute-centric model; sandbox at epoch.ai/gate.
- [Epoch AI — Training compute of frontier AI models grows by 4-5x per year](https://epoch.ai/blog/training-compute-of-frontier-ai-models-grows-by-4-5x-per-year) — the hardware trend.
- [Burtsev — Recursive Criticality of AI Self-Improvement (arXiv:2609.00137)](https://arxiv.org/abs/2609.00137) — cycle duration as the limiting timescale.
- [Anthropic — RSP updates](https://www.anthropic.com/rsp-updates) — the v3.1 clarification and the v3.4 revision.
- [Phase 15 · 13 — Action Budgets, Iteration Caps, and Cost Governors](../../../15-autonomous-systems/13-cost-governors/docs/en.md) — the same logic applied to one agent's budget.
