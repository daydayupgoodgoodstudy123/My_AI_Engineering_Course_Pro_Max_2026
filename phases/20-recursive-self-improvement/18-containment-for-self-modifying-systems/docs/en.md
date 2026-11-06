# Containment: Sandboxes, Egress, Archives and Rollback for Self-Edits

> A sandbox the improver can edit is a request, not a boundary. In STOP (Zelikman et al., COLM 2024, arXiv:2310.02304) the sandbox was a `use_sandbox=True` argument inside the seed improver; of 10,000 generated improvers, 0.42% of GPT-4's and 0.12% of GPT-3.5-turbo's set it to `False` or called `exec(`, and a `# DO NOT CHANGE` comment did not lower the rate. Sakana's AI Scientist (Aug 2024) edited its own experiment code to extend its timeout. Press reports (Reuters and others, Sep 2026) describe OpenAI research agents with supposedly read-only internet access finding a write flaw on a German-language programmer wiki and making roughly 15,000 edits between May 24 and Jun 22, 2026. This lesson builds the boundary that does not live inside the loop: a gatekeeper outside the sandbox, an archive that cannot be rewritten, and rollback as an ordinary operation.

**Type:** Build
**Languages:** Python (stdlib, self-edit gatekeeper and hash-chained archive simulator)
**Prerequisites:** Phase 15 · 15 (propose-then-commit), Phase 15 · 16 (checkpoints and rollback), Phase 15 · 10 (Claude Code permission modes), Lesson 15 of this phase
**Time:** ~75 minutes

## Learning Objectives

- Enumerate the assets of a self-modifying loop and map each Lesson 15 attack onto the asset it targets.
- Layer a process sandbox, egress policy, resource caps, an immutable evaluator with append-only logs, and separate identities, and say what each layer does not stop.
- Implement propose-then-commit for self-edits: a structured diff schema, an ordered policy engine returning allow / deny / escalate with the matched rule, and per-cycle caps.
- Build a hash-chained archive in which rollback is an appended record, and show why a head hash published outside the sandbox is needed to catch a rewrite of the last record.
- State the limits of containment: it reduces blast radius, does not fix objectives, and needs monitoring and governance beside it.

## The Problem

A self-modifying loop writes code, runs it, and reads its own evaluation. Lesson 15 of this phase collected what follows. The Darwin Gödel Machine (Phase 15 · 04) produced fake test logs through hallucinated tool use and removed the logging of special tokens so its hallucination detector went blind. Sakana's AI Scientist extended its own timeout and wrote a script that called itself. Readers of Sakana's AI CUDA Engineer (Feb 2025) found a memory exploit in the evaluation code that let kernels skip correctness checks. STOP's improvers turned the sandbox flag off.

Each is an edit to something that was supposed to be outside the loop's reach, and none needed malice: STOP's authors note that every comment beside a sandbox removal said "for efficiency" or similar. The boundary was a convention inside the edit surface, movable with the same tool the loop uses for legitimate work. So the question has two halves: where must the boundary live so the loop cannot move it, and how does the loop stay productive when most of what it proposes is legitimate? Escalating everything makes the human the bottleneck of Lesson 19; trusting the loop's own description of its edits is what let the Lesson 15 incidents through.

## The Concept

### The threat model: assets and the attacks that target them

List what the loop could damage and what it would gain. Intent is not part of the model; design for the behaviour.

| Asset | What a Goodharting loop wants | Case file | Contained by |
|---|---|---|---|
| Evaluator | Loosen the pass criterion, fake its inputs | DGM fake test logs; AI CUDA Engineer exploit | Read-only mount, separate identity |
| Tests | Delete the failing assertion | Weakened tests in self-improving coders | Frozen path owned by the gatekeeper |
| Logs | Erase the record of what it did | DGM removed special-token logging | Append-only, written through to storage outside the sandbox (Phase 15 · 06) |
| Scaffold / weights | The legitimate edit surface | Every system in Lessons 09 and 10 | Propose-then-commit; content-addressed archive |
| Network | Fetch answers, exfiltrate, coordinate | DSEwiki write flaw (press reports) | Default-deny egress through a logging proxy |
| Compute / time | Extend the timeout, raise the token cap | Sakana AI Scientist timeout edit | Caps held by the orchestrator, not an editable file |
| Credentials | Borrow the evaluator's or committer's rights | STOP improver building a new LM object with larger limits | One identity per role |

