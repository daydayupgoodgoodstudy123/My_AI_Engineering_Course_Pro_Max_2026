# Self-Play: The One Loop That Already Closed

> AlphaZero (Silver et al., Science 2018) is the one recursive improvement loop that has fully closed: the policy generated its own training games, the rules of Go, chess and shogi scored them without error, and the opponent was always the current self. The recipe reached silver-medal level at IMO 2024 once the Lean proof checker replaced the rules: AlphaProof with AlphaGeometry 2 scored 28 of 42, one point short of gold (DeepMind, Jul 25, 2024; Nature, Nov 12, 2025). This lesson rebuilds the loop in stdlib Python and breaks the one assumption that made it work: a tabular self-play learner climbs from 17.0% to 98.5% non-loss against a minimax-optimal opponent in 40,000 self-generated games; with 20% of its results flipped by the verifier it plateaus at 74.5%.

**Type:** Build
**Languages:** Python (stdlib, tic-tac-toe self-play simulator with a minimax oracle)
**Prerequisites:** Phase 09 · 04 (Q-learning), Phase 09 · 12 (AlphaZero), Lesson 01 of this phase
**Time:** ~75 minutes

## Learning Objectives

- Describe the four parts of the AlphaZero loop and why nothing outside it supplies tasks, labels or scores.
- State the three closure conditions and test a proposed loop against them.
- Score AlphaProof (2024) against the conditions and name the ones it satisfies only partially.
- Implement generational self-play with a tabular Q-learner and evaluate it against a minimax oracle.
- Diagnose cycling, forgetting and exploitability from an exploit-against-archive column.
- Predict, then measure, what a corrupted verifier does to a closed loop.

## The Problem

Lesson 01 gave you the ladder from self-refinement to RSI. Every rung above the bottom asks where the training signal comes from once humans stop supplying it. For most systems in this phase the answer is a judge we hope is good enough: a reward model, an LLM grader, a rubric. Lesson 14 is about what goes wrong then.

One loop closed years before the current wave, with no judge at all. AlphaZero (Silver et al., Science 2018; preprint arXiv:1712.01815, Dec 2017) started from random weights, played itself, scored each game with the rules and trained on the result; after hours of self-play in chess and shogi and 13 days in Go on 2018 hardware it beat the strongest engines of its day. This lesson names the properties of games that made closure possible, shows they are conditions rather than conveniences, and demonstrates in code what the same loop does when one is removed.

## The Concept

### Anatomy of the loop

Four parts. A policy-and-value network proposes moves. A generator plays the network against itself, with Monte-Carlo tree search as a policy-improvement operator at every move. A verifier, the rules of the game, assigns z in {+1, 0, -1} to each finished game, the only reward that enters the system. A trainer fits the network to the search-improved moves and the outcome, and the new network becomes the next generator. Absent: human data, so no ceiling set by the best human; a learned reward, so nothing to hack; a curriculum designer, because the opponent is always exactly as strong as you are. Phase 09 · 12 covers search and network; in the Build the network becomes a Q-table and the search becomes epsilon-greedy exploration. The loop's logic does not change.

### Three closure conditions

| Condition | What it requires | How games satisfy it | What fails without it |
|---|---|---|---|
| 1. Verifier that cannot be gamed | A scoring function the policy cannot influence, with no false positives | The rules decide win, draw, loss | Goodhart: the policy learns the verifier's errors (Lesson 14) |
| 2. Unbounded tasks at the right difficulty | New tasks keep appearing at the learner's frontier | Opponent = current self; self-play never runs out and auto-adjusts | Saturation: a fixed pool is memorised and gains stop (ReST-EM, Lesson 05) |
| 3. No train/target shift | The thing trained on is the thing evaluated | Chess is chess | Drift: training on your own outputs while the target moves away (Lesson 16) |

These are conditions, not conveniences: remove one and the loop still runs, still produces data, still updates weights, and stops improving toward the target. Condition 1 is the sharp one, and the Build is organised around it: a flag dials the rules from perfect to corrupt.

### From games to proofs: AlphaProof

