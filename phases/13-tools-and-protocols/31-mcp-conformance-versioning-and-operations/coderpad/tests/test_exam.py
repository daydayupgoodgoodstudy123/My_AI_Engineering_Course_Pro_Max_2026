"""Behavior tests for 31-mcp-conformance-versioning-and-operations; default target is starter."""
import unittest
from _support import m

GOOD = {'transcripts': [True, True], 'redacted': True, 'rollback_tested': True, 'health': {'requests': 100, 'errors': 1, 'p95_ms': 500}}

class CoreTests(unittest.TestCase):

    def test_extension_allowed(self):
        self.assertTrue(m.compare({'resultType': 'complete', 'x-extra': 1}, {'resultType': 'complete'}, set()))

    def test_additive_field_preserved(self):
        with self.assertRaises(ValueError):
            m.compare({'resultType': 'complete', 'newField': 1}, {'resultType': 'complete'}, set())

    def test_result_type_capability(self):
        with self.assertRaises(ValueError):
            m.compare({'resultType': 'task'}, {'resultType': 'task'}, set())
        self.assertTrue(m.compare({'resultType': 'task'}, {'resultType': 'task'}, {'tasks'}))
        with self.assertRaises(ValueError):
            m.compare({'resultType': 'unknown'}, {}, set())
        with self.assertRaises(ValueError):
            m.compare({'resultType': []}, {}, set())

    def test_bool_not_int(self):
        with self.assertRaises(ValueError):
            m.compare({'resultType': 'complete', 'v': True}, {'resultType': 'complete', 'v': 1}, set())

    def test_release_boundary(self):
        self.assertEqual(m.release(GOOD), {'ready': True, 'reasons': []})

    def test_missing_evidence(self):
        self.assertEqual(m.release({})['reasons'], ['health', 'redacted', 'rollback', 'transcripts'])

    def test_unhealthy(self):
        self.assertEqual(m.release(dict(GOOD, health={'requests': 100, 'errors': 2, 'p95_ms': 1}))['reasons'], ['health'])

class BonusTests(unittest.TestCase):

    def test_rate(self):
        self.assertEqual(m.failure_rate(GOOD), 0.01)

    def test_zero_requests(self):
        with self.assertRaises(ValueError):
            m.failure_rate({'health': {'requests': 0, 'errors': 0}})
