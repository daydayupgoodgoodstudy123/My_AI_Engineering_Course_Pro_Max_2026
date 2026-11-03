"""Behavior tests for 14-mcp-apps; default target is starter."""
import unittest
from _support import m

MSG = {'id': '1', 'method': 'notes/read', 'params': {'id': 1}}

class CoreTests(unittest.TestCase):

    def test_read(self):
        self.assertEqual(m.bridge('good', MSG, 'good', {'read'}), dict(MSG, ok=True))

    def test_origin_first(self):
        self.assertEqual(m.bridge('bad', None, 'good', set())['error'], 'origin')

    def test_message(self):
        self.assertEqual(m.bridge('good', {}, 'good', {'read'})['error'], 'message')

    def test_permission(self):
        self.assertEqual(m.bridge('good', dict(MSG, method='notes/export'), 'good', {'read'})['error'], 'permission')

    def test_unknown(self):
        self.assertEqual(m.bridge('good', dict(MSG, method='shell'), 'good', {'read'})['error'], 'method')

    def test_escape(self):
        self.assertEqual(m.timeline(['<script>', 'a&b']), '<ul><li>&lt;script&gt;</li><li>a&amp;b</li></ul>')

    def test_copy(self):
        msg = {'id': 'x', 'method': 'notes/read', 'params': {'a': []}}
        r = m.bridge('g', msg, 'g', {'read'})
        r['params']['a'].append(1)
        self.assertEqual(msg['params'], {'a': []})

class BonusTests(unittest.TestCase):

    def test_resource(self):
        self.assertEqual(m.resource('ui://timeline', True), {'uri': 'ui://timeline', 'mimeType': 'text/html'})

    def test_disabled(self):
        for uri, enabled in (('ui://a', False), ('https://a', True), ('ui://', True)):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                m.resource(uri, enabled)
