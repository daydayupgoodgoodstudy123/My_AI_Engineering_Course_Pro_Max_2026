# Model Collapse: Recursive Training on Your Own Output

> Shumailov et al. showed in *Nature* (vol. 631, pp. 755–759, published 25 July 2024; author correction 21 March 2025) that indiscriminately training on model-generated data causes irreversible defects: the tails of the original distribution vanish first, then the variance shrinks, and a chain of OPT-125m models fine-tuned on each other's output drifted from medieval church architecture to a list of coloured jackrabbits by generation 9. The mechanism needs no neural network at all — finite sampling is enough. Every refit on n of your own samples is a Wright–Fisher step in which a category with probability p disappears with probability (1 − p)^n ≈ e^(−np), and once it has zero samples the model can never produce it again. Gerstgrasser et al. (arXiv:2404.01413, April 2024) showed that accumulating data instead of replacing it bounds the damage; Seddik et al. (arXiv:2404.05090, April 2024) showed that when real data is mixed in there is a maximal synthetic fraction below which collapse can be avoided. Every self-training loop in this phase, from self-play (Lesson 04) to SEAL (Lesson 08), feeds its own output back as training data, which makes this the failure mode the loop's monitors must be built to see.

**Type:** Build
**Languages:** Python (stdlib, finite-sample recursive-training simulator)
**Prerequisites:** Phase 01 · 06 (probability & distributions), Phase 01 · 09 (information theory), Lesson 05 of this phase
**Time:** ~60 minutes

## Learning Objectives

- Explain early and late model collapse, name the three error sources in Shumailov et al., and show why finite sampling alone produces collapse.
- Derive the extinction probability (1 − p)^n ≈ e^(−np) and the first-order per-generation entropy loss, then check both against a simulation.
- Compare the replace, accumulate and mix-real regimes and state what each one buys and costs.
- Instrument a self-training loop with entropy, extinction, total-variation and pass@k-style diversity monitors, and say which of them can mislead.
- Write a synthetic-data mix policy with provenance tags, synthetic-fraction caps, diversity dashboards and regeneration from source.

## The Problem

Every loop in this phase generates data and trains on it. Self-play (Lesson 04) trains on games against itself. STaR and ReST-EM (Lesson 05) train on their own filtered rationales. Self-rewarding LMs (Lesson 06) train on outputs their own judge preferred. R-Zero and Agent0 (Lesson 07) train on tasks they proposed. SEAL (Lesson 08) writes its own fine-tuning data. In each case the model's output distribution at cycle g is the training distribution at cycle g + 1. Nothing in that sentence mentions the world.

A loop with that shape is a Markov chain on probability distributions. If the only thing that re-anchors it is data it generated itself, its absorbing states are degenerate: a distribution that has lost a mode cannot, by sampling from itself, get the mode back. Chen, Wang and Qu's 2026 survey (arXiv:2607.07663) lists "collapse dynamics" alongside grounding requirements and compute limits as a fundamental constraint on open-ended RSI, and files model and diversity collapse under failures that come from violating verification requirements. The same chain runs at web scale: model-generated text is now a large share of what the next crawl collects, so even a lab that never trains on its own outputs on purpose is training on someone's.

The question of this lesson is quantitative. How fast does the tail go? What slows it? Which numbers on a dashboard would have shown it before generation 9?

## The Concept

### What Shumailov et al. observed

The Nature paper defines model collapse as a degenerative process in which generations of models trained on data produced by earlier generations lose information about the true distribution. It distinguishes two stages. In **early collapse** the model loses the tails: low-probability events, rare categories and minority styles disappear first. In **late collapse** the model converges towards a distribution with much smaller variance than the original, often bearing little resemblance to it. Three error sources drive the process: **statistical approximation error** (a finite sample never reproduces the distribution exactly, so information is lost at every resampling step), **functional expressivity error** (the model class cannot represent the truth — a Gaussian mixture with too few components, a tokenizer that cannot say a word) and **functional approximation error** (the learning procedure itself adds bias). The paper treats the first as primary and shows, with Gaussian mixtures, variational autoencoders and language models, that it alone suffices.

