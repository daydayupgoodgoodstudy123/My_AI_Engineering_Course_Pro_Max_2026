"""Behavior tests for 08-building-an-mcp-client; default target is starter."""
import unittest
from _support import m

class Peer:

    def __init__(self, names):
        self.tools = [{'name': n, 'schema': {}} for n in names]
        self.seen = []

    def list_tools(self):
        return self.tools

    def call(self, name, args):
        self.seen.append((name, args))
        return {'peer_result': name}

class CoreTests(unittest.TestCase):

    def test_merge_and_route(self):
        a, b = (Peer(['read']), Peer(['read']))
        c = m.Client({'b': b, 'a': a})
        self.assertEqual(c.discover(), ['a::read', 'b::read'])
        self.assertEqual(c.call('b::read', {'id': 1}), {'peer_result': 'read'})
        self.assertEqual(a.seen, [])
        self.assertEqual(b.seen, [('read', {'id': 1})])

    def test_before_discovery(self):
        with self.assertRaises(KeyError):
            m.Client({'a': Peer(['read'])}).call('a::read', {})

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            m.Client({'a': Peer(['read', 'read'])}).discover()

    def test_delimiter(self):
        for peers in ({'a::b': Peer(['r'])}, {'a': Peer(['b::r'])}):
            with self.subTest(peers=peers), self.assertRaises(ValueError):
                m.Client(peers).discover()

    def test_atomic_refresh(self):
        p = Peer(['read'])
        c = m.Client({'a': p})
        c.discover()
        p.tools = [{'name': 'new'}, {'name': 'new'}]
        with self.assertRaises(ValueError):
            c.discover()
        self.assertEqual(c.call('a::read', {}), {'peer_result': 'read'})

    def test_empty(self):
        self.assertEqual(m.Client({}).discover(), [])

class BonusTests(unittest.TestCase):

    def test_descriptor_copy(self):
        c = m.Client({'a': Peer(['read'])})
        c.discover()
        d = c.descriptor('a::read')
        d['schema']['x'] = 1
        self.assertEqual(c.descriptor('a::read'), {'name': 'a::read', 'schema': {}})

    def test_unknown(self):
        with self.assertRaises(KeyError):
            m.Client({}).descriptor('missing')
