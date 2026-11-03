"""Behavior tests for 11-mcp-sampling; default target is starter."""
import unittest
from _support import m

STATE = {'principal': 'a', 'method': 'summarize', 'arguments': {'id': 1}, 'expires': 10}

class CoreTests(unittest.TestCase):

    def token(self):
        return m.seal(STATE, b'test-secret')

    def test_roundtrip(self):
        self.assertEqual(m.verify(self.token(), b'test-secret', 'a', 'summarize', {'id': 1}, 9), STATE)

    def test_canonical(self):
        self.assertEqual(m.seal({'b': 2, 'a': 1}, b's'), m.seal({'a': 1, 'b': 2}, b's'))

    def test_binding(self):
        for p, method, args in (('b', 'summarize', {'id': 1}), ('a', 'delete', {'id': 1}), ('a', 'summarize', {'id': 2}), ('a', 'summarize', {'id': True})):
            with self.subTest(p=p, method=method, args=args), self.assertRaises(ValueError):
                m.verify(self.token(), b'test-secret', p, method, args, 0)

    def test_expired(self):
        with self.assertRaises(ValueError):
            m.verify(self.token(), b'test-secret', 'a', 'summarize', {'id': 1}, 10)

    def test_tamper_and_wrong_key(self):
        with self.assertRaises(ValueError):
            m.verify(self.token() + '0', b'test-secret', 'a', 'summarize', {'id': 1}, 0)
        with self.assertRaises(ValueError):
            m.verify(self.token(), b'wrong', 'a', 'summarize', {'id': 1}, 0)

    def test_malformed(self):
        for token in ('bad', '@@@.x', '..'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                m.verify(token, b's', 'a', 'm', {}, 0)

class BonusTests(unittest.TestCase):

    def test_round(self):
        self.assertEqual(m.next_round(0, 2), 1)

    def test_limit(self):
        for a, b in ((2, 2), (-1, 2), (0, 0), (True, 2)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                m.next_round(a, b)
