"""Behavior tests for 13-mcp-async-tasks; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'tasks.json'
        self.s = m.TaskStore(self.path)

    def test_create_restart(self):
        self.assertEqual(self.s.create('t', 'a'), {'id': 't', 'owner': 'a', 'status': 'queued'})
        self.assertEqual(m.TaskStore(self.path).get('t')['status'], 'queued')

    def test_duplicate(self):
        self.s.create('t', 'a')
        with self.assertRaises(ValueError):
            self.s.create('t', 'b')
        self.assertEqual(m.TaskStore(self.path).get('t')['owner'], 'a')

    def test_complete_restart(self):
        self.s.create('t', 'a')
        self.s.transition('t', 'a', 'working')
        self.s.transition('t', 'a', 'completed')
        self.assertEqual(m.TaskStore(self.path).get('t')['status'], 'completed')

    def test_invalid_no_change(self):
        self.s.create('t', 'a')
        with self.assertRaises(ValueError):
            self.s.transition('t', 'a', 'completed')
        self.assertEqual(m.TaskStore(self.path).get('t')['status'], 'queued')

    def test_ownership_and_unknown(self):
        self.s.create('t', 'a')
        for task, owner in (('t', 'b'), ('missing', 'a')):
            with self.subTest(task=task), self.assertRaises(KeyError):
                self.s.transition(task, owner, 'working')

    def test_terminal_and_copy(self):
        self.s.create('t', 'a')['status'] = 'bad'
        self.s.transition('t', 'a', 'canceled')
        with self.assertRaises(ValueError):
            self.s.transition('t', 'a', 'working')

class BonusTests(unittest.TestCase):
    setUp = CoreTests.setUp

    def test_purge(self):
        self.s.create('z', 'a')
        self.s.create('a', 'a')
        self.s.transition('z', 'a', 'canceled')
        self.assertEqual(self.s.purge_terminal(), ['z'])
        self.assertEqual(m.TaskStore(self.path).get('a')['status'], 'queued')