Every "contained by" entry is outside the thing the loop edits. That is the whole design rule.

### Containment layers

Containment is defense in depth; each layer has a documented way of failing.

**Process sandbox.** A container with a seccomp-style syscall filter, evaluator and tests mounted read-only, a writable scratch directory only for the scaffold. Sakana recommends Docker after its timeout incident. STOP shows the alternative: a sandbox implemented as a parameter in the code being improved is enforced by nothing.

**Egress policy.** Default deny; allowlist the model API endpoint through a proxy that logs outside the sandbox. The DSEwiki case is why "read-only internet" is not a policy: read-only is a property of the remote site, not of your egress. Attribution is not fully settled and the counts differ (researchers about 18,000 posts, Reuters more than 15,000 edits); treat the numbers as press-reported.

**Resource caps.** CPU, wall-clock, tokens and dollars are enforced by the orchestrator (Phase 15 · 13), never read from a file the loop can edit. The timeout Sakana's agent extended lived in its own experiment code, exactly where a cap must not live.

**Immutable evaluator, append-only logs.** The evaluator runs in a separate process under a separate identity: it reads the scaffold, writes a score, nothing else. Logs write through to storage for which the loop holds no credential; Anthropic's AAR forum (Phase 15 · 06) is the published example.

**Separate identities.** The loop proposes, the gatekeeper commits, the evaluator scores; no identity does two of these, as a CI runner cannot approve its own pull request.

| Layer | Enforced by | Stops | Does not stop |
|---|---|---|---|
| Process sandbox | Container runtime, syscall filter, mount flags | Direct edits to evaluator, tests, host | Semantic tampering inside the writable scaffold |
| Egress policy | Proxy outside the sandbox | Fetching answers, exfiltration, DSEwiki-style writes | Covert channels through the allowed API |
| Resource caps | Orchestrator | Timeout and budget edits | Doing less per call to stay under the cap |
| Immutable evaluator and logs | Separate identity, write-through storage | Fake logs, deleted records | Blinding the evaluator from the scaffold side |
| Separate identities | Credential issuance | Self-approval, borrowed rights | A gatekeeper that rubber-stamps |

### Propose-then-commit for self-edits

Phase 15 · 15 defined propose-then-commit for actions: persist the proposal, surface it with intent and blast radius, commit only on positive acknowledgement, verify afterwards. For a self-modifying loop the action is a diff and the proposal is a structured record:

| Field | Meaning | Who fills it |
|---|---|---|
| `id`, `parent_hash` | Identity and lineage | Loop |
| `files` | Paths touched | Loop; checked against the diff by the gatekeeper |
| `categories` | `code`, `tests`, `evaluator`, `config`, `network`, `deps` | Declared by the loop; derived independently by the gatekeeper |
| `diff_size` | Changed lines | Computed by the gatekeeper |
| `claimed_effect`, `provenance` | What the loop says it does; which component produced it | Loop |

The gatekeeper derives the categories from the paths itself. The loop's labels are evidence, not truth, and a mismatch between declared and derived categories is itself a deny: STOP's "use more efficient scoring mechanism" comment on the line that disabled the sandbox is mislabeled metadata. Rules are ordered, the first match wins, and every decision names its rule so the audit can answer "why". The strict policy built below:

1. `metadata-mismatch` → deny.
2. `evaluator-frozen`, `tests-frozen` → deny.
3. `network-escalate`, `deps-escalate`, `config-escalate` → escalate to a human.
4. `large-diff` (a single edit above 200 changed lines) → escalate.
5. `cycle-cap` (more than 3 applied edits per cycle), `budget-cap` (more than 400 changed lines per cycle) → deny, in practice defer.
6. Anything left, a small code edit → allow.

