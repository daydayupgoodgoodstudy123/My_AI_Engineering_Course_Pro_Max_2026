"""Experience streams and skill libraries — stdlib Python.

An agent solves key/door/tool tasks in small gridworlds over a stream of episodes.
A horizon-limited planner searches over primitive actions; successful trajectories
are abstracted into typed macros (skills) that the planner can call, which lowers
the effective search depth. A poisoned skill (a concrete recording that only works
where it was learned) shows why a library needs a validation gate: held-out replay
before admission, live telemetry and retirement afterwards. Phase 20 · Lesson 12.
Usage: python3 main.py [--episodes 48] [--layouts 8] [--gate on|off] [--poison on|off]
       [--gate-k 3] [--max-skills 12] [--horizon 6] [--budget 22] [--rank cost|rate] [--seed 11]
See docs/en.md
"""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Optional

DEFAULT_SEED = 11
WIDTH, HEIGHT = 9, 7
WALL_COL = 4
MOVES = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
INTERACTIONS = ("PICKUP", "USE", "OPEN")
PRIMITIVES = ("N", "S", "E", "W") + INTERACTIONS
EXPANSION_BUDGET = 400          # planner node expansions per decision
RETIRE_MIN_USES = 3             # live uses before telemetry can retire a skill
RETIRE_MAX_RATE = 0.5           # retire when live success rate is below this
POISON_PRIOR_USES = 8           # imported record: "ran 8 times, 8 successes"
BLOCKS = 4

Cell = tuple[int, int]
Segment = tuple[str, str]
SHORT = {("key", "PICKUP"): "key", ("door", "USE"): "door", ("pick", "PICKUP"): "pick",
         ("rock", "USE"): "rock", ("chest", "OPEN"): "chest"}
SINGLE_NAMES = {("key", "PICKUP"): "fetch_key", ("door", "USE"): "unlock_door",
                ("pick", "PICKUP"): "fetch_pick", ("rock", "USE"): "break_rock",
                ("chest", "OPEN"): "open_chest"}


# ----------------------------------------------------------------------------
# World
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Layout:
    index: int
    kind: str                      # "A": key>door>chest   "B": key>door>pick>rock>chest
    walls: frozenset[Cell]
    start: Cell
    door: Cell
    chest: Cell
    rock: Optional[Cell]
    items: tuple[tuple[str, Cell], ...]


@dataclass(frozen=True)
class State:
    pos: Cell
    inv: frozenset[str]
    items: frozenset[tuple[str, Cell]]
    door_open: bool = False
    rock_broken: bool = False
    chest_open: bool = False


def make_layout(rng: random.Random, index: int) -> Layout:
    """Two rooms split by a wall with one door. Even index: kind A; odd: kind B."""
    kind = "A" if index % 2 == 0 else "B"
    walls = {(x, y) for x in range(WIDTH) for y in (0, HEIGHT - 1)}
    walls |= {(x, y) for x in (0, WIDTH - 1) for y in range(HEIGHT)}
    door_row = rng.randint(1, HEIGHT - 2)
    walls |= {(WALL_COL, y) for y in range(1, HEIGHT - 1) if y != door_row}
    left = [(x, y) for x in range(1, WALL_COL) for y in range(1, HEIGHT - 1)]
    right = [(x, y) for x in range(WALL_COL + 1, WIDTH - 1) for y in range(1, HEIGHT - 1)]
    start, key = rng.sample(left, 2)
    items: list[tuple[str, Cell]] = [("key", key)]
    rock: Optional[Cell] = None
    if kind == "A":
        chest = rng.choice(right)
    else:  # chest in an alcove whose only entrance is the rock cell
        if rng.random() < 0.5:
            chest, rock, extra = (WIDTH - 2, 1), (WIDTH - 2, 2), (WIDTH - 3, 1)
        else:
            chest, rock, extra = (WIDTH - 2, HEIGHT - 2), (WIDTH - 2, HEIGHT - 3), (WIDTH - 3, HEIGHT - 2)
        walls.add(extra)
        pick = rng.choice([c for c in right if c not in (chest, rock, extra)])
        items.append(("pick", pick))
    return Layout(index, kind, frozenset(walls), start, (WALL_COL, door_row), chest, rock, tuple(items))