The language-model experiment fine-tunes OPT-125m on wikitext2, generates text from it, fine-tunes the next generation on that text, and repeats. The worked example starts from a passage about medieval church architecture; by generation 9 the chain outputs a list of black-, white-, blue-, red- and yellow-tailed jackrabbits. Over generations the perplexity of generated samples under the original model shifts upward and later generations produce sequences the original model would have assigned very low probability: the tail has moved, not merely thinned. The authors call the defects irreversible for the reason the next section makes precise, and argue that the provenance of model-generated content will matter and that data about genuine human interactions becomes more valuable as generated text spreads. (The March 2025 author correction fixed a notation slip in the theoretical-intuition section; the findings are unchanged.)

### The mathematics: finite sampling is a Wright–Fisher process

Strip away the neural network. Let the truth be a distribution p over V categories, and let the "model" be the empirical distribution of n samples. Resample n points from the model, refit, repeat. This is the Wright–Fisher model of genetic drift with V alleles and population n, and it has three textbook properties.

1. **Each probability is a martingale.** E[p̂_i(g+1) | p̂(g)] = p̂_i(g). On average nothing moves — which is why the expected variance is preserved in Shumailov's Gaussian case, and why tail *mass* is a poor collapse monitor (we return to this).
2. **Extinction is absorbing.** A category with current probability p gets zero draws in n samples with probability (1 − p)^n ≈ e^(−np). Once it has zero draws its fitted probability is zero and it is never sampled again. For the truth in `code/main.py` (Zipf with exponent 1.1 over 200 categories, n = 2000) the rarest category has p = 0.00063, so n·p = 1.25 and it dies in a single resample with probability 0.286; the expected number of categories lost in the very first fit from real data is Σ_i (1 − p_i)^n = 19.4. The simulator measured 0.240 (48 of 200 trials) and 19.2, within sampling error.
3. **Entropy is a supermartingale.** H is strictly concave, so by Jensen's inequality E[H(p̂(g+1)) | p̂(g)] ≤ H(p̂(g)). The first-order size of the expected drop is the Miller–Madow bias of the plug-in entropy estimator, (K − 1)/(2n) nats or (K − 1)/(2n ln 2) bits, where K is the number of categories still alive. With K = 184 alive after generation 0 and n = 2000 that is 0.0648 bits per generation; the simulated mean drop from generation 0 to 1 was 0.0741 bits (ratio 1.14). The formula assumes n·p_i ≫ 1 for every category; categories sitting at n·p ≈ 1–3, which is where this tail lives, lose a little more than 1/(2n) nats each, so the first-order number is a floor rather than an estimate. As K shrinks the expected drop shrinks with it, which is why collapse curves flatten instead of crashing.

Because each probability is a martingale, the sum over the tail is a martingale too. In the default run the tail mass (categories of rank 101–200) was 0.088 at generation 0 and 0.085 at generation 20 under the replace regime, essentially unchanged, while the number of tail categories still present fell from 85 to 12. The mass did not leave the tail; it piled onto a dozen survivors. A dashboard tracking "share of rare content" would have shown nothing. A dashboard tracking "number of distinct rare items" would have shown collapse by generation 4.

| Quantity (default run, seed 11) | Truth | Gen 0 | Replace, gen 20 | Accumulate, gen 20 | Mix ρ = 0.2, gen 20 |
|---|---|---|---|---|---|
| Entropy (bits) | 5.567 | 5.460 | 4.657 (−16.3%) | 5.410 (−2.8%) | 5.395 (−3.1%) |
| Extinct categories (of 200) | 0 | 16 | 141 | 16 | 45 |
| Tail categories alive (of 100) | 100 | 85 | 12 | 85 | 61 |
| Tail mass (rank > 100) | 0.090 | 0.088 | 0.085 | 0.080 | 0.093 |
| Total variation to truth | 0 | 0.090 | 0.318 | 0.108 | 0.132 |
| Expected distinct in 100 draws | 44.0 | 42.6 | 33.2 | 42.2 | 42.3 |

The continuous version shows late collapse. Fit a Gaussian by sample mean and unbiased sample variance to n = 25 points, resample, repeat. The unbiased estimator makes the variance a martingale — its expectation is exactly 1 at every generation — yet the chain converges to zero variance almost surely: a non-negative martingale converges, and because each step's increment has non-zero spread unless the variance is already zero, zero is the only place it can settle. In 200 simulated chains the median standard deviation fell to 0.59 by generation 20 and 36.0% of chains had already dropped below 0.5, while the mean variance was 1.23 (noisy, and exactly 1 on average). Run `--generations 200` and the median is 0.018 with 97.0% of chains below 0.5. "Preserved in expectation" is not "preserved".

