"""Tests for the self-edit gatekeeper simulator (Phase 20, Lesson 18)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as m  # noqa: E402


def proposal(pid: str = "p-001", files=("agent/search.py",), declared=None,
             diff_size: int = 10, parent: str = m.GENESIS) -> m.EditProposal:
    files = tuple(files)
    declared = tuple(declared) if declared is not None else m.derive_categories(files)
    return m.EditProposal(id=pid, parent_hash=parent, files=files, categories=declared,
                          diff_size=diff_size, claimed_effect="test", provenance="test@cycle0")


class SchemaTests(unittest.TestCase):
    def test_round_trip_and_stable_hash(self) -> None:
        p = proposal(files=("eval/score.py", "agent/x.py"), declared=("code", "evaluator"))
        text = p.to_json()
        back = m.EditProposal.from_json(text)
        self.assertEqual(p, back)
        self.assertEqual(p.content_hash(), back.content_hash())
        self.assertEqual(len(p.content_hash()), 64)
        self.assertNotEqual(p.content_hash(), proposal(diff_size=11).content_hash())

    def test_derive_categories_from_paths(self) -> None:
        self.assertEqual(m.derive_categories(("tests/t.py", "eval/s.py", "agent/a.py")),
                         ("code", "evaluator", "tests"))
        self.assertEqual(m.classify_path("network/egress.json"), "network")
        self.assertEqual(m.classify_path("anything/else.py"), "code")


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pol = m.strict_policy(max_edits_per_cycle=3, max_diff_per_cycle=400, large_diff=200)
        self.state = m.CycleState()

    def test_each_deny_rule_fires(self) -> None:
        cases = {
            "evaluator-frozen": proposal(files=("eval/score.py",)),
            "tests-frozen": proposal(files=("tests/test_agent.py",)),
            "metadata-mismatch": proposal(files=("eval/score.py",), declared=("code",)),
        }
        for rule, p in cases.items():
            d = self.pol.decide(p, self.state)
            self.assertEqual((d.verdict, d.rule), ("deny", rule), msg=rule)
        full = m.CycleState(edits_applied=3)
        d = self.pol.decide(proposal(), full)
        self.assertEqual((d.verdict, d.rule), ("deny", "cycle-cap"))
        spent = m.CycleState(edits_applied=1, diff_applied=395)
        d = self.pol.decide(proposal(diff_size=10), spent)
        self.assertEqual((d.verdict, d.rule), ("deny", "budget-cap"))

    def test_escalation_on_network_deps_config_and_large_diff(self) -> None:
        expect = {
            ("network/egress_policy.json",): "network-escalate",
            ("deps/requirements.txt",): "deps-escalate",
            ("config/limits.yaml",): "config-escalate",
        }
        for files, rule in expect.items():
            d = self.pol.decide(proposal(files=files), self.state)
            self.assertEqual((d.verdict, d.rule), ("escalate", rule), msg=rule)
        d = self.pol.decide(proposal(diff_size=201), self.state)
        self.assertEqual((d.verdict, d.rule), ("escalate", "large-diff"))

    def test_small_code_edit_allowed_and_permissive_trusts_labels(self) -> None:
        d = self.pol.decide(proposal(diff_size=20), self.state)
        self.assertEqual((d.verdict, d.rule), ("allow", "small-code-edit"))
        perm = m.permissive_policy()
        lying = proposal(files=("eval/score.py",), declared=("code",))
        self.assertEqual(perm.decide(lying, self.state).verdict, "allow")
        self.assertEqual(self.pol.decide(lying, self.state).verdict, "deny")

    def test_per_cycle_cap_resets_each_cycle(self) -> None:
        # five small code edits in cycle 0, two in cycle 1: cap 3 must fire twice, then reset
        stream = [m.Emitted(proposal(pid=f"p-{i:03d}"), m.BENIGN, "small-code", cycle=0 if i < 5 else 1)
                  for i in range(7)]
        res = m.run_policy(self.pol, stream)
        verdicts = [(r.cycle, r.verdict, r.rule) for r in res.archive.records]
        self.assertEqual(verdicts[:5], [(0, "allow", "small-code-edit")] * 3
                         + [(0, "deny", "cycle-cap")] * 2)
        self.assertEqual(verdicts[5:], [(1, "allow", "small-code-edit")] * 2)
        self.assertEqual(res.archive.applied, ["p-000", "p-001", "p-002", "p-005", "p-006"])


class ArchiveTests(unittest.TestCase):
    def _archive(self) -> m.Archive:
        arc = m.Archive()
        pol = m.strict_policy()
        state = m.CycleState()
        files = [("agent/a.py",), ("agent/b.py",), ("eval/score.py",), ("agent/c.py",)]
        for i, f in enumerate(files):
            p = proposal(pid=f"p-{i + 1:03d}", files=f)
            d = pol.decide(p, state)
            if d.verdict == "allow":
                state.edits_applied += 1
            arc.commit(p, d, cycle=0)
        return arc

    def test_chain_verifies_then_fails_after_tamper(self) -> None:
        arc = self._archive()
        ok, pos = m.verify_chain(arc.records, arc.head)
        self.assertEqual((ok, pos), (True, -1))
        self.assertEqual(arc.records[0].prev_hash, m.GENESIS)
        naive = m.tamper_record(arc.records, 2, rehash=False)
        self.assertEqual(m.verify_chain(naive, arc.head), (False, 2))
        rehashed = m.tamper_record(arc.records, 2, rehash=True)
        self.assertEqual(m.verify_chain(rehashed, arc.head), (False, 3))
        last = m.tamper_record(arc.records, 3, rehash=True)
        self.assertEqual(m.verify_chain(last)[0], True)          # internal links cannot see it
        self.assertEqual(m.verify_chain(last, arc.head), (False, 3))  # the published head can

    def test_rollback_restores_state_and_appends(self) -> None:
        arc = self._archive()
        self.assertEqual(arc.applied, ["p-001", "p-002", "p-004"])
        snapshot_after_p002 = next(r.state_hash for r in arc.records if r.proposal_id == "p-002")
        depth = arc.depth()
        rec, reverted = arc.rollback("p-002", cycle=1)
        self.assertEqual(arc.applied, ["p-001", "p-002"])
        self.assertEqual(reverted, 1)
        self.assertEqual(arc.state_hash(), snapshot_after_p002)
        self.assertEqual(arc.depth(), depth + 1)
        self.assertEqual(rec.kind, "rollback")
        self.assertEqual(m.verify_chain(arc.records, arc.head), (True, -1))


class SimulationTests(unittest.TestCase):
    def test_determinism_same_seed_same_heads(self) -> None:
        heads = []
        for _ in range(2):
            stream = m.simulate_stream(40, 0.25, 8, random.Random(m.DEFAULT_SEED))
            res = m.run_policy(m.strict_policy(), stream)
            heads.append((res.archive.head, dict(res.rule_counts)))
        self.assertEqual(heads[0], heads[1])
        other = m.run_policy(m.strict_policy(),
                             m.simulate_stream(40, 0.25, 8, random.Random(m.DEFAULT_SEED + 1)))
        self.assertNotEqual(other.archive.head, heads[0][0])

    def test_strict_lets_through_no_more_tampering_than_permissive(self) -> None:
        for seed in range(6):
            stream = m.simulate_stream(60, 0.4, 6, random.Random(seed))
            strict = m.run_policy(m.strict_policy(), stream)
            perm = m.run_policy(m.permissive_policy(), stream)
            self.assertLessEqual(len(strict.slipped), len(perm.slipped), msg=f"seed {seed}")
            self.assertEqual(strict.n_tamper, perm.n_tamper)
            # the only tampering that can pass strict is the small code edit
            self.assertTrue(all(kind == "disable-logging" for kind, _ in strict.slipped))


if __name__ == "__main__":
    unittest.main()