DeepMind announced AlphaProof on Jul 25, 2024 and published the method as Hubert et al., Nature, Nov 12, 2025. The Lean proof assistant has the same property as game rules: a proof that type-checks is correct, with no appeal. An AlphaZero-style agent proposes proof steps, Lean verifies them, and the verified result is the reward.

Condition 2 was the engineering problem. A fine-tuned Gemini model autoformalised "around one million" informal problems (DeepMind blog); Silver and Sutton (Apr 2025) give the scale as around a hundred thousand human-written formal proofs to start from, after which the RL algorithm "subsequently generated a hundred million more". The Nature paper adds Test-Time RL, which generates and learns from millions of variants of a hard target problem at inference time. At IMO 2024 AlphaProof solved two algebra problems and one number-theory problem, including the hardest of the contest (solved by five of 609 contestants), and AlphaGeometry 2 solved the geometry problem in 19 seconds: four of six, 28 of 42 points, gold starting at 29.

Scored against the table: condition 1 holds fully; condition 2 partially, because the task supply is an autoformalised human corpus rather than an endless opponent; condition 3 partially, because the contest problems were translated into Lean by hand and proof search is not the same activity as choosing what to prove. AlphaProof is closed in the verifier dimension and bounded in the other two.

### The Era of Experience thesis and its limit

Silver and Sutton, "Welcome to the Era of Experience" (Apr 2025; a preprint chapter of *Designing an Intelligence*, MIT Press), argue that learning from human data is saturating and that agents will next learn predominantly from their own experience, with rewards grounded in the environment rather than in human prejudgement. It is the thesis that self-play generalises. The objection is narrow: grounded rewards are condition 1. Games and formal proofs have them; code has a partial version (tests, which can be edited or over-fitted); research, writing and taste do not. Chen, Wang and Qu's survey of 1,250 RSI papers (arXiv:2607.07663, Jul 2026) found that demonstrated self-improvement follows a verification hierarchy: formal verifiers, then execution and tests, then judges and rubrics, then intrinsic self-assessment. Self-play sits on the top rung; most of this phase lives lower down.

### Failure modes inside games

Even with all three conditions satisfied, self-play has its own pathologies. Intransitivity: in a game with rock-paper-scissors structure, beating your parent does not imply beating your grandparent; Balduzzi et al. (ICML 2019, arXiv:1901.08106) showed that self-play against the latest self cycles in non-transitive games, and Czarnecki et al. (NeurIPS 2020, arXiv:2004.09468) argued that real games are spinning tops with a wide non-transitive belt. Forgetting: strategies that beat older generations are unlearned when only the newest generation is ever faced. Exploitability: a best-response opponent finds the hole the self-play distribution never visited.

The fix is population-based training, sampling opponents from an archive of past generations (PSRO, Lanctot et al., NeurIPS 2017, arXiv:1711.00832; the AlphaStar league, Vinyals et al., Nature 2019). The Build exposes it as `--population k` and reports an exploit column, the highest loss rate against any archived generation. Tic-tac-toe is nearly transitive and a Q-table never forgets, so in a clean run that column stays near zero; when it stops being zero, the cause is the verifier.

### What breaks when the verifier is corrupted

Flip the announced winner with probability p. A win is worth 1 - 2p in expectation, a loss -(1 - 2p), and a draw, which cannot be flipped, exactly 0. At p = 0.2 the ordering is preserved, so you might predict only slower learning. The Build shows something worse: the loop plateaus or regresses, and older generations start beating newer ones.

The mechanism is the bootstrap. Q-learning updates toward r + gamma * max over a' of Q(s', a'), and a maximum over noisy estimates is biased upward (the maximisation bias behind Double Q-learning, van Hasselt, NeurIPS 2010). The safe drawing line is worth exactly 0 forever; risky lines that minimax refutes collect occasional false +1s, float above 0, and the greedy policy picks them. The loop has learned the verifier's mistakes, not the game. In Lessons 05 and 07 the verifier is a final-answer check or a code executor, close to exact; in Lesson 06 it is the model itself; Lesson 14 asks how far from exact a verifier can be before the loop stops improving.