def initial_state(layout: Layout) -> State:
    return State(layout.start, frozenset(), frozenset(layout.items))


def passable(layout: Layout, state: State, cell: Cell) -> bool:
    if cell in layout.walls:
        return False
    if cell == layout.door and not state.door_open:
        return False
    if layout.rock is not None and cell == layout.rock and not state.rock_broken:
        return False
    return True


def adjacent(a: Cell, b: Cell) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def neighbours(c: Cell) -> list[Cell]:
    return [(c[0] + dx, c[1] + dy) for dx, dy in MOVES.values()]


def step(layout: Layout, state: State, prim: str) -> tuple[State, bool]:
    """Apply one primitive. Returns (new_state, changed). Every call costs one step."""
    if prim in MOVES:
        dx, dy = MOVES[prim]
        nxt = (state.pos[0] + dx, state.pos[1] + dy)
        return (replace(state, pos=nxt), True) if passable(layout, state, nxt) else (state, False)
    if prim == "PICKUP":
        for item in sorted(state.items):
            if item[1] == state.pos:
                return replace(state, inv=state.inv | {item[0]}, items=state.items - {item}), True
        return state, False
    if prim == "USE":
        if "key" in state.inv and not state.door_open and adjacent(state.pos, layout.door):
            return replace(state, door_open=True, inv=state.inv - {"key"}), True
        if ("pick" in state.inv and layout.rock is not None and not state.rock_broken
                and adjacent(state.pos, layout.rock)):
            return replace(state, rock_broken=True), True
        return state, False
    if prim == "OPEN":
        if state.pos == layout.chest and not state.chest_open:
            return replace(state, chest_open=True), True
        return state, False
    raise ValueError(prim)


def shortest_path(layout: Layout, state: State, targets: set[Cell]) -> Optional[list[str]]:
    if state.pos in targets:
        return []
    prev: dict[Cell, Optional[tuple[Cell, str]]] = {state.pos: None}
    queue = deque([state.pos])
    while queue:
        cur = queue.popleft()
        for name, (dx, dy) in MOVES.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or not passable(layout, state, nxt):
                continue
            prev[nxt] = (cur, name)
            if nxt in targets:
                path, node = [], nxt
                while prev[node] is not None:
                    node, mv = prev[node]
                    path.append(mv)
                return path[::-1]
            queue.append(nxt)
    return None


def solve_optimal(layout: Layout) -> list[str]:
    """Full breadth-first search over primitives (no horizon): the oracle route."""
    root = initial_state(layout)
    prev: dict[State, Optional[tuple[State, str]]] = {root: None}
    queue = deque([root])
    while queue:
        cur = queue.popleft()
        for prim in PRIMITIVES:
            nxt, changed = step(layout, cur, prim)
            if not changed or nxt in prev:
                continue
            prev[nxt] = (cur, prim)
            if nxt.chest_open:
                path, node = [], nxt
                while prev[node] is not None:
                    node, mv = prev[node]
                    path.append(mv)
                return path[::-1]
            queue.append(nxt)
    raise RuntimeError("layout unsolvable")


# ----------------------------------------------------------------------------
# Typed segments: the unit of abstraction ("go to the nearest X and interact")
# ----------------------------------------------------------------------------
def segment_targets(layout: Layout, state: State, seg: Segment) -> set[Cell]:
    obj, act = seg
    if act == "PICKUP":
        return {pos for kind, pos in state.items if kind == obj}
    if act == "USE":
        if obj == "door":
            if "key" not in state.inv or state.door_open:
                return set()
            anchor = layout.door
        elif obj == "rock":
            if "pick" not in state.inv or layout.rock is None or state.rock_broken:
                return set()
            anchor = layout.rock
        else:
            return set()
        return {c for c in neighbours(anchor) if passable(layout, state, c)}
    if act == "OPEN" and obj == "chest" and not state.chest_open:
        return {layout.chest}
    return set()


