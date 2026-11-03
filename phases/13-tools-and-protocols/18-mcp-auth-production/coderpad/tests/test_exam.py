"""Behavior tests for 18-mcp-auth-production; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_token_isolation(self):
        c = {('i', 'r'): {'token': 'secret', 'exp': 10}}
        self.assertEqual(m.token_for(c, 'i', 'r', 9), c['i', 'r'])
        self.assertIsNone(m.token_for(c, 'other', 'r', 9))
        self.assertIsNone(m.token_for(c, 'i', 'other', 9))

    def test_expired(self):
        self.assertIsNone(m.token_for({('i', 'r'): {'token': 't', 'exp': 10}}, 'i', 'r', 10))

    def test_copy(self):
        c = {('i', 'r'): {'token': 't', 'exp': 10}}
        m.token_for(c, 'i', 'r', 0)['token'] = 'changed'
        self.assertEqual(c['i', 'r']['token'], 't')

    def test_cache_hit(self):
        c = m.KeyCache(10)
        seen = []

        def fetch():
            seen.append(1)
            return {'k': 'key'}
        self.assertEqual(c.get('k', 0, fetch), 'key')
        self.assertEqual(c.get('k', 9, fetch), 'key')
        self.assertEqual(len(seen), 1)

    def test_rotation_and_unknown(self):
        c = m.KeyCache(10)
        c.get('old', 0, lambda: {'old': 'v1'})
        self.assertEqual(c.get('new', 1, lambda: {'new': 'v2'}), 'v2')
        seen = []
        with self.assertRaises(KeyError):
            c.get('missing', 2, lambda: seen.append(1) or {'new': 'v2'})
        self.assertEqual(len(seen), 1)

    def test_refresh_failure(self):
        c = m.KeyCache(10)
        c.get('k', 0, lambda: {'k': 'v'})

        def fail():
            raise RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            c.get('k', 10, fail)
        self.assertEqual(c.keys, {'k': 'v'})
        self.assertEqual(c.expires, 10)

class BonusTests(unittest.TestCase):

    def test_invalidate(self):
        c = {('i', 'a'): 1, ('i', 'b'): 2, ('j', 'a'): 3}
        self.assertEqual(m.invalidate(c, 'i'), 2)
        self.assertEqual(c, {('j', 'a'): 3})

    def test_no_matches(self):
        self.assertEqual(m.invalidate({}, 'i'), 0)