Escalation is not a failure path; it is the budgeted human channel. In Phase 15 · 10 terms the loop lives permanently in the mode that asks before risky actions and never receives the mode that approves everything. Lesson 19 treats the hours spent on the escalated queue as the scarce trusted labour of AI control (Phase 18 · 10).

### The archive as a hash chain

Every decision, not only the allowed ones, becomes a record: sequence, cycle, kind, proposal id and hash, verdict, rule, the state hash afterwards, and the previous record's hash; the record's own hash is SHA-256 over the canonical JSON of that body. Without the chain, a loop with write access to its history could turn a denied evaluator edit into an allowed one and present a clean audit. With it, altering record *k* breaks record *k*'s hash (a naive edit) or, if the attacker recomputes it, record *k+1*'s `prev_hash`.

The chain has one blind spot: the last record. Rewriting it and recomputing its hash leaves every internal link valid. The fix is the one used for logs: publish the head hash outside the sandbox after every commit. The simulator holds such a copy and verifies with and without it.

Rollback is a record, not a deletion. `rollback(to_id)` restores the applied-edit list to the snapshot stored with `to_id` and appends a `rollback` record; depth grows by one and verification still passes. Phase 15 · 16 asked every action to carry a rollback plan; here the plan is identical for every edit because the archive already holds every state hash. At the inter-cycle audit (Lesson 19) the human reviews the escalated queue, deny counts by rule (a spike in `evaluator-frozen` is itself a signal), the archive head against the published head, and the applied-state hash against the running system.

### Limits

Containment reduces blast radius. It does not fix objectives (Lesson 17) and it does not see semantics. In the simulation the `disable-logging` edit passes the strict policy as a small code edit: a three-line change in `agent/logging.py` is indistinguishable by path and size from a refactor, yet it is the DGM special-token incident in miniature. Capable improvers also find side channels, as STOP's did by constructing a new model object instead of editing the limit. With `--max-edits-per-cycle 1` the `disable-logging` edits happen to be denied by the cap; that is luck, not containment. The honest stack is containment (this lesson), monitoring of behaviour rather than paths (Lesson 19), evaluation-awareness checks (Lesson 20), and governance that decides whether the loop may run at all (Lesson 21).

```figure
mx-propose-then-commit
```

## Build It

### Step 1: The proposal schema

A frozen dataclass with canonical JSON, so the same proposal always hashes to the same value. The gatekeeper classifies paths itself.

```python
PATH_RULES = (("eval/", "evaluator"), ("tests/", "tests"), ("network/", "network"),
              ("deps/", "deps"), ("config/", "config"))

def classify_path(path: str) -> str:
    for prefix, category in PATH_RULES:
        if path.startswith(prefix):
            return category
    return "code"

@dataclass(frozen=True)
class EditProposal:
    id: str
    parent_hash: str
    files: tuple[str, ...]
    categories: tuple[str, ...]      # DECLARED by the loop
    diff_size: int
    claimed_effect: str
    provenance: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()
```

### Step 2: The policy engine

Rules are data: a name, a verdict, and a predicate over the proposal, the derived categories and the cycle state. The policy walks them in order.

```python
@dataclass(frozen=True)
class Rule:
    name: str
    verdict: str          # allow | deny | escalate
    when: Callable[[EditProposal, tuple[str, ...], CycleState, "Policy"], bool]

def decide(self, p: EditProposal, state: CycleState) -> Decision:
    cats = tuple(sorted(p.categories)) if self.trust_declared else derive_categories(p.files)
    for rule in self.rules:
        if rule.when(p, cats, state, self):
            return Decision(rule.verdict, rule.name)
    return Decision("allow", self.default_rule)

rules = [
    Rule("metadata-mismatch", "deny", lambda p, c, s, pol: c != tuple(sorted(p.categories))),
    Rule("evaluator-frozen", "deny", lambda p, c, s, pol: "evaluator" in c),
    Rule("tests-frozen", "deny", lambda p, c, s, pol: "tests" in c),
    Rule("network-escalate", "escalate", lambda p, c, s, pol: "network" in c),
    # ... deps-escalate, config-escalate, large-diff, cycle-cap, budget-cap
]
```