def run_segment(layout: Layout, state: State, seg: Segment) -> Optional[tuple[State, int]]:
    """Execute one typed segment exactly. None if not applicable here."""
    targets = segment_targets(layout, state, seg)
    if not targets:
        return None
    path = shortest_path(layout, state, targets)
    if path is None:
        return None
    for mv in path:
        state, _ = step(layout, state, mv)
    state, changed = step(layout, state, seg[1])
    return (state, len(path) + 1) if changed else None


def satisfied(state: State) -> frozenset[str]:
    flags = set(state.inv)
    if state.door_open:
        flags.add("door_open")
    if state.rock_broken:
        flags.add("rock_broken")
    return frozenset(flags)


def progress(state: State) -> int:
    score = 5 * state.chest_open + 2 * state.door_open + 2 * state.rock_broken
    score += int("key" in state.inv or state.door_open)
    score += int("pick" in state.inv or state.rock_broken)
    return score


# ----------------------------------------------------------------------------
# Skills and the library
# ----------------------------------------------------------------------------
@dataclass
class Skill:
    name: str
    segments: tuple[Segment, ...]          # declared behaviour (what the planner trusts)
    needs: frozenset[str]                  # declared preconditions
    program: Optional[tuple[str, ...]] = None   # concrete implementation; None = typed
    origin: str = ""
    uses: int = 0                          # live telemetry (observed in this run)
    successes: int = 0
    cost_total: int = 0
    wasted: int = 0
    prior_uses: int = 0                    # imported record (claims, not observations)
    prior_successes: int = 0
    prior_cost: int = 0
    origin_layout: int = -1
    origin_successes: int = 0
    status: str = "candidate"
    status_episode: int = -1
    gate_note: str = ""

    def rate(self) -> float:
        """Laplace-smoothed success rate as the planner sees it: imported + live."""
        return (self.prior_successes + self.successes + 1) / (self.prior_uses + self.uses + 2)

    def mean_cost(self) -> float:
        n = self.prior_uses + self.uses
        return (self.prior_cost + self.cost_total) / n if n else 0.0

    def live_rate(self) -> float:
        return self.successes / self.uses if self.uses else 1.0

    def signature(self) -> tuple:
        return (self.segments, self.program)


def skill_name(segments: tuple[Segment, ...]) -> str:
    if len(segments) == 1:
        return SINGLE_NAMES[segments[0]]
    return "route(" + ">".join(SHORT[s] for s in segments) + ")"


def declared_effect(layout: Layout, state: State, skill: Skill) -> Optional[tuple[State, int]]:
    """The planner's model of a skill: run its declared typed segments."""
    total = 0
    for seg in skill.segments:
        res = run_segment(layout, state, seg)
        if res is None:
            return None
        state, cost = res
        total += cost
    return state, total


def execute_skill(layout: Layout, state: State, skill: Skill) -> tuple[State, int, bool]:
    """Really run the skill. ok = the actual end state matches the declared one."""
    declared = declared_effect(layout, state, skill)
    if declared is None:
        return state, 0, False
    if skill.program is None:
        return declared[0], declared[1], True
    cur = state
    for prim in skill.program:            # a keystroke macro: replays blind to the layout
        cur, _ = step(layout, cur, prim)
    return cur, len(skill.program), cur == declared[0]


def should_retire(skill: Skill) -> bool:
    return skill.uses >= RETIRE_MIN_USES and skill.live_rate() < RETIRE_MAX_RATE


def prepare(layout: Layout, needs: frozenset[str]) -> Optional[State]:
    """Build a held-out test state in which the declared preconditions hold."""
    st = initial_state(layout)
    inv, items = set(), set(st.items)
    door_open = rock_broken = False
    for need in sorted(needs):
        if need in ("key", "pick"):
            for item in sorted(items):
                if item[0] == need:
                    items.discard(item)
                    break
            inv.add(need)
        elif need == "door_open":
            door_open = True
        elif need == "rock_broken":
            if layout.rock is None:
                return None
            rock_broken = True
    return State(st.pos, frozenset(inv), frozenset(items), door_open, rock_broken, False)


