"""Behavior tests for 30-mcp-registry-supply-chain-and-drift; default target is starter."""
import unittest
from _support import m

RECORD = {'name': 'org.example.notes', 'status': 'active', 'source_digest': 'a' * 64, 'tools_digest': 'b' * 64}
EVIDENCE = {'namespace': 'org.example', 'source_digest': 'a' * 64, 'live_digest': 'b' * 64}

class CoreTests(unittest.TestCase):

    def test_admit(self):
        r = m.Registry('org.example')
        self.assertEqual(r.admit('1', RECORD, EVIDENCE), '1')
        self.assertEqual(r.active, '1')

    def test_independent_namespace(self):
        r = m.Registry('org.example')
        with self.assertRaises(ValueError):
            r.admit('1', RECORD, dict(EVIDENCE, namespace='other'))
        self.assertEqual(r.history, [])
        self.assertIsNone(r.active)

    def test_invalid_evidence(self):
        for patch in ({'status': 'deleted'}, {'name': 'org.exampleevil.notes'}, {'tools_digest': 'x' * 64}, {'source_digest': 'c' * 64}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                m.Registry('org.example').admit('1', dict(RECORD, **patch), EVIDENCE)

    def test_duplicate(self):
        r = m.Registry('org.example')
        r.admit('1', RECORD, EVIDENCE)
        with self.assertRaises(ValueError):
            r.admit('1', RECORD, EVIDENCE)
        self.assertEqual(len(r.history), 1)

    def test_drift_quarantines(self):
        r = m.Registry('org.example')
        r.admit('1', RECORD, EVIDENCE)
        self.assertFalse(r.observe('c' * 64, 'active'))
        self.assertIsNone(r.active)
        self.assertEqual(r.history[-1], ('quarantine', '1'))

    def test_healthy_no_history(self):
        r = m.Registry('org.example')
        r.admit('1', RECORD, EVIDENCE)
        self.assertTrue(r.observe('b' * 64, 'active'))
        self.assertEqual(len(r.history), 1)

class BonusTests(unittest.TestCase):

    def test_rollback_preserves_history(self):
        r = m.Registry('org.example')
        r.admit('1', RECORD, EVIDENCE)
        r.admit('2', RECORD, EVIDENCE)
        r.observe('bad', 'active')
        r.rollback('1')
        self.assertEqual(r.active, '1')
        self.assertEqual(len(r.admitted), 2)
        self.assertEqual(r.history[-2:], [('quarantine', '2'), ('rollback', '1')])

    def test_unknown_rollback(self):
        with self.assertRaises(KeyError):
            m.Registry('org.example').rollback('missing')