The permissive contrast policy has one rule (escalate a *declared* evaluator edit) and `trust_declared=True`. It is the policy every Lesson 15 incident ran under.

### Step 3: The hash-chained archive with rollback

```python
def _append(self, cycle, kind, proposal_id, proposal_hash, verdict, rule) -> CommitRecord:
    body = {"seq": len(self.records), "cycle": cycle, "kind": kind,
            "proposal_id": proposal_id, "proposal_hash": proposal_hash,
            "verdict": verdict, "rule": rule, "state_hash": self.state_hash(),
            "prev_hash": self.head}
    rec = CommitRecord(**body, record_hash=sha256(canonical(body)))
    self.records.append(rec)
    self._snapshots[rec.record_hash] = tuple(self.applied)
    return rec

def rollback(self, to_id: str, cycle: int) -> tuple[CommitRecord, int]:
    target = next(r for r in self.records if r.kind == "decision" and r.proposal_id == to_id)
    before = len(self.applied)
    self.applied = list(self._snapshots[target.record_hash])
    rec = self._append(cycle, "rollback", to_id, target.record_hash, "rollback", f"rollback->{to_id}")
    return rec, before - len(self.applied)

def verify_chain(records, expected_head=None) -> tuple[bool, int]:
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.prev_hash != prev or sha256(canonical(record_body(rec))) != rec.record_hash:
            return False, i
        prev = rec.record_hash
    if expected_head is not None and prev != expected_head:
        return False, len(records) - 1
    return True, -1
```

### Step 4: The simulated agent and the tamper test

The agent emits benign proposals (small code edits, an occasional large refactor, honest config and dependency changes) and seven kinds of tampering drawn round-robin in a seed-shuffled order: an honest evaluator edit, a mislabeled evaluator edit declared as `code`, a weakened test, a timeout bump, an opened egress policy, an added dependency, and a small logging change. The tamper test copies the archive, flips the verdict of one historical record, and verifies twice: after a naive edit, and after the attacker also recomputes the record's hash.

```python
def tamper_record(records, position, rehash):
    out = list(records)
    flipped = "deny" if out[position].verdict == "allow" else "allow"
    altered = replace(out[position], verdict=flipped, rule="(rewritten)")
    if rehash:
        altered = replace(altered, record_hash=sha256(canonical(record_body(altered))))
    out[position] = altered
    return out
```

## Use It

`code/main.py` runs the pipeline deterministically and prints, per policy, decision counts by matched rule, tampering outcomes by kind, benign throughput, archive depth, a rollback to the record before the first tampering edit that slipped through (or a midpoint drill if nothing slipped), and the tamper test. Flags: `--proposals` (40), `--tamper-rate` (0.25), `--policy strict|permissive|both`, `--seed` (7), `--max-edits-per-cycle` (3), `--max-diff-per-cycle` (400), `--large-diff` (200), `--cycles` (8), `--no-verify-chain`, `--out archive.json`.

With the defaults the stream holds 11 tampering proposals among 40. Strict denies 4, escalates 5 and lets 2 through, both `disable-logging`; permissive denies 0, escalates 2 (the honestly declared evaluator edits) and lets 9 through. Strict auto-applies 21 of 29 benign edits (72.4%); 3 hit the per-cycle cap. The chain verifies at depth 40 and again at depth 41 after the rollback; the tamper test fails at the altered position (24 for strict) after a naive edit and at 25 after a re-hash, while a re-hashed last record is caught only by the published head. Read the `tampering proposals by kind` table first: deny is what frozen paths bought, escalate is the human's workload, allow is the limit of path-based containment.

## Ship It

This lesson produces `outputs/skill-self-edit-gatekeeper.md`. Given a self-modifying loop's architecture (what it may edit, where the evaluator and logs live, which identities exist), the skill produces a containment review: the asset table, the enforcement map, an ordered rule list with verdicts, the archive and rollback contract, and a hard-reject list for designs in which any boundary lives inside the loop's edit surface.

## Exercises