```figure
tree-of-thoughts
```

## Build It

### Step 1: An environment with a minimax oracle

Tic-tac-toe has 5,478 reachable positions, 4,520 of them undecided. A memoised minimax solves all of them in milliseconds and gives you something AlphaZero never had: an exact verifier of every move, not only of finished games. `value(b)` is the outcome for the player to move under perfect play; a move is worth minus the value of the position it leads to.

```python
from typing import Dict, List, Optional, Tuple

EMPTY, X, O = 0, 1, 2
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
Board = Tuple[int, ...]

def player_to_move(b: Board) -> int:
    return X if b.count(X) == b.count(O) else O

def legal_moves(b: Board) -> List[int]:
    return [i for i, c in enumerate(b) if c == EMPTY]

def play(b: Board, m: int) -> Board:
    cells = list(b)
    cells[m] = player_to_move(b)
    return tuple(cells)

def winner(b: Board) -> Optional[int]:
    for a, c, d in LINES:
        if b[a] != EMPTY and b[a] == b[c] == b[d]:
            return b[a]
    return None if EMPTY in b else 0

memo: Dict[Board, int] = {}

def value(b: Board) -> int:                 # for the player to move: +1 / 0 / -1
    w = winner(b)
    if w is not None:
        return 0 if w == 0 else -1          # a decided game was won by the previous mover
    if b not in memo:
        memo[b] = max(-value(play(b, m)) for m in legal_moves(b))
    return memo[b]

empty = (EMPTY,) * 9
print("value of the empty board:", value(empty), "| positions solved:", len(memo))
print("first moves that hold the draw:", [m for m in legal_moves(empty) if -value(play(empty, m)) == 0])
trap = (X, X, EMPTY, O, O, EMPTY, EMPTY, EMPTY, EMPTY)   # X to move
print("move values in the trap position:", {m: -value(play(trap, m)) for m in legal_moves(trap)})
```

Output: the empty board is worth 0, 4,520 positions are solved, all nine first moves hold the draw, and in the trap position square 2 wins (+1), square 5 blocks (0) and every other move loses (-1). Perfect play never loses, so non-loss rate against minimax has a known ceiling of 100%.

### Step 2: A tabular Q-learning agent

The agent keeps `Q[(board, move)]` from the point of view of whoever is to move, so one table serves both colours. When the agent gets to move again, the earlier move is pulled toward `gamma * max Q(next, .)`; when the game ends, it is pulled toward the verifier's announcement, +1, 0 or -1. Run from `code/`:

```python
import random
from main import QAgent, start_board, play

agent = QAgent(alpha=0.4, gamma=1.0, epsilon=0.3)
rng = random.Random(0)
s = start_board()
a = agent.choose(s, rng)                       # eps-greedy; every Q(s, .) is 0, so this is a random pick
s2 = play(play(s, a), 4 if a != 4 else 0)      # we move, the opponent replies, it is our turn at s2
agent.update(s, a, agent.gamma * agent.best_value(s2))   # bootstrap: r + gamma * max_a' Q(s2, a')
print("after the bootstrap:", agent.q_value(s, a))
agent.update(s, a, -1.0)                       # terminal: the verifier says we lost
print("move", a, "after one reported loss:", round(agent.q_value(s, a), 3))
```

The bootstrap leaves the value at 0.0 because nothing downstream has been learned yet; one reported loss moves it to -0.4, which is `0 + 0.4 * (-1 - 0)`. Everything the agent will ever believe about the game is built from these two lines, which is why the second one being honest matters.

### Step 3: Generational self-play

A generation is a block of games after which the learner's table is frozen as a snapshot. Half the games are pure self-play, both seats updating one table; the other half are against a frozen opponent from the pool: the previous generation when `population=1`, the last k when `population=k`. Frozen opponents keep 10% random moves so the learner sees variety.

