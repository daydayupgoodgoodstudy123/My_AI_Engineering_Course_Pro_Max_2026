"""Behavior tests for 10-mcp-resources-and-prompts; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_private_cache(self):
        c = m.Cache()
        c.put('alice', 'notes://a', {'text': 'secret'}, 10, 5)
        self.assertEqual(c.get('alice', 'notes://a', 14), {'text': 'secret'})
        self.assertIsNone(c.get('bob', 'notes://a', 14))

    def test_expiry_boundary(self):
        c = m.Cache()
        c.put('a', 'u', 1, 10, 5)
        self.assertIsNone(c.get('a', 'u', 15))
        c.put('a', 'z', 2, 10, 0)
        self.assertIsNone(c.get('a', 'z', 10))

    def test_copy(self):
        c = m.Cache()
        v = {'x': []}
        c.put('a', 'u', v, 0, 5)
        v['x'].append(1)
        c.get('a', 'u', 1)['x'].append(2)
        self.assertEqual(c.get('a', 'u', 1), {'x': []})

    def test_ttl(self):
        with self.assertRaises(ValueError):
            m.Cache().put('a', 'u', 1, 0, -1)

    def test_render(self):
        self.assertEqual(m.render('summarize', {'text': ' hi '}), [{'role': 'user', 'content': 'Summarize: hi'}])

    def test_bad_prompt(self):
        with self.assertRaises(KeyError):
            m.render('delete', {})
        for a in ({}, {'text': ' '}, {'text': 'a', 'extra': 1}):
            with self.subTest(a=a), self.assertRaises(ValueError):
                m.render('summarize', a)

class BonusTests(unittest.TestCase):

    def test_kinds(self):
        self.assertEqual([m.resource_kind(x) for x in ('notes://a', 'ui://b')], ['resource', 'ui'])

    def test_bad_uri(self):
        for uri in ('notes://', 'https://a', None):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                m.resource_kind(uri)