### What prevents collapse

**Accumulate, do not replace.** Gerstgrasser et al. (arXiv:2404.01413, 1 April 2024, 14 authors) asked whether collapse is inevitable and answered no: if each generation is trained on the original real data plus every earlier synthetic generation, rather than on the latest synthetic generation alone, collapse does not occur across language models, diffusion models and VAEs, and in a linear-model setting the test error has a finite upper bound independent of the number of iterations. The mechanism in the simulator is transparent. The real generation-0 sample never leaves the pool, so any category it contained can never reach zero count; extinct stayed at 16 for all 20 generations, entropy loss stayed at 2.8%, and total variation drifted only from 0.090 to 0.108. The cost is that the real data's share of the pool shrinks as 1/(G + 1), so the bound is loose, and the pool keeps growing.

**Keep a fraction of real data every generation.** Seddik et al. (arXiv:2404.05090, 7 April 2024) analysed recursive training with a statistical model and showed that collapse cannot be avoided when training solely on synthetic data, but that when real and synthetic data are mixed there is a maximal synthetic fraction below which collapse can eventually be avoided. In the simulator a fresh real fraction ρ = 0.2 each generation kept total variation near 0.13 and let extinct categories be resurrected (the count hovered between 35 and 45 instead of climbing); ρ = 0.05 lost 8.2% of entropy and 92 categories; ρ = 1 is repeated sampling from the truth and stays within sampling noise (TV between 0.083 and 0.103). The maximal fraction is not a universal constant: at n = 500 the same ρ = 0.2 lost 14.5% of entropy and 123 categories, because the real slice was 100 samples and could not cover the tail. Dohmatob et al. (ICML 2024, arXiv:2402.07043) reach the same picture through scaling laws: synthetic data changes the scaling exponent, and mixing in human data produces delayed "grokking" rather than a smooth curve.

**Filter and verify — but know what the filter removes.** Lesson 05 showed that the filter *is* the model in a STaR or ReST-EM loop. A correctness filter stops garbage from entering the pool, and provenance plus filtering is the defence the Nature paper asks the field to take seriously. It does not restore the tail: a verifier that keeps only correct answers also keeps only the answer *styles* the current model produces, and selection on a correctness criterion is itself a sampling step with its own extinction probability for rare-but-correct strategies. Filters guard quality; they guard diversity only if asked to.

**Diversity as an objective.** Quality-diversity archives (Darwin Gödel Machine, Phase 15 · 04; Hyperagents and the Red Queen Gödel Machine, Lesson 10) keep stepping-stones alive precisely because the archive refuses to let a niche go extinct. The Red Queen machine's co-evolving evaluators are a diversity mechanism for the judge as much as for the agent. Novelty bonuses, temperature control at generation time and explicit coverage targets per category all amount to the same thing: making p̂_i = 0 expensive.

**Regenerate from source.** Nothing above resurrects a category that is already extinct from the data except real data. "Irreversible" in the Nature paper means exactly this: if generation 9 is all jackrabbits, the fix is to go back to the archive of real text, not to prompt generation 9 harder. A loop should always be able to rebuild its pool from tagged sources.

### Collapse inside RSI loops specifically

The simulator's "model" is a histogram. The loops in this phase collapse through the same arithmetic in less obvious clothing.

- **Self-play mode collapse (Lesson 04).** A policy whose only opponent is itself experiences an opponent distribution it generated. If a strategy is never played, the response to it is never learned, and play narrows to a cycle. League training with pools of historical opponents (AlphaStar, Vinyals et al., Nature 2019) is the accumulate regime applied to opponents.
- **Curriculum narrowing (Lesson 07).** A proposer rewarded for tasks near the solver's frontier is sampling from the solver's own distribution over task types. Absolute Zero's learnability reward (arXiv:2505.03335) favours intermediate solve-rates, which is a diversity device — it penalises both the trivial and the impossible — but it does not by itself stop all tasks drifting into one family. R-Zero (arXiv:2508.05004) and Agent0 (arXiv:2511.16043) report gains over a handful of iterations; a collapse monitor asks what the distinct-task count does over fifty.
- **Judge-induced style collapse (Lesson 06).** When the same model is actor and judge (Yuan et al., arXiv:2401.10020), whatever surface features the judge rewards are amplified in the next generation and rewarded again. Meta-Rewarding's length control (Wu et al., arXiv:2407.19594) is a patch for the single most visible collapsed feature. Lesson 14 treats the general case as Goodhart inside the loop.
- **Sharpening without learning.** Yue et al. (NeurIPS 2025 oral, arXiv:2504.13837) found that models trained with RL on verifiable rewards beat their base models at pass@1 but lose to them at large k: the base model could already solve the problems, and RL moved probability mass onto the paths it already preferred. That is the finite-sampling picture — pass@1 up, support down — and it is why **pass@k at large k** is the diversity monitor this lesson's figure is named after.