```python
import random
from main import LoopConfig, QAgent, train_generation

cfg = LoopConfig(generations=3, episodes=2000, seed=11)
rng, noise_rng = random.Random(cfg.seed), random.Random(cfg.seed + 1)
learner = QAgent(alpha=cfg.alpha, gamma=cfg.gamma, epsilon=cfg.epsilon)
frozen = []
for gen in range(cfg.generations):
    pool = frozen[-cfg.population:]            # generation g-1 only (population=1), or a pool of k
    train_generation(learner, pool, cfg, rng, noise_rng)
    frozen.append(learner.snapshot())          # freeze: this becomes the next generation's opponent
    print(f"gen {gen}: trained vs {len(pool)} frozen opponent(s); {len(learner.q):,} (state, move) pairs")
```

Generation 0 trains against nobody but itself and ends with 5,270 state-action pairs; generations 1 and 2 add the frozen parent and reach 6,673 and 7,560. The table carries over between generations, as AlphaZero's network does; snapshots exist so the archive can be evaluated against.

### Step 4: Evaluate against the oracle, then corrupt the verifier

Self-play's own win rate is useless as a progress metric, since the opponent improves too. The oracle gives three honest ones: non-loss rate against a minimax player that breaks ties randomly, the share of the learner's moves minimax rates optimal, and loss rate against every archived generation. `--verifier-noise p` makes the rules lie: with probability p a decided game is announced with the wrong winner, consistently for both seats.

```python
import random
from main import LoopConfig, run_loop, verifier_report

for noise in (0.0, 0.2):
    hist = run_loop(LoopConfig(generations=4, seed=11, verifier_noise=noise))
    print(f"noise {noise:.1f}: non-loss vs minimax by generation:",
          [f"{s.non_loss_vs_minimax:.1%}" for s in hist])
rng = random.Random(1)
print("share of X-wins reported as O-wins at p=0.2:",
      sum(verifier_report(1, 0.2, rng) == 2 for _ in range(10000)) / 10000)
```

With a clean verifier the first four generations read 17.0%, 75.0%, 85.0%, 90.5%. With 20% of results flipped they read 44.0%, 43.5%, 43.0%, 46.5%: the noisy loop starts better by luck and then does not move. The flip check prints 0.2058. Both runs use the same seed and the same games; the only difference is whether the verifier told the truth.

## Use It

`code/main.py` runs the loop twice and prints both in one report: RUN A with a clean verifier, RUN B with the verifier corrupted at `--verifier-noise` (default 0.2). Flags: `--generations` (default 8), `--episodes` per generation (default 5,000), `--population` (1 = previous generation only; k = pool of the last k snapshots), `--seed` (default 11), `--eval-games` (default 200 per opponent) and `--out stats.json`.

Read `non-loss` first: in RUN A it climbs 17.0%, 75.0%, 85.0%, 90.5%, 96.5%, 97.0%, 95.0%, 98.5%, first passing 95% at generation 4 after 25,000 self-generated games, and `optimal` reaches 99.7%; `exploit` is 0.0% in every clean generation. In RUN B `non-loss` ends at 74.5%, `optimal` at 94.0%, and `exploit` reads 50.0% from generation 5 onward, meaning a past snapshot wins every game as one colour; averaged over generations it is 29.5% against 0.0%. The noisy loop also learned more table entries (14,309 versus 12,797) and plays worse. The HEADLINE is generated from the numbers: `--verifier-noise 0.05` reaches 100.0% at generation 7; `--verifier-noise 0.5` ends at 22.0% with an averaged exploit of 54.1%; `--episodes 1000` leaves the clean loop at 68.5%, which says condition 2 is load-bearing too.

## Ship It

This lesson produces `outputs/skill-closure-conditions-checklist.md`. Given any loop in which a system generates its own training signal, it scores each closure condition 0-2 with evidence, checks intransitivity, forgetting and exploitability against the full archive rather than the parent, and returns a verdict of closed, bounded or open, naming the condition that fails first. It hard-rejects verifiers that are models trained on the loop's own output and improvement claims measured only against the previous generation.

## Exercises

1. Run `python3 main.py` and read both tables. At which generation does the clean run first reach 95% non-loss, and what is the noisy run's peak? Explain how `optimal` can be 94.0% while `non-loss` is 74.5%. (Hint: one wrong move in a drawn game is a loss.)

