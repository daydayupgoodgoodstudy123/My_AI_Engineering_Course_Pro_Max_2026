"""Behavior tests for 21-llm-routing-layer; default target is starter."""
import unittest
from _support import m

def ok(prompt):
    return {'text': prompt.upper(), 'input_tokens': 2, 'output_tokens': 3}

def transient(prompt):
    raise m.TransientError('offline')

class CoreTests(unittest.TestCase):

    def test_success_cost(self):
        self.assertEqual(m.route([('a', ok)], 'hi', {'a': (2, 3)}), {'provider': 'a', 'text': 'HI', 'attempted': ['a'], 'cost': 13})

    def test_fallback(self):
        self.assertEqual(m.route([('a', transient), ('b', ok)], 'x', {'b': (1, 1)})['attempted'], ['a', 'b'])

    def test_stop_after_success(self):

        def fail(p):
            self.fail('should not run')
        self.assertEqual(m.route([('a', ok), ('b', fail)], 'x', {'a': (0, 0)})['provider'], 'a')

    def test_permanent_error(self):
        seen = []

        def bad(p):
            raise ValueError('invalid request')
        with self.assertRaises(ValueError):
            m.route([('a', bad), ('b', lambda p: seen.append(p))], 'x', {})
        self.assertEqual(seen, [])

    def test_exhausted(self):
        with self.assertRaises(m.ExhaustedError) as ctx:
            m.route([('a', transient)], 'x', {})
        self.assertEqual(ctx.exception.attempted, ['a'])

    def test_empty(self):
        with self.assertRaises(m.ExhaustedError) as ctx:
            m.route([], 'x', {})
        self.assertEqual(ctx.exception.attempted, [])

class BonusTests(unittest.TestCase):

    def test_capabilities(self):
        self.assertEqual(m.eligible([{'name': 'z', 'price': 1, 'capabilities': {'tools'}}, {'name': 'a', 'price': 1, 'capabilities': {'tools'}}, {'name': 'b', 'price': 0, 'capabilities': set()}], {'tools'}), ['a', 'z'])

    def test_empty(self):
        self.assertEqual(m.eligible([], {'tools'}), [])