The pass@k algebra is the simulator's distinct-count metric. For one task, pass@k = 1 − (1 − p)^k where p is the per-sample success probability. For a distribution over V categories, the probability that category i appears at least once in k draws is 1 − (1 − p_i)^k, and summing over i gives the expected number of distinct categories in k draws. A model can keep its head (pass@1) while its support (distinct@k) shrinks: in the default run distinct@100 fell from 42.6 to 33.2 while tail mass, the martingale, stayed put. Distinct-n on generated text, type-token ratios and "how many unique proof strategies among 100 samples" are the same measurement in other units.

### Policy: what a loop must record and cap

The engineering response is procedural, not clever. (1) **Provenance tags** on every training example: real, synthetic-from-generation-g, filtered-by-verifier-v. Without tags you cannot compute a synthetic fraction, cannot accumulate correctly and cannot regenerate. (2) **A synthetic-fraction cap** per training run, set from an experiment like this lesson's `--real-fraction` sweep at the loop's actual n, not from a paper's constant. (3) **A diversity dashboard** with entropy, newly-missing categories, distinct@k on held-out prompts and total variation against a fixed real reference set that never enters training. (4) **A regeneration path** from tagged sources that is exercised, not merely documented. Phase 18 · 27 covers the legal and governance side of provenance; this lesson covers the statistical side. The skill file in Ship It turns the four items into a checklist.

```figure
pass-at-k
```

## Build It

### Step 1: A heavy-tailed truth and a model that is just counts

```python
import itertools, math, random

def zipf_distribution(vocab: int, exponent: float) -> list[float]:
    weights = [1.0 / (rank ** exponent) for rank in range(1, vocab + 1)]
    total = sum(weights)
    return [w / total for w in weights]

def sample_counts(probs, n: int, rng: random.Random) -> list[int]:
    counts = [0] * len(probs)
    cum = list(itertools.accumulate(probs))
    for idx in rng.choices(range(len(probs)), cum_weights=cum, k=n):
        counts[idx] += 1
    return counts

def fit(counts, smoothing: float = 0.0) -> list[float]:
    total = sum(counts) + smoothing * len(counts)
    return [(c + smoothing) / total for c in counts]
```

The model is the empirical distribution. With `smoothing=0` a category with zero counts has probability zero and extinction is absorbing; with smoothing it never dies, but the mass it gets back is uniform rather than the truth's shape. Try `--smoothing 0.5` and watch total variation get worse (0.456 against 0.318) even as entropy climbs above the truth.

### Step 2: The recursive loop in three regimes

```python
def run_regime(regime, truth, cfg, gen0_counts, rng):
    pool = list(gen0_counts)                 # the real sample every regime starts from
    model = fit(pool, cfg.smoothing)
    history = [measure(0, model, pool, truth, cfg)]
    n_real = round(cfg.real_fraction * cfg.samples)
    for g in range(1, cfg.generations + 1):
        if regime == "replace":
            data = sample_counts(model, cfg.samples, rng)
        elif regime == "accumulate":
            pool = [a + b for a, b in zip(pool, sample_counts(model, cfg.samples, rng))]
            data = pool
        else:                                # mix: rho fresh real + (1 - rho) synthetic
            real = sample_counts(truth, n_real, rng)
            synthetic = sample_counts(model, cfg.samples - n_real, rng)
            data = [a + b for a, b in zip(real, synthetic)]
        model = fit(data, cfg.smoothing)
        history.append(measure(g, model, data, truth, cfg))
    return history
```