def gate_check(skill: Skill, heldout: list[Layout], k: int) -> tuple[bool, int, int]:
    """Replay on up to k held-out layouts where the skill applies. Pass = zero mismatches."""
    trials = failures = 0
    for lay in heldout:
        st = prepare(lay, skill.needs)
        if st is None or declared_effect(lay, st, skill) is None:
            continue
        _, _, ok = execute_skill(lay, st, skill)
        trials += 1
        failures += int(not ok)
        if trials == k:
            break
    return trials >= 1 and failures == 0, trials, failures


class Library:
    def __init__(self, max_skills: int, gate_on: bool, gate_k: int, heldout: list[Layout]):
        self.max_skills = max_skills
        self.gate_on = gate_on
        self.gate_k = gate_k
        self.heldout = heldout
        self.skills: list[Skill] = []
        self.quarantined: list[Skill] = []
        self.retired: list[Skill] = []
        self.evicted: list[Skill] = []
        self.replays = 0

    def known(self, sig: tuple) -> bool:
        pools = self.skills + self.quarantined + self.retired + self.evicted
        return any(s.signature() == sig for s in pools)

    def propose(self, skill: Skill, episode: int) -> str:
        if self.known(skill.signature()):
            return "duplicate"
        if self.gate_on and self.gate_k > 0:
            passed, trials, failures = gate_check(skill, self.heldout, self.gate_k)
            self.replays += trials
            skill.gate_note = f"{trials - failures}/{trials} held-out replays matched"
            if not passed:
                skill.status, skill.status_episode = "quarantined", episode
                self.quarantined.append(skill)
                return "quarantined"
        skill.status, skill.status_episode = "admitted", episode
        self.skills.append(skill)
        while len(self.skills) > self.max_skills:
            victim = min(self.skills, key=lambda s: (s.uses, s.status_episode, s.name))
            self.skills.remove(victim)
            victim.status = "evicted"
            self.evicted.append(victim)
        return "admitted"

    def record_use(self, skill: Skill, ok: bool, cost: int, episode: int, layout_index: int) -> None:
        skill.uses += 1
        skill.cost_total += cost
        if ok:
            skill.successes += 1
            skill.origin_successes += int(layout_index == skill.origin_layout)
        else:
            skill.wasted += cost
        if self.gate_on and skill in self.skills and should_retire(skill):
            self.skills.remove(skill)
            skill.status, skill.status_episode = "retired", episode
            self.retired.append(skill)


# ----------------------------------------------------------------------------
# Planner: horizon-limited BFS over primitives + applicable skills
# ----------------------------------------------------------------------------
Action = tuple[str, object]   # ("prim", name) or ("skill", Skill)


@dataclass
class Node:
    state: State
    path: tuple[Action, ...]
    cost: int
    cells: tuple[Cell, ...]


def rank_skills(skills: list[Skill], mode: str = "cost") -> list[Skill]:
    """cost: cheapest claimed skill first (rate breaks ties). rate: most reliable first."""
    if mode == "rate":
        return sorted(skills, key=lambda s: (-s.rate(), s.mean_cost(), s.name))
    return sorted(skills, key=lambda s: (s.mean_cost(), -s.rate(), s.name))


