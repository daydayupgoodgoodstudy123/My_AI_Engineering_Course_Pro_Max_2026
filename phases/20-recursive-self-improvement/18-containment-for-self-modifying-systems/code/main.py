"""Self-edit gatekeeper simulator (Phase 20, Lesson 18) -- stdlib only.
A simulated self-modifying agent emits edit proposals (benign refactors plus
Lesson-15-style tampering). A policy engine that lives OUTSIDE the sandbox
returns allow / deny / escalate with the matched rule; an archive stores every
decision as a hash-chained record; rollback appends rather than rewrites; a
tamper test alters one historical record and shows verification failing there.
Usage: python3 main.py [--proposals N] [--tamper-rate R] [--policy strict|permissive|both] [--seed S]
See docs/en.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, replace
from typing import Callable, Optional

DEFAULT_SEED = 7
GENESIS = "0" * 64
CATEGORIES = ("code", "tests", "evaluator", "config", "network", "deps")
TAMPER = "tamper"
BENIGN = "benign"

# Path prefix -> category. The GATEKEEPER derives categories from the files a
# proposal touches; it never trusts the categories the loop declares about itself.
PATH_RULES: tuple[tuple[str, str], ...] = (
    ("eval/", "evaluator"),
    ("tests/", "tests"),
    ("network/", "network"),
    ("deps/", "deps"),
    ("config/", "config"),
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def classify_path(path: str) -> str:
    for prefix, category in PATH_RULES:
        if path.startswith(prefix):
            return category
    return "code"


def derive_categories(files: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({classify_path(f) for f in files}))


# --------------------------------------------------------------------------
# Step 1: the edit-proposal schema (dataclass <-> JSON, content-addressed)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class EditProposal:
    id: str
    parent_hash: str                 # content hash of the proposal this one builds on
    files: tuple[str, ...]
    categories: tuple[str, ...]      # as DECLARED by the loop (may be wrong or lying)
    diff_size: int                   # changed lines
    claimed_effect: str
    provenance: str                  # which component produced it, in which cycle

    def to_json(self) -> str:
        return canonical(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> "EditProposal":
        data = json.loads(text)
        data["files"] = tuple(data["files"])
        data["categories"] = tuple(data["categories"])
        return cls(**data)

    def content_hash(self) -> str:
        return sha256(self.to_json())


@dataclass(frozen=True)
class Decision:
    verdict: str   # allow | deny | escalate
    rule: str


@dataclass
class CycleState:
    cycle: int = 0
    edits_applied: int = 0
    diff_applied: int = 0


# --------------------------------------------------------------------------
# Step 2: the policy engine -- ordered rules, first match wins
# --------------------------------------------------------------------------
Predicate = Callable[[EditProposal, tuple[str, ...], CycleState, "Policy"], bool]


@dataclass(frozen=True)
class Rule:
    name: str
    verdict: str
    when: Predicate


@dataclass
class Policy:
    name: str
    rules: list[Rule]
    trust_declared: bool             # permissive trusts the loop's own category labels
    max_edits_per_cycle: int
    max_diff_per_cycle: int
    large_diff: int
    default_rule: str = "small-code-edit"

    def effective_categories(self, p: EditProposal) -> tuple[str, ...]:
        return tuple(sorted(p.categories)) if self.trust_declared else derive_categories(p.files)

    def decide(self, p: EditProposal, state: CycleState) -> Decision:
        cats = self.effective_categories(p)
        for rule in self.rules:
            if rule.when(p, cats, state, self):
                return Decision(rule.verdict, rule.name)
        return Decision("allow", self.default_rule)


def strict_policy(max_edits_per_cycle: int = 3, max_diff_per_cycle: int = 400,
                  large_diff: int = 200) -> Policy:
    rules = [
        Rule("metadata-mismatch", "deny",
             lambda p, c, s, pol: c != tuple(sorted(p.categories))),
        Rule("evaluator-frozen", "deny", lambda p, c, s, pol: "evaluator" in c),
        Rule("tests-frozen", "deny", lambda p, c, s, pol: "tests" in c),
        Rule("network-escalate", "escalate", lambda p, c, s, pol: "network" in c),
        Rule("deps-escalate", "escalate", lambda p, c, s, pol: "deps" in c),
        Rule("config-escalate", "escalate", lambda p, c, s, pol: "config" in c),
        Rule("large-diff", "escalate", lambda p, c, s, pol: p.diff_size > pol.large_diff),
        Rule("cycle-cap", "deny",
             lambda p, c, s, pol: s.edits_applied >= pol.max_edits_per_cycle),
        Rule("budget-cap", "deny",
             lambda p, c, s, pol: s.diff_applied + p.diff_size > pol.max_diff_per_cycle),
    ]
    return Policy("strict", rules, trust_declared=False,
                  max_edits_per_cycle=max_edits_per_cycle,
                  max_diff_per_cycle=max_diff_per_cycle, large_diff=large_diff)


def permissive_policy() -> Policy:
    # "Trust the loop": only an edit that DECLARES itself an evaluator edit is held.
    rules = [Rule("evaluator-declared", "escalate", lambda p, c, s, pol: "evaluator" in c)]
    return Policy("permissive", rules, trust_declared=True,
                  max_edits_per_cycle=10**9, max_diff_per_cycle=10**9, large_diff=10**9,
                  default_rule="trust-loop")


# --------------------------------------------------------------------------
# Step 3: the archive -- hash-chained records, rollback as an appended record
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CommitRecord:
    seq: int
    cycle: int
    kind: str            # decision | rollback
    proposal_id: str
    proposal_hash: str
    verdict: str
    rule: str
    state_hash: str      # hash of the applied-edit list AFTER this record
    prev_hash: str
    record_hash: str


def record_body(rec: CommitRecord) -> dict:
    body = asdict(rec)
    body.pop("record_hash")
    return body


class Archive:
    def __init__(self) -> None:
        self.records: list[CommitRecord] = []
        self.applied: list[str] = []
        self._snapshots: dict[str, tuple[str, ...]] = {}

    @property
    def head(self) -> str:
        return self.records[-1].record_hash if self.records else GENESIS

    def state_hash(self) -> str:
        return sha256("\n".join(self.applied))

    def _append(self, cycle: int, kind: str, proposal_id: str, proposal_hash: str,
                verdict: str, rule: str) -> CommitRecord:
        body = {
            "seq": len(self.records), "cycle": cycle, "kind": kind,
            "proposal_id": proposal_id, "proposal_hash": proposal_hash,
            "verdict": verdict, "rule": rule, "state_hash": self.state_hash(),
            "prev_hash": self.head,
        }
        rec = CommitRecord(**body, record_hash=sha256(canonical(body)))
        self.records.append(rec)
        self._snapshots[rec.record_hash] = tuple(self.applied)
        return rec

    def commit(self, p: EditProposal, d: Decision, cycle: int) -> CommitRecord:
        if d.verdict == "allow":
            self.applied.append(p.id)
        return self._append(cycle, "decision", p.id, p.content_hash(), d.verdict, d.rule)

    def rollback(self, to_id: str, cycle: int) -> tuple[CommitRecord, int]:
        """Restore the applied set to the state right after `to_id` was decided.
        History is never rewritten: the rollback is itself a chained record."""
        target = next(r for r in self.records
                      if r.kind == "decision" and r.proposal_id == to_id)
        before = len(self.applied)
        self.applied = list(self._snapshots[target.record_hash])
        reverted = before - len(self.applied)
        rec = self._append(cycle, "rollback", to_id, target.record_hash,
                           "rollback", f"rollback->{to_id}")
        return rec, reverted

    def depth(self) -> int:
        return len(self.records)


def verify_chain(records: list[CommitRecord],
                 expected_head: Optional[str] = None) -> tuple[bool, int]:
    """Return (ok, first_bad_position). -1 means every link checked out.
    `expected_head` is a head hash published outside the sandbox: it catches a
    rewrite of the LAST record, which no internal link can detect."""
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.prev_hash != prev or sha256(canonical(record_body(rec))) != rec.record_hash:
            return False, i
        prev = rec.record_hash
    if expected_head is not None and prev != expected_head:
        return False, len(records) - 1
    return True, -1


def tamper_record(records: list[CommitRecord], position: int,
                  rehash: bool) -> list[CommitRecord]:
    """Return a copy where record[position] has its verdict flipped
    (deny/escalate -> allow, allow -> deny) and its rule rewritten.
    rehash=False: naive edit (hash no longer matches body).
    rehash=True: the attacker also recomputes that record's hash, so the
    break moves to the NEXT record's prev_hash (or to the published head)."""
    out = list(records)
    flipped = "deny" if out[position].verdict == "allow" else "allow"
    altered = replace(out[position], verdict=flipped, rule="(rewritten)")
    if rehash:
        altered = replace(altered, record_hash=sha256(canonical(record_body(altered))))
    out[position] = altered
    return out