All three regimes start from the same generation-0 sample, so differences after that are the regime, not the seed.

### Step 3: Monitors per generation

```python
def entropy_bits(probs):
    return -sum(p * math.log2(p) for p in probs if p > 0.0)

def tail_alive(counts, tail_rank):
    return sum(1 for c in counts[tail_rank:] if c > 0)

def total_variation(p, q):
    return 0.5 * sum(abs(a - b) for a, b in zip(p, q))

def expected_distinct(probs, k):             # pass@k algebra, summed over categories
    return sum(1.0 - (1.0 - p) ** k for p in probs)

def extinction_probability(p, n):            # exact; e**(-n*p) is the approximation
    return (1.0 - p) ** n

def miller_madow_drop_bits(k_alive, n):      # first-order expected entropy loss per refit
    return (k_alive - 1) / (2.0 * n * math.log(2.0))
```

`total_variation` needs the truth, which a real loop does not have; the production substitute is a frozen real reference set that never enters training.

### Step 4: Late collapse in a Gaussian

```python
import statistics

def gaussian_chain(n: int, generations: int, rng: random.Random) -> list[float]:
    mu, sd = 0.0, 1.0
    out = [sd]
    for _ in range(generations):
        xs = [rng.gauss(mu, sd) for _ in range(n)]
        mu, sd = statistics.fmean(xs), statistics.stdev(xs)   # unbiased variance: a martingale
        out.append(sd)
    return out
```

Ten lines, no tail at all, and the variance still goes to zero: late collapse needs no heavy tail, only a finite sample.

## Use It

`code/main.py` runs the discrete loop under all three regimes from the same generation-0 model and prints a per-generation table for each (entropy, entropy lost, tail mass, tail categories alive, extinct categories, total variation, expected distinct in k draws), a comparison table at the final generation, theory checks (exact and e^(−np) extinction probability against Monte-Carlo, expected extinct count, Miller–Madow drop against the simulated drop), the Gaussian late-collapse table, and a HEADLINE assembled from the computed numbers.

Flags: `--generations` (default 20), `--samples` n per generation (2000), `--vocab` V (200), `--zipf` exponent (1.1), `--regime replace|accumulate|mix|all`, `--real-fraction` ρ for the mix regime (0.2), `--tail-rank` (100), `--k` draws for the distinct count (100), `--smoothing`, `--trials` for the Monte-Carlo checks (200), `--cont-samples` for the Gaussian variant (25), `--seed` (11) and `--out report.json`.

What to look at: under replace, watch `tail alive` fall long before `tail mass` moves; under accumulate, watch `extinct` freeze at its generation-0 value; under mix, watch `extinct` fluctuate instead of climbing, because fresh real data resurrects categories. In the theory block, compare the simulated extinction rate with (1 − p)^n and note that the Miller–Madow number is a floor. In the Gaussian block, compare `median sd` with `mean var`.

## Ship It

This lesson produces `outputs/skill-synthetic-data-mix-policy.md`. Given a description of a self-training or data-generation loop (sources, generation procedure, filters, training schedule), it produces a mix policy: a provenance tag schema, a synthetic-fraction cap derived from a stated experiment at the loop's own n, a diversity dashboard specification with the four monitors from this lesson and a stop condition for each, and a regeneration-from-source procedure. It refuses policies that cap the fraction without stating how the cap was measured, dashboards that track tail mass but not distinct counts, and loops with no path back to real data.

## Exercises

1. **(Easy)** Run `python3 main.py --regime replace --generations 100`. Read off the generation at which `tail alive` first drops below 10 of 100 and the entropy lost at generation 100. Why does the entropy curve flatten instead of continuing at the early rate? Use the Miller–Madow expression in your answer.

2. **(Medium)** Run `python3 main.py --samples 500` and `python3 main.py --samples 8000`. For each, compare the theory block's expected extinct count after one resample with the simulated mean, then explain why the mix regime at ρ = 0.2 fails at n = 500 but is almost perfect at n = 8000. What does this say about quoting a "maximal synthetic fraction" without stating n?

3. **(Medium)** Sweep `--real-fraction` over 0.05, 0.1, 0.2 and 0.5 at seeds 11, 3 and 5, recording total variation and extinct categories at generation 20. Find the smallest ρ for which TV stays below 0.15 at all three seeds. Write one paragraph relating your threshold to Seddik et al.'s maximal synthetic fraction and to Gerstgrasser et al.'s accumulate result, which has no ρ at all.