2. Run `python3 main.py --verifier-noise 0.05` and `python3 main.py --verifier-noise 0.5`, then tabulate final non-loss and averaged exploit against p for p in {0.0, 0.05, 0.2, 0.5}. Where does the loop stop reaching the ceiling, and how does that relate to the expected win value 1 - 2p?

3. Run `python3 main.py --population 3` and `python3 main.py --population 7` for `--seed 3`, `--seed 7` and `--seed 11`. Record the noisy run's averaged exploit each time. Does the pool help every time? Say in two sentences why one seed is not evidence either way, then average across seeds.

4. Change `verifier_report` so that corruption is optimistic: with probability p a loss is reported as a win, never the reverse. Predict what happens to the draw-versus-attack trade-off before you run it, then measure final non-loss and exploit at p = 0.2.

5. Add 8-fold symmetry canonicalisation to the Q-table key (rotations and reflections of the board, with the move index mapped the same way). Measure how many games the clean loop now needs to reach 95% non-loss, then confirm that the noisy loop's plateau does not go away. Sample efficiency and verifier integrity are different axes.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Closed loop | "It trains itself" | Tasks, labels and scores all originate inside the loop |
| Verifier | "The reward" | A scoring function the policy cannot influence; exact for rules and proof checkers, approximate for judges |
| Auto-curriculum | "It gets harder as you improve" | Task difficulty tracks the learner because the opponent is the learner |
| Train/target shift | "Train on what you test on" | Condition 3: the training game and the deployment target are the same distribution |
| Intransitivity | "Rock-paper-scissors" | A beats B and B beats C does not imply A beats C; self-play can cycle |
| Population-based training | "A league" | Training against an archive of past or specialised opponents, not only the latest self |
| Exploitability | "It has a hole" | Loss rate against a best-response or archived opponent the self-play distribution never visited |
| Maximisation bias | "Q-learning is optimistic" | A max over noisy estimates is biased upward; a noisy verifier turns this into a taste for refutable lines |
| Grounded reward | "Era of Experience" | A reward computed from the environment, not from human or model judgement; condition 1 |

## Further Reading

- [Silver et al., "A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play", Science 2018](https://www.science.org/doi/10.1126/science.aar6404) — the canonical closed loop, with training curves against Stockfish, Elmo and AlphaGo Zero.
- [Silver et al., arXiv:1712.01815](https://arxiv.org/abs/1712.01815) — the open-access preprint; the method section shows how little sits outside the loop.
- [DeepMind, "AI achieves silver-medal standard solving International Mathematical Olympiad problems", Jul 25, 2024](https://deepmind.google/discover/blog/ai-solves-imo-problems-at-silver-medal-level/) — primary source for the 28/42 result and the autoformalisation pipeline.
- [Hubert et al., "Olympiad-level formal mathematical reasoning with reinforcement learning", Nature, Nov 12, 2025](https://www.nature.com/articles/s41586-025-09833-y) — the AlphaProof method paper, including Test-Time RL.
- [Silver and Sutton, "Welcome to the Era of Experience", Apr 2025](https://storage.googleapis.com/deepmind-media/Era-of-Experience%20/The%20Era%20of%20Experience%20Paper.pdf) — the thesis that self-play generalises; read it with condition 1 in mind.
- [Balduzzi et al., "Open-ended Learning in Symmetric Zero-sum Games", ICML 2019, arXiv:1901.08106](https://arxiv.org/abs/1901.08106) — why self-play cycles in non-transitive games and what population objectives fix.
- [Czarnecki et al., "Real World Games Look Like Spinning Tops", NeurIPS 2020, arXiv:2004.09468](https://arxiv.org/abs/2004.09468) — the geometry of transitive strength plus a non-transitive belt.
- [Chen, Wang and Qu, "Recursive Self-Improvement in AI", arXiv:2607.07663](https://arxiv.org/abs/2607.07663) — the verification hierarchy that puts self-play on the top rung.