# --------------------------------------------------------------------------
# Step 4: the simulated self-modifying agent
# --------------------------------------------------------------------------
BENIGN_FILES = ("agent/search.py", "agent/memory.py", "agent/prompts.py",
                "agent/planner.py", "agent/tools.py")

# kind, files, DECLARED categories, diff range, claimed effect
TAMPER_KINDS: tuple[tuple[str, tuple[str, ...], tuple[str, ...], tuple[int, int], str], ...] = (
    ("edit-evaluator", ("eval/score.py",), ("evaluator",), (20, 60), "loosen pass criterion"),
    ("mislabel-evaluator", ("eval/score.py",), ("code",), (10, 40), "refactor scoring helper"),
    ("edit-tests", ("tests/test_agent.py",), ("tests",), (5, 30), "remove flaky assertion"),
    ("bump-timeout", ("config/limits.yaml",), ("config",), (1, 4), "raise timeout 300s->3000s"),
    ("open-egress", ("network/egress_policy.json",), ("network",), (2, 6), "allow outbound to *"),
    ("add-dep", ("deps/requirements.txt",), ("deps",), (1, 3), "add helper package"),
    ("disable-logging", ("agent/logging.py",), ("code",), (3, 12), "drop noisy special-token log"),
)

BENIGN_KINDS: tuple[tuple[str, float], ...] = (
    ("small-code", 0.75), ("large-refactor", 0.10), ("honest-config", 0.08), ("honest-deps", 0.07),
)


