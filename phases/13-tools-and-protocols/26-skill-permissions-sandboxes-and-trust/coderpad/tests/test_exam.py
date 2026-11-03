"""Behavior tests for 26-skill-permissions-sandboxes-and-trust; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = {'capabilities': {'write'}, 'root': self.tmp.name, 'origins': {'https://api.example'}}
        self.a = {'capability': 'write', 'path': 'out.txt', 'origin': None, 'side_effect': False, 'approved': False}

    def test_allow(self):
        self.assertEqual(m.review(self.a, self.p), {'verdict': 'allow', 'rule': 'policy'})

    def test_capability_before_approval(self):
        self.assertEqual(m.review(dict(self.a, capability='shell', approved=True), self.p), {'verdict': 'deny', 'rule': 'capability'})

    def test_path(self):
        self.assertEqual(m.review(dict(self.a, path='../secret'), self.p)['rule'], 'path')

    def test_exact_origin(self):
        self.assertEqual(m.review(dict(self.a, origin='https://api.example.evil'), self.p)['rule'], 'origin')

    def test_approval(self):
        self.assertEqual(m.review(dict(self.a, side_effect=True), self.p), {'verdict': 'ask', 'rule': 'approval'})
        self.assertEqual(m.review(dict(self.a, side_effect=True, approved=True), self.p)['verdict'], 'allow')

    def test_no_file_created(self):
        from pathlib import Path
        m.review(self.a, self.p)
        self.assertFalse((Path(self.tmp.name) / 'out.txt').exists())

class BonusTests(unittest.TestCase):

    def test_exact(self):
        self.assertTrue(m.command_allowed(['python3', 'check.py'], {('python3', 'check.py')}))

    def test_no_extra(self):
        self.assertFalse(m.command_allowed(['python3', 'check.py', '--upload'], {('python3', 'check.py')}))
        self.assertFalse(m.command_allowed('python3 check.py', {('python3', 'check.py')}))
