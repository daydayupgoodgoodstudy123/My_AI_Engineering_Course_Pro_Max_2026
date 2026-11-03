"""Behavior tests for 07-building-an-mcp-server; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def setUp(self):
        self.s = m.NotesServer()

    def test_create_and_get(self):
        self.assertEqual(self.s.call('notes_create', {'title': ' A '}), {'ok': True, 'value': {'id': 1, 'title': 'A'}})
        self.assertEqual(self.s.call('notes_get', {'id': 1})['value']['title'], 'A')

    def test_invalid_no_id_consumed(self):
        for a in ({'title': ' '}, {'title': 1}, {'title': 'x' * 81}, {'title': 'a', 'id': 1}):
            with self.subTest(a=a):
                self.assertEqual(self.s.call('notes_create', a)['error'], 'invalid_arguments')
        self.assertEqual(self.s.call('notes_create', {'title': 'good'})['value']['id'], 1)

    def test_not_found(self):
        self.assertEqual(self.s.call('notes_get', {'id': 1}), {'ok': False, 'error': 'not_found'})

    def test_strict_id(self):
        self.assertEqual(self.s.call('notes_get', {'id': True})['error'], 'invalid_arguments')

    def test_unknown(self):
        self.assertEqual(self.s.call('delete', None)['error'], 'unknown_tool')

    def test_defensive_copy(self):
        self.s.call('notes_create', {'title': 'a'})['value']['title'] = 'bad'
        r = self.s.call('notes_get', {'id': 1})
        r['value']['title'] = 'also bad'
        self.assertEqual(self.s.call('notes_get', {'id': 1})['value']['title'], 'a')

class BonusTests(unittest.TestCase):

    def test_discovery(self):
        self.assertEqual(m.NotesServer().list_tools(), ['notes_create', 'notes_get'])

    def test_search(self):
        s = m.NotesServer()
        for title in ('Beta', 'ALPHA', 'alphabet'):
            s.call('notes_create', {'title': title})
        self.assertEqual([n['id'] for n in s.search('alpha')], [2, 3])