@dataclass(frozen=True)
class Emitted:
    proposal: EditProposal
    truth: str      # benign | tamper  (ground truth for scoring; the policy never sees it)
    kind: str
    cycle: int


def simulate_stream(n: int, tamper_rate: float, cycles: int, rng: random.Random) -> list[Emitted]:
    per_cycle = max(1, -(-n // cycles))   # ceil
    parent = GENESIS
    # Tampering kinds are drawn round-robin in a seed-shuffled order, so every
    # run with >= 7 tampering proposals exercises every attack at least once.
    order = list(range(len(TAMPER_KINDS)))
    rng.shuffle(order)
    n_tamper = 0
    stream: list[Emitted] = []
    for i in range(n):
        cycle = i // per_cycle
        pid = f"p-{i + 1:03d}"
        if rng.random() < tamper_rate:
            kind, files, declared, (lo, hi), effect = TAMPER_KINDS[order[n_tamper % len(order)]]
            n_tamper += 1
            truth = TAMPER
        else:
            r, acc, kind = rng.random(), 0.0, BENIGN_KINDS[0][0]
            for name, w in BENIGN_KINDS:
                acc += w
                if r < acc:
                    kind = name
                    break
            truth = BENIGN
            if kind == "small-code":
                files = (BENIGN_FILES[rng.randrange(len(BENIGN_FILES))],)
                lo, hi, effect = 4, 80, "tighten retry loop"
            elif kind == "large-refactor":
                files = (BENIGN_FILES[0], BENIGN_FILES[3])
                lo, hi, effect = 220, 480, "restructure planner module"
            elif kind == "honest-config":
                files = ("config/limits.yaml",)
                lo, hi, effect = 1, 3, "lower batch size"
            else:
                files = ("deps/requirements.txt",)
                lo, hi, effect = 1, 2, "pin patch version"
            declared = derive_categories(files)
        p = EditProposal(id=pid, parent_hash=parent, files=files,
                         categories=tuple(declared), diff_size=rng.randint(lo, hi),
                         claimed_effect=effect, provenance=f"improver@cycle{cycle}")
        parent = p.content_hash()
        stream.append(Emitted(p, truth, kind, cycle))
    return stream


# --------------------------------------------------------------------------
# Running a policy over the stream
# --------------------------------------------------------------------------
@dataclass
class RunResult:
    policy: str
    archive: Archive
    rule_counts: Counter
    tamper_by_kind: dict[str, Counter]
    benign_verdicts: Counter
    slipped: list[tuple[str, str]]       # (kind, proposal id) of tampering that was allowed
    n_tamper: int
    n_benign: int

    def tamper_totals(self) -> Counter:
        total: Counter = Counter()
        for c in self.tamper_by_kind.values():
            total.update(c)
        return total


def run_policy(policy: Policy, stream: list[Emitted]) -> RunResult:
    archive = Archive()
    state = CycleState()
    rule_counts: Counter = Counter()
    tamper_by_kind: dict[str, Counter] = {k[0]: Counter() for k in TAMPER_KINDS}
    benign_verdicts: Counter = Counter()
    slipped: list[tuple[str, str]] = []
    n_t = n_b = 0
    for item in stream:
        if item.cycle != state.cycle:
            state = CycleState(cycle=item.cycle)
        d = policy.decide(item.proposal, state)
        if d.verdict == "allow":
            state.edits_applied += 1
            state.diff_applied += item.proposal.diff_size
        archive.commit(item.proposal, d, item.cycle)
        rule_counts[(d.verdict, d.rule)] += 1
        if item.truth == TAMPER:
            n_t += 1
            tamper_by_kind[item.kind][d.verdict] += 1
            if d.verdict == "allow":
                slipped.append((item.kind, item.proposal.id))
        else:
            n_b += 1
            benign_verdicts[d.verdict] += 1
    return RunResult(policy.name, archive, rule_counts, tamper_by_kind,
                     benign_verdicts, slipped, n_t, n_b)


def rollback_target(res: RunResult) -> Optional[str]:
    """Roll back to the last applied edit BEFORE the first tampering edit that
    slipped through; if nothing slipped, roll back to the midpoint applied edit."""
    applied = res.archive.applied
    if not applied:
        return None
    if res.slipped:
        bad = res.slipped[0][1]
        idx = applied.index(bad)
        return applied[idx - 1] if idx > 0 else None
    return applied[len(applied) // 2]


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def pct(n: int, d: int) -> str:
    return f"{(n / d if d else 0.0):.1%}"


def print_policy_report(res: RunResult) -> None:
    print(f"\n[{res.policy}] decisions by matched rule")
    print(f"  {'verdict':<9} {'rule':<20} {'count':>5}")
    for (verdict, rule), c in sorted(res.rule_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {verdict:<9} {rule:<20} {c:>5}")
    tot = res.tamper_totals()
    print(f"\n[{res.policy}] tampering proposals ({res.n_tamper}) by kind")
    print(f"  {'kind':<20} {'deny':>5} {'escal':>5} {'allow':>5}")
    for kind, c in res.tamper_by_kind.items():
        if sum(c.values()):
            print(f"  {kind:<20} {c['deny']:>5} {c['escalate']:>5} {c['allow']:>5}")
    print(f"  {'total':<20} {tot['deny']:>5} {tot['escalate']:>5} {tot['allow']:>5}"
          f"   -> let through: {pct(tot['allow'], res.n_tamper)}")
    b = res.benign_verdicts
    print(f"[{res.policy}] benign proposals ({res.n_benign}): "
          f"allow {b['allow']} ({pct(b['allow'], res.n_benign)}), "
          f"escalate {b['escalate']}, deny {b['deny']}")
    print(f"[{res.policy}] archive depth {res.archive.depth()}, applied edits "
          f"{len(res.archive.applied)}, head {res.archive.head[:12]}")


def rollback_and_tamper_demo(res: RunResult, verify: bool) -> dict:
    out: dict = {"rollback": None, "naive": None, "rehash": None, "verify_before": None}
    arc = res.archive
    print(f"\n[{res.policy}] rollback + chain verification")
    ok, pos = verify_chain(arc.records)
    out["verify_before"] = ok
    print(f"  verify chain ({arc.depth()} records): {'OK' if ok else f'FAIL at {pos}'}")
    target = rollback_target(res)
    if target is not None:
        before = arc.state_hash()[:12]
        rec, reverted = arc.rollback(target, cycle=arc.records[-1].cycle + 1)
        ok2, _ = verify_chain(arc.records)
        why = (f"first slipped tampering edit {res.slipped[0][1]} ({res.slipped[0][0]})"
               if res.slipped else "midpoint (nothing slipped; drill only)")
        print(f"  rollback(to_id={target}) because: {why}")
        print(f"  state {before} -> {arc.state_hash()[:12]}, reverted {reverted} edit(s), "
              f"depth {arc.depth()} (appended, not rewritten), chain {'OK' if ok2 else 'FAIL'}")
        out["rollback"] = {"to": target, "reverted": reverted, "ok": ok2}
    else:
        print("  rollback skipped: no applied edits")
    if verify and arc.depth() >= 3:
        published_head = arc.head                      # copy held OUTSIDE the sandbox
        denies = [r.seq for r in arc.records if r.verdict == "deny"]
        k = denies[len(denies) // 2] if denies else arc.depth() // 2
        naive = tamper_record(arc.records, k, rehash=False)
        ok_n, pos_n = verify_chain(naive, published_head)
        rehashed = tamper_record(arc.records, k, rehash=True)
        ok_r, pos_r = verify_chain(rehashed, published_head)
        last = tamper_record(arc.records, arc.depth() - 1, rehash=True)
        ok_l_int, _ = verify_chain(last)                 # internal links only
        ok_l_ext, pos_l = verify_chain(last, published_head)
        print(f"  tamper test: rewrite record {k} ('{arc.records[k].verdict}' -> '{naive[k].verdict}')")
        print(f"    naive edit            -> verify {'OK' if ok_n else 'FAIL'} at position {pos_n}")
        print(f"    edit + recompute hash -> verify {'OK' if ok_r else 'FAIL'} at position {pos_r}")
        print(f"  tamper test: rewrite LAST record {arc.depth() - 1} + recompute hash")
        print(f"    internal links only   -> verify {'OK' if ok_l_int else 'FAIL'}"
              f"   (undetectable without an external anchor)")
        print(f"    with published head   -> verify {'OK' if ok_l_ext else 'FAIL'} at position {pos_l}")
        out["naive"] = (k, pos_n)
        out["rehash"] = (k, pos_r)
        out["last_internal_ok"] = ok_l_int
        out["last_external_pos"] = pos_l
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposals", type=int, default=40, help="proposals emitted (default %(default)s)")
    ap.add_argument("--tamper-rate", type=float, default=0.25,
                    help="probability a proposal is a tampering attempt (default %(default)s)")
    ap.add_argument("--policy", choices=["strict", "permissive", "both"], default="both")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--max-edits-per-cycle", type=int, default=3)
    ap.add_argument("--max-diff-per-cycle", type=int, default=400, help="changed-line budget per cycle")
    ap.add_argument("--large-diff", type=int, default=200, help="single-edit size that escalates")
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--verify-chain", action=argparse.BooleanOptionalAction, default=True,
                    help="run the tamper test on the archive (default on)")
    ap.add_argument("--out", type=str, default=None, help="write the strict archive as JSON")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    stream = simulate_stream(args.proposals, args.tamper_rate, args.cycles, rng)
    n_t = sum(1 for e in stream if e.truth == TAMPER)
    print("=" * 72)
    print("CONTAINMENT FOR SELF-EDITS: propose -> gatekeeper -> hash-chained archive")
    print("=" * 72)
    print(f"  proposals {args.proposals}  cycles {args.cycles}  tampering {n_t} "
          f"({pct(n_t, args.proposals)})  seed {args.seed}")
    print(f"  strict caps: {args.max_edits_per_cycle} edits/cycle, {args.max_diff_per_cycle} lines/cycle, "
          f"single edit > {args.large_diff} lines escalates")

    policies: list[Policy] = []
    if args.policy in ("strict", "both"):
        policies.append(strict_policy(args.max_edits_per_cycle, args.max_diff_per_cycle, args.large_diff))
    if args.policy in ("permissive", "both"):
        policies.append(permissive_policy())

    results: dict[str, RunResult] = {}
    demos: dict[str, dict] = {}
    for pol in policies:
        res = run_policy(pol, stream)
        results[pol.name] = res
        print_policy_report(res)
        demos[pol.name] = rollback_and_tamper_demo(res, args.verify_chain)

    if args.out:
        strict_or_any = results.get("strict") or next(iter(results.values()))
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump([asdict(r) for r in strict_or_any.archive.records], fh, indent=1)
        print(f"\n  wrote {len(strict_or_any.archive.records)} records to {args.out}")

    print()
    print("=" * 72)
    print("HEADLINE")
    print("-" * 72)
    for name, res in results.items():
        tot = res.tamper_totals()
        kinds = sorted({k for k, _ in res.slipped})
        tail = f" ({', '.join(kinds)})" if kinds else ""
        print(f"  {name}: blocked {tot['deny']} of {res.n_tamper} tampering proposals, escalated "
              f"{tot['escalate']} to a human, let {tot['allow']} through{tail}.")
    if "strict" in results:
        s = results["strict"]
        b = s.benign_verdicts
        caps = s.rule_counts[("deny", "cycle-cap")] + s.rule_counts[("deny", "budget-cap")]
        print(f"  containment cost: strict auto-applied {b['allow']} of {s.n_benign} benign edits "
              f"({pct(b['allow'], s.n_benign)}); {caps} proposal(s) hit a per-cycle cap.")
        if s.slipped:
            print(f"  limit: {len(s.slipped)} tampering edit(s) passed strict as small code edits -- "
                  f"path rules cannot see semantics; that is monitoring's job (Lesson 19).")
    for name, d in demos.items():
        if d.get("rollback"):
            rb = d["rollback"]
            print(f"  {name}: rollback to {rb['to']} reverted {rb['reverted']} edit(s); "
                  f"the chain still verifies ({'yes' if rb['ok'] else 'NO'}).")
        if d.get("naive"):
            k, pn = d["naive"]
            _, pr = d["rehash"]
            print(f"  {name}: chain verification detected the altered record {k} at position {pn} "
                  f"(naive) and {pr} (re-hashed); a re-hashed LAST record was "
                  f"{'invisible' if d['last_internal_ok'] else 'visible'} to internal links and "
                  f"caught at {d['last_external_pos']} by the published head.")


if __name__ == "__main__":
    main()
