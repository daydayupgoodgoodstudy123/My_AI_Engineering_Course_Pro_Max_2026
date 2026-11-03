"""Behavior tests for 12-mcp-roots-and-elicitation; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_paths(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'work'
            root.mkdir()
            self.assertTrue(m.within(root, 'a/b'))
            self.assertTrue(m.within(root, root))
            self.assertFalse(m.within(root, '../outside'))
            self.assertFalse(m.within(root, Path(d) / 'workspace'))

    def test_symlink_escape(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'work'
            root.mkdir()
            outside = Path(d) / 'out'
            outside.mkdir()
            (root / 'link').symlink_to(outside, target_is_directory=True)
            self.assertFalse(m.within(root, 'link/secret'))

    def test_accept_once(self):
        used = set()
        self.assertEqual(m.confirm('accept', 't', used), {'status': 'confirmed', 'execute': True})
        with self.assertRaises(ValueError):
            m.confirm('accept', 't', used)

    def test_decline_and_cancel(self):
        for action, status in (('decline', 'declined'), ('cancel', 'canceled')):
            used = set()
            with self.subTest(action=action):
                self.assertEqual(m.confirm(action, 't', used), {'status': status, 'execute': False})
                self.assertIn('t', used)

    def test_invalid_not_consumed(self):
        used = set()
        with self.assertRaises(ValueError):
            m.confirm('maybe', 't', used)
        self.assertEqual(used, set())

class BonusTests(unittest.TestCase):

    def test_form(self):
        self.assertEqual(m.validate_form({'title': ' A '}), {'title': 'A'})

    def test_bad_form(self):
        for d in ({'title': ' '}, {'title': 'a', 'extra': 1}, {'title': False}):
            with self.subTest(d=d), self.assertRaises(ValueError):
                m.validate_form(d)
