"""Behavior tests for 20-opentelemetry-genai; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_nested_redaction(self):
        self.assertEqual(m.redact({'x': [{'Authorization': 'secret', 'prompt': 'hi'}], 'ok': 1}), {'x': [{'Authorization': '[REDACTED]', 'prompt': '[REDACTED]'}], 'ok': 1})

    def test_opt_in_still_redacts_secret(self):
        self.assertEqual(m.redact({'prompt': 'hi', 'token': 'secret'}, True), {'prompt': 'hi', 'token': '[REDACTED]'})

    def test_copy(self):
        x = {'a': [1]}
        m.redact(x)['a'].append(2)
        self.assertEqual(x, {'a': [1]})

    def test_aggregate(self):
        self.assertEqual(m.summarize([{'name': 'tool', 'start': 0, 'end': 5}, {'name': 'tool', 'start': 2, 'end': 9}]), {'tool': {'count': 2, 'total_ms': 12, 'max_ms': 7}})

    def test_invalid_time(self):
        with self.assertRaises(ValueError):
            m.summarize([{'name': 'x', 'start': 2, 'end': 1}])

    def test_empty(self):
        self.assertEqual(m.summarize([]), {})

class BonusTests(unittest.TestCase):

    def test_tie(self):
        self.assertEqual(m.critical_span([{'name': 'z', 'start': 0, 'end': 2}, {'name': 'a', 'start': 1, 'end': 3}]), 'a')

    def test_empty(self):
        self.assertIsNone(m.critical_span([]))
