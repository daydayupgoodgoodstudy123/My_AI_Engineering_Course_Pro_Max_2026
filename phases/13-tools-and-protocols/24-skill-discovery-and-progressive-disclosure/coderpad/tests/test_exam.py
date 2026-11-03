"""Behavior tests for 24-skill-discovery-and-progressive-disclosure; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_precedence(self):
        self.assertEqual(m.catalog([{'name': 'a', 'description': 'low', 'scope': 'user'}, {'name': 'a', 'description': 'high', 'scope': 'project'}], ['project', 'user'], 100), [{'name': 'a', 'description': 'high'}])

    def test_budget_skip(self):
        self.assertEqual(m.catalog([{'name': 'a', 'description': 'too long', 'scope': 's'}, {'name': 'b', 'description': 'x', 'scope': 's'}], ['s'], 2), [{'name': 'b', 'description': 'x'}])

    def test_collision_even_outside_budget(self):
        c = {'name': 'a', 'description': 'x', 'scope': 's'}
        with self.assertRaises(ValueError):
            m.catalog([c, c], ['s'], 0)

    def test_unknown_scope(self):
        self.assertEqual(m.catalog([{'name': 'a', 'description': 'x', 'scope': 's'}], [], 100), [])

    def test_reference(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'ref.txt').write_text('abcdef')
            self.assertEqual(m.reference(d, 'ref.txt', 3), 'abc')
            with self.assertRaises(ValueError):
                m.reference(d, '../escape', 10)
            with self.assertRaises(ValueError):
                m.reference(d, str(Path(d) / 'ref.txt'), 10)

    def test_symlink(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'skill'
            root.mkdir()
            (Path(d) / 'secret').write_text('s')
            (root / 'ref').symlink_to(Path(d) / 'secret')
            with self.assertRaises(ValueError):
                m.reference(root, 'ref', 10)

class BonusTests(unittest.TestCase):

    def test_activation(self):
        self.assertEqual(m.activation({'name': 'a', 'description': 'd'}, 'body'), {'name': 'a', 'instructions': 'body'})

    def test_no_mutation(self):
        e = {'name': 'a'}
        m.activation(e, 'x')
        self.assertEqual(e, {'name': 'a'})
