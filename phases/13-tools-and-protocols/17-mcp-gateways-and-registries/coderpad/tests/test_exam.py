"""Behavior tests for 17-mcp-gateways-and-registries; default target is starter."""
import unittest
from _support import m

ROUTES = {'a::read': {'peer': 'a', 'local': 'read', 'roles': {'reader', 'admin'}, 'pin': 'v1'}}

class CoreTests(unittest.TestCase):

    def setUp(self):
        self.fetched = []
        self.calls = []
        self.g = m.Gateway(ROUTES, lambda p, n: self.fetched.append((p, n)) or 'v1', lambda p, n, a: self.calls.append((p, n, a)) or 'done')

    def test_forward(self):
        self.assertEqual(self.g.call('a::read', {'reader'}, {'x': 1}), 'done')
        self.assertEqual(self.calls, [('a', 'read', {'x': 1})])

    def test_unknown(self):
        with self.assertRaises(KeyError):
            self.g.call('read', {'admin'}, {})
        self.assertEqual(self.calls, [])

    def test_denied_before_fetch(self):
        with self.assertRaises(PermissionError):
            self.g.call('a::read', {'guest'}, {})
        self.assertEqual(self.fetched, [])
        self.assertEqual(self.calls, [])

    def test_drift(self):
        self.g.fetch = lambda p, n: 'v2'
        with self.assertRaises(ValueError):
            self.g.call('a::read', {'admin'}, {})
        self.assertEqual(self.calls, [])

    def test_fetch_failure(self):

        def fail(p, n):
            raise RuntimeError('offline')
        self.g.fetch = fail
        with self.assertRaisesRegex(RuntimeError, 'offline'):
            self.g.call('a::read', {'admin'}, {})
        self.assertEqual(self.calls, [])

    def test_empty_roles(self):
        with self.assertRaises(PermissionError):
            self.g.call('a::read', set(), {})

class BonusTests(unittest.TestCase):

    def test_visible(self):
        self.assertEqual(m.Gateway(ROUTES, None, None).visible({'reader'}), ['a::read'])

    def test_hidden(self):
        self.assertEqual(m.Gateway(ROUTES, None, None).visible({'guest'}), [])