def plan(layout: Layout, state: State, skills: list[Skill], horizon: int,
         visited: set[Cell], rank: str = "cost") -> tuple[list[Action], int, bool]:
    """Return (plan, expansions, solved). Unsolved plans are the best partial plan."""
    ranked = rank_skills(skills, rank)
    queue = deque([Node(state, (), 0, ())])
    seen = {state}
    generated: list[Node] = []
    expansions = 0
    while queue and expansions < EXPANSION_BUDGET:
        node = queue.popleft()
        if len(node.path) >= horizon:
            continue
        expansions += 1
        succs: list[tuple[Action, State, int]] = []
        for sk in ranked:
            if not sk.needs <= satisfied(node.state):
                continue
            eff = declared_effect(layout, node.state, sk)
            if eff is not None:
                succs.append((("skill", sk), eff[0], eff[1]))
        for prim in PRIMITIVES:
            nxt, changed = step(layout, node.state, prim)
            if changed:
                succs.append((("prim", prim), nxt, 1))
        for action, nxt, cost in succs:
            if nxt in seen:
                continue
            seen.add(nxt)
            child = Node(nxt, node.path + (action,), node.cost + cost, node.cells + (nxt.pos,))
            if nxt.chest_open:
                return list(child.path), expansions, True
            generated.append(child)
            queue.append(child)
    if not generated:
        return [], expansions, False
    best = max(generated, key=lambda n: (progress(n.state),
                                         len({c for c in n.cells if c not in visited}),
                                         -n.cost))
    return list(best.path), expansions, False


# ----------------------------------------------------------------------------
# Episodes, abstraction, streams
# ----------------------------------------------------------------------------
@dataclass
class Record:
    kind: str
    name: str
    pre: State
    post: State
    cost: int
    ok: bool
    skill: Optional[Skill] = None


@dataclass
class EpisodeResult:
    success: bool
    steps: int
    expansions: int
    decisions: int
    macro_decisions: int
    macro_steps: int
    kind: str = "A"
    records: list[Record] = field(default_factory=list)
    library_size: int = 0


@dataclass
class Config:
    label: str
    library: bool
    poison: bool
    gate: bool
    gate_k: int = 3
    max_skills: int = 12
    horizon: int = 6
    budget: int = 22
    episodes: int = 48
    layouts: int = 8
    seed: int = DEFAULT_SEED
    rank: str = "cost"


def run_episode(layout: Layout, lib: Optional[Library], cfg: Config, episode: int) -> EpisodeResult:
    state = initial_state(layout)
    steps = expansions = decisions = macro_decisions = macro_steps = 0
    disabled: set[str] = set()
    visited = {state.pos}
    records: list[Record] = []
    while not state.chest_open and steps < cfg.budget:
        skills = [s for s in lib.skills if s.name not in disabled] if lib else []
        path, exp, _ = plan(layout, state, skills, cfg.horizon, visited, cfg.rank)
        expansions += exp
        if not path:
            break
        for kind, payload in path:
            if kind == "prim":
                nxt, ok = step(layout, state, payload)
                cost = 1
                records.append(Record("prim", payload, state, nxt, cost, ok))
            else:
                nxt, cost, ok = execute_skill(layout, state, payload)
                lib.record_use(payload, ok, cost, episode, layout.index)
                macro_decisions += 1
                macro_steps += min(cost, cfg.budget - steps)   # the budget stops a long skill
                records.append(Record("skill", payload.name, state, nxt, cost, ok, payload))
            decisions += 1
            steps += cost
            state = nxt
            visited.add(state.pos)
            if kind == "skill" and not ok:
                disabled.add(payload.name)     # do not retry a skill that just failed
                break
            if state.chest_open or steps >= cfg.budget:
                break
    success = state.chest_open and steps <= cfg.budget
    return EpisodeResult(success, min(steps, cfg.budget), expansions, decisions, macro_decisions,
                         macro_steps, layout.kind, records, len(lib.skills) if lib else 0)


def infer_segment(rec: Record) -> Segment:
    if rec.name == "PICKUP":
        return (sorted(rec.post.inv - rec.pre.inv)[0], "PICKUP")
    if rec.name == "USE":
        return ("door", "USE") if rec.post.door_open != rec.pre.door_open else ("rock", "USE")
    return ("chest", "OPEN")


def abstract(layout: Layout, records: list[Record], start: State) -> list[tuple[Segment, State]]:
    """Turn a trajectory into typed segments, each with the state it started from."""
    out: list[tuple[Segment, State]] = []
    seg_start = start
    for rec in records:
        if rec.kind == "skill":
            if not rec.ok:
                continue
            cur = seg_start
            for seg in rec.skill.segments:
                out.append((seg, cur))
                res = run_segment(layout, cur, seg)
                cur = res[0] if res else cur
            seg_start = rec.post
        elif rec.name in INTERACTIONS and rec.ok:
            out.append((infer_segment(rec), seg_start))
            seg_start = rec.post
    return out