4. **(Medium)** Run `python3 main.py --smoothing 0.5`. Entropy under replace now exceeds the truth and `extinct` stays low, yet total variation is worse than without smoothing. Explain this in terms of Shumailov's functional approximation error, and say which monitor on a real dashboard would have caught it.

5. **(Hard)** Add a fourth regime, `filter`, that samples from the model but keeps only categories with truth-rank ≤ 50 ("verified correct") before refitting. Measure entropy, extinct and distinct@100 across 20 generations and compare with replace. Then write a two-component Gaussian-mixture version of Step 4 using a few hard-EM steps and report which happens first: the loss of the second mode or the shrinking of each mode's variance.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Model collapse | "the model gets worse on its own data" | A degenerative process in which generations trained on earlier generations' output lose information about the true distribution; tails first, then variance (Shumailov et al., Nature 2024) |
| Early collapse | "it forgets the rare stuff" | Loss of low-probability categories and tails; measured by extinct count, tail-alive count and distinct@k |
| Late collapse | "everything looks the same" | Convergence to a distribution with far smaller variance than the original; measured by variance, entropy and TV against a real reference |
| Statistical approximation error | "sampling noise" | Information lost because a finite sample never reproduces a distribution; sufficient on its own to cause collapse |
| Wright–Fisher process | "genetic drift" | Resampling n items from the current frequencies each generation; frequencies are martingales and extinction is absorbing |
| Extinction probability | "the rare class disappears" | P[zero draws in n samples] = (1 − p)^n ≈ e^(−np); absorbing when the model has no smoothing |
| Miller–Madow bias | "plug-in entropy is biased low" | E[H(p̂)] ≈ H(p) − (K − 1)/(2n) nats; the first-order expected entropy loss per refit |
| Accumulate regime | "keep all the data" | Train on the original real data plus every synthetic generation; bounded error (Gerstgrasser et al. 2024) |
| Maximal synthetic fraction | "don't use more than X% synthetic" | The synthetic share above which mixing real data no longer prevents collapse (Seddik et al. 2024); depends on n and on the tail |
| pass@k / expected distinct | "diversity score" | 1 − (1 − p)^k per item; summed over categories it is the expected number of distinct outcomes in k draws; falls when support shrinks even if pass@1 rises |

## Further Reading

- [Shumailov et al. — AI models collapse when trained on recursively generated data (Nature 631:755–759, 2024)](https://www.nature.com/articles/s41586-024-07566-y) — the primary source; read the theoretical-intuition section for the Gaussian martingale argument.
- [Author Correction (Nature, 21 March 2025), via PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11981929/) — a notation fix in the theory section; worth knowing it exists before someone cites it as a retraction.
- [Shumailov et al. — The Curse of Recursion: Training on Generated Data Makes Models Forget (arXiv:2305.17493)](https://arxiv.org/abs/2305.17493) — the 2023 preprint with the fuller experimental appendix.
- [Gerstgrasser et al. — Is Model Collapse Inevitable? Breaking the Curse of Recursion by Accumulating Real and Synthetic Data (arXiv:2404.01413)](https://arxiv.org/abs/2404.01413) — the accumulate result and the linear-model bound.
- [Seddik et al. — How Bad is Training on Synthetic Data? A Statistical Analysis of Language Model Collapse (arXiv:2404.05090)](https://arxiv.org/abs/2404.05090) — the maximal-synthetic-fraction argument.
- [Dohmatob et al. — A Tale of Tails: Model Collapse as a Change of Scaling Laws (ICML 2024, arXiv:2402.07043)](https://arxiv.org/abs/2402.07043) — collapse expressed as a shift in the scaling exponent.
- [Yue et al. — Does Reinforcement Learning Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model? (NeurIPS 2025, arXiv:2504.13837)](https://arxiv.org/abs/2504.13837) — pass@k at large k as a diversity monitor in a production RL setting.
- [Chen, Wang, Qu — Recursive Self-Improvement in AI: From Bounded Self-Refinement to Autonomous Research Loops (arXiv:2607.07663)](https://arxiv.org/abs/2607.07663) — collapse dynamics as a structural limit on open-ended RSI.