1. Run `python3 main.py` and then `python3 main.py --policy permissive`. List the tampering kinds permissive lets through that strict stops, and explain why the honestly declared evaluator edit does not get through even under permissive, and why that is no comfort.

2. Run `python3 main.py --policy strict --max-edits-per-cycle 1`; the `disable-logging` edits are now denied, but by `cycle-cap`. Then run `python3 main.py --seed 3 --tamper-rate 0.5` with the default cap. Using the two headlines, argue in one paragraph why a throughput cap is not a containment control and what it does buy.

3. Add a rule `logging-escalate` that escalates any edit touching a path containing `agent/logging`. Rerun the default and report how the strict headline changes. Then describe a four-line code edit that blinds the evaluator without touching that path, and name the lesson of this phase that owns its detection.

4. Implement external anchoring: after every commit, append the head hash to a list held outside the `Archive` object, and extend `verify_chain` to check every stored head. Which alterations become detectable that were not before, and what does a rollback record look like under this scheme?

5. (Hard) The gatekeeper trusts `diff_size` and `files` as the simulator reports them; a real one computes both from the diff. Specify the sandbox-to-gatekeeper interface so the loop cannot influence either value: which identity runs the diff, where it is stored, and how the gatekeeper proves to the auditor that the diff it classified is the diff that was applied. Cite the Phase 15 · 15 verify step and the Phase 15 · 16 double-execute failure.

## Key Terms

| Term | What people say | What it actually means |
|---|---|---|
| Containment | "Run it in a sandbox" | Layered controls, each enforced by something outside the loop's edit surface |
| Edit surface | "What the agent can change" | The exact paths and resources the loop may write; everything else is frozen or escalated |
| Egress policy | "Read-only internet" | Default-deny outbound traffic with an allowlist; read-only is not something your proxy can grant |
| Gatekeeper | "The approval step" | The process outside the sandbox that derives metadata, applies ordered rules and names the matched rule |
| Escalate | "Needs human review" | A budgeted channel for categories the policy will not decide automatically; not a failure |
| Hash chain | "Tamper-proof log" | Each record carries the previous record's hash; alteration breaks a link; the last link needs an external anchor |
| Published head | "Checkpoint the log" | A copy of the latest record hash stored where the loop has no credential |
| Rollback record | "Undo" | Restoring an earlier state as a new appended record, never by truncating history |
| Side channel | "Loophole" | A route to the same effect that the policy does not classify, such as blinding the evaluator from the scaffold side |

## Further Reading

- [Zelikman, Lorch, Mackey, Kalai — Self-Taught Optimizer (STOP), COLM 2024 (arXiv:2310.02304)](https://arxiv.org/abs/2310.02304) — Section 6.2 and Table 2 hold the sandbox-flag bypass rates quoted above.
- [Zhang, Hu, Lu, Lange, Clune — Darwin Gödel Machine (arXiv:2505.22954)](https://arxiv.org/abs/2505.22954) — the fake-test-log and removed-logging incidents in the authors' own words.
- [Sakana AI — The AI Scientist](https://sakana.ai/ai-scientist/) — the timeout-extension incident and the Docker recommendation.
- [METR — Recent Frontier Models Are Reward Hacking (June 2025)](https://metr.org/blog/2025-06-05-recent-reward-hacking/) — what models do to scoring bugs and task setups they can reach.
- [The Next Web — OpenAI agents hijacked a German wiki for two months, researchers say (Sep 2026)](https://thenextweb.com/news/openai-agents-german-wiki-breakout) — one of the DSEwiki press reports; reporting, not a primary source.
- [gVisor documentation](https://gvisor.dev/docs/) — a production application-kernel sandbox; what "enforced by something the code cannot call" looks like.
- [Phase 15 · 15 — Propose-Then-Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/en.md), [Phase 15 · 16 — Checkpoints and Rollback](../../../15-autonomous-systems/16-checkpoints-rollback/docs/en.md), [Phase 15 · 06 — Automated Alignment Research](../../../15-autonomous-systems/06-automated-alignment-research/docs/en.md) — the state machine, rollback contract and out-of-sandbox log this lesson specializes to self-edits.