def make_skill(layout: Layout, segments: tuple[Segment, ...], pre: State, origin: str) -> Skill:
    sk = Skill(skill_name(segments), segments, satisfied(pre), None, origin)
    eff = declared_effect(layout, pre, sk)
    sk.uses, sk.successes, sk.cost_total = 1, 1, eff[1] if eff else 0
    return sk


def propose_from_episode(lib: Library, layout: Layout, result: EpisodeResult, episode: int) -> list[str]:
    segs = abstract(layout, result.records, initial_state(layout))
    if not segs:
        return []
    origin = f"learned ep {episode} (layout {layout.index})"
    outcomes = [lib.propose(make_skill(layout, tuple(s for s, _ in segs), segs[0][1], origin), episode)]
    for seg, pre in segs:
        outcomes.append(lib.propose(make_skill(layout, (seg,), pre, origin), episode))
    return outcomes


def make_poison(layout: Layout) -> Skill:
    """A concrete recording of layout 0's optimal route, declaring the honest route's effect."""
    program = tuple(solve_optimal(layout))
    state = initial_state(layout)
    records = []
    for prim in program:
        nxt, ok = step(layout, state, prim)
        records.append(Record("prim", prim, state, nxt, 1, ok))
        state = nxt
    segments = tuple(seg for seg, _ in abstract(layout, records, initial_state(layout)))
    return Skill(f"fast_route_L{layout.index}", segments, frozenset(), program,
                 f"imported recording from layout {layout.index}",
                 prior_uses=POISON_PRIOR_USES, prior_successes=POISON_PRIOR_USES,
                 prior_cost=POISON_PRIOR_USES * len(program), origin_layout=layout.index)


@dataclass
class RunResult:
    cfg: Config
    episodes: list[EpisodeResult]
    lib: Optional[Library]
    poison: Optional[Skill]
    oracle_steps: float


def run_stream(cfg: Config) -> RunResult:
    rng = random.Random(cfg.seed)
    layouts = [make_layout(rng, i) for i in range(cfg.layouts)]
    heldout_rng = random.Random(cfg.seed + 1000)
    heldout = [make_layout(heldout_rng, i) for i in range(2 * cfg.gate_k + 4)]
    lib = Library(cfg.max_skills, cfg.gate, cfg.gate_k, heldout) if cfg.library else None
    poison = None
    if cfg.library and cfg.poison:
        poison = make_poison(layouts[0])
        lib.propose(poison, 0)
    results = []
    for ep in range(cfg.episodes):
        lay = layouts[ep % cfg.layouts]
        res = run_episode(lay, lib, cfg, ep)
        if lib is not None and res.success:
            propose_from_episode(lib, lay, res, ep)
            res.library_size = len(lib.skills)
        results.append(res)
    oracle = sum(len(solve_optimal(layouts[ep % cfg.layouts])) for ep in range(cfg.episodes)) / cfg.episodes
    return RunResult(cfg, results, lib, poison, oracle)


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------
def summarize(eps: list[EpisodeResult]) -> dict:
    n = len(eps)
    steps = sum(e.steps for e in eps)
    macro = sum(e.macro_steps for e in eps)
    return {
        "n": n,
        "success": sum(e.success for e in eps) / n if n else 0.0,
        "mean_steps": steps / n if n else 0.0,
        "expansions": sum(e.expansions for e in eps) / n if n else 0.0,
        "macro_share": macro / steps if steps else 0.0,
        "library_size": eps[-1].library_size if eps else 0,
    }


