"""Behavior tests for 04-structured-output; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_success(self):
        self.assertEqual(m.extract('{"title":" A ","score":0}'), {'kind': 'ok', 'value': {'title': 'A', 'score': 0}})

    def test_refusal_precedence(self):
        self.assertEqual(m.extract('{', 'policy'), {'kind': 'refusal', 'reason': 'policy'})

    def test_parse(self):
        self.assertEqual(m.extract('{'), {'kind': 'parse_error'})

    def test_shape(self):
        for raw in ('[]', 'null', '{"title":"a"}', '{"title":"a","score":1,"extra":1}'):
            with self.subTest(raw=raw):
                self.assertEqual(m.extract(raw), {'kind': 'schema_error'})

    def test_strict_score(self):
        import json
        for v in (True, 2.0, '2', None, -1, 6):
            with self.subTest(v=v):
                self.assertEqual(m.extract(json.dumps({'title': 'a', 'score': v})), {'kind': 'schema_error'})

    def test_title_bounds(self):
        import json
        for v in (' ', 'x' * 81, 7):
            with self.subTest(v=v):
                self.assertEqual(m.extract(json.dumps({'title': v, 'score': 1})), {'kind': 'schema_error'})
        self.assertEqual(m.extract(json.dumps({'title': 'x' * 80, 'score': 5}))['kind'], 'ok')

class BonusTests(unittest.TestCase):

    def test_batch_isolation(self):
        r = m.extract_many([{'raw': '{'}, {'raw': '{"title":"a","score":1}'}])
        self.assertEqual(r['ok_count'], 1)
        self.assertEqual([x['kind'] for x in r['items']], ['parse_error', 'ok'])

    def test_empty(self):
        self.assertEqual(m.extract_many([]), {'items': [], 'ok_count': 0})