def block_rows(run: RunResult) -> list[tuple[str, dict]]:
    eps = run.episodes
    size = max(1, -(-len(eps) // BLOCKS))
    rows = []
    for b in range(0, len(eps), size):
        chunk = eps[b:b + size]
        rows.append((f"{b + 1}-{b + len(chunk)}", summarize(chunk)))
    rows.append((f"all 1-{len(eps)}", summarize(eps)))
    return rows


def print_run(run: RunResult) -> None:
    cfg = run.cfg
    print(f"\n{cfg.label}")
    print(f"  {'episodes':<12}{'success':>9}{'mean steps':>12}{'expansions/ep':>15}"
          f"{'library':>9}{'macro share':>13}")
    for label, s in block_rows(run):
        print(f"  {label:<12}{s['success']:>9.1%}{s['mean_steps']:>12.1f}{s['expansions']:>15.1f}"
              f"{s['library_size']:>9d}{s['macro_share']:>13.1%}")
    by_kind = []
    for kind, desc in (("A", "key>door>chest"), ("B", "+pick>rock")):
        eps = [e for e in run.episodes if e.kind == kind]
        if eps:
            by_kind.append(f"{kind} ({desc}) {summarize(eps)['success']:.1%} of {len(eps)}")
    print("  by task kind: " + " · ".join(by_kind))
    lib = run.lib
    if lib is None:
        return
    print(f"  skills: {len(lib.skills)} admitted, {len(lib.quarantined)} quarantined, "
          f"{len(lib.retired)} retired, {len(lib.evicted)} evicted; held-out replays run: {lib.replays}")
    print(f"  {'name':<34}{'live uses':>10}{'live succ':>10}{'mean cost':>10}  status")
    for sk in sorted(lib.skills, key=lambda s: (-s.uses, s.name)):
        print(f"  {sk.name:<34}{sk.uses:>10d}{sk.successes:>10d}{sk.mean_cost():>10.1f}  {sk.status}")
    if run.poison is not None:
        p = run.poison
        where = f"episode {p.status_episode}" if p.status != "admitted" else "still in library"
        print(f"  poison {p.name}: status {p.status} ({where}); {p.gate_note or 'no replay'}; "
              f"live uses {p.uses}, live successes {p.successes} ({p.origin_successes} in origin layout), "
              f"wasted steps {p.wasted}; program length {len(p.program)}")


def headline(runs: dict[str, RunResult], cfg: Config) -> list[str]:
    a, b = summarize(runs["A"].episodes), summarize(runs["B"].episodes)
    lines = [
        f"Over {cfg.episodes} episodes on {cfg.layouts} layouts, the skill library moves success from "
        f"{a['success']:.1%} to {b['success']:.1%} and mean steps from {a['mean_steps']:.1f} to "
        f"{b['mean_steps']:.1f} (oracle optimum {runs['A'].oracle_steps:.1f}); planner expansions per "
        f"episode fall from {a['expansions']:.0f} to {b['expansions']:.0f}.",
        f"Last block of the clean library run: {block_rows(runs['B'])[-2][1]['macro_share']:.1%} of steps "
        f"are executed inside skills; library size {b['library_size']} of max {cfg.max_skills}.",
    ]
    if "C" in runs:
        c, d = summarize(runs["C"].episodes), summarize(runs["D"].episodes)
        pc, pd = runs["C"].poison, runs["D"].poison
        lines.append(
            f"Without the gate the poisoned skill was admitted at episode 0, fired {pc.uses} times, "
            f"succeeded {pc.successes} times ({pc.origin_successes} of them in the layout where it was "
            f"recorded) and wasted {pc.wasted} steps; "
            f"success {c['success']:.1%} vs {b['success']:.1%}, mean steps {c['mean_steps']:.1f} vs "
            f"{b['mean_steps']:.1f}; at the end it is still {pc.status}.")
        if pd.status == "quarantined":
            lines.append(
                f"With the gate (k={cfg.gate_k}) it was quarantined before any live use "
                f"({pd.gate_note}); success {d['success']:.1%}, mean steps {d['mean_steps']:.1f}.")
        elif pd.status == "retired":
            lines.append(
                f"With the gate (k={cfg.gate_k}) it passed admission ({pd.gate_note or 'no replay'}) "
                f"but live telemetry retired it at episode {pd.status_episode} after {pd.uses} uses "
                f"({pd.successes} successes, {pd.wasted} wasted steps); success {d['success']:.1%}, "
                f"mean steps {d['mean_steps']:.1f}.")
        else:
            lines.append(
                f"With the gate (k={cfg.gate_k}) the poisoned skill is still {pd.status} after "
                f"{pd.uses} uses ({pd.successes} successes); success {d['success']:.1%}, "
                f"mean steps {d['mean_steps']:.1f}.")
    return lines


def to_json(runs: dict[str, RunResult]) -> dict:
    out = {}
    for key, run in runs.items():
        out[key] = {"label": run.cfg.label, "blocks": [(lbl, s) for lbl, s in block_rows(run)],
                    "oracle_steps": run.oracle_steps}
        if run.lib is not None:
            out[key]["skills"] = [{"name": s.name, "uses": s.uses, "successes": s.successes,
                                   "status": s.status} for s in run.lib.skills]
    return out


def build_runs(args: argparse.Namespace) -> dict[str, RunResult]:
    base = dict(gate_k=args.gate_k, max_skills=args.max_skills, horizon=args.horizon,
                budget=args.budget, episodes=args.episodes, layouts=args.layouts, seed=args.seed,
                rank=args.rank)
    gate = args.gate == "on"
    runs = {
        "A": run_stream(Config("Run A — no library (primitives only)", False, False, False, **base)),
        "B": run_stream(Config(f"Run B — library on, poison off, gate {args.gate}",
                               True, False, gate, **base)),
    }
    if args.poison == "on":
        runs["C"] = run_stream(Config("Run C — library on, poison ON, gate OFF",
                                      True, True, False, **base))
        runs["D"] = run_stream(Config(f"Run D — library on, poison ON, gate ON (k={args.gate_k})",
                                      True, True, True, **base))
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episodes", type=int, default=48,
                        help="episodes in the stream (default: %(default)s)")
    parser.add_argument("--layouts", type=int, default=8,
                        help="distinct layouts cycled through (default: %(default)s)")
    parser.add_argument("--gate", choices=["on", "off"], default="on",
                        help="validation gate for the clean library run B (default: %(default)s)")
    parser.add_argument("--poison", choices=["on", "off"], default="on",
                        help="inject the poisoned skill; runs the gate-off / gate-on pair (default: %(default)s)")
    parser.add_argument("--gate-k", type=int, default=3,
                        help="held-out replays before admission; 0 = retirement only (default: %(default)s)")
    parser.add_argument("--max-skills", type=int, default=12,
                        help="library capacity; least-used evicted (default: %(default)s)")
    parser.add_argument("--horizon", type=int, default=6,
                        help="planner horizon in decisions (default: %(default)s)")
    parser.add_argument("--budget", type=int, default=22,
                        help="environment steps per episode (default: %(default)s)")
    parser.add_argument("--rank", choices=["cost", "rate"], default="cost",
                        help="how the planner orders skills with the same effect (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="RNG seed (default: %(default)s)")
    parser.add_argument("--out", type=str, default=None, help="optional JSON report path")
    args = parser.parse_args()

    print("=" * 78)
    print("EXPERIENCE STREAMS AND SKILL LIBRARIES (Phase 20, Lesson 12)")
    print("=" * 78)
    print(f"seed {args.seed} · {args.episodes} episodes over {args.layouts} layouts "
          f"(even = key>door>chest, odd = +pick>rock) · horizon {args.horizon} · "
          f"budget {args.budget} steps · max skills {args.max_skills} · gate k={args.gate_k} · "
          f"rank by {args.rank}")
    runs = build_runs(args)
    print(f"oracle (full search, no horizon): mean steps {runs['A'].oracle_steps:.1f}")
    for run in runs.values():
        print_run(run)
    print()
    print("=" * 78)
    print("HEADLINE")
    print("-" * 78)
    for line in headline(runs, runs["A"].cfg):
        print(f"  {line}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(to_json(runs), fh, indent=2)
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
