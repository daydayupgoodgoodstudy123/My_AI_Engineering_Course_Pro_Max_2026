"""Behavior tests for 19-a2a-protocol; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_lifecycle(self):
        t = m.Task()
        for mid, state in (('1', 'working'), ('2', 'input-required'), ('3', 'working')):
            self.assertEqual(t.apply(mid, state), state)
        self.assertEqual(t.apply('4', 'completed', 'report'), 'completed')
        self.assertEqual(t.artifacts, ['report'])

    def test_replay(self):
        t = m.Task()
        t.apply('1', 'working')
        t.apply('2', 'completed', 'r')
        self.assertEqual(t.apply('1', 'working'), 'completed')
        t.apply('2', 'completed', 'r')
        self.assertEqual(t.artifacts, ['r'])

    def test_conflict(self):
        t = m.Task()
        t.apply('1', 'working')
        with self.assertRaises(ValueError):
            t.apply('1', 'rejected')

    def test_invalid_does_not_consume(self):
        t = m.Task()
        with self.assertRaises(ValueError):
            t.apply('1', 'completed', 'r')
        self.assertEqual(t.apply('1', 'working'), 'working')

    def test_terminal(self):
        t = m.Task()
        t.apply('1', 'rejected')
        with self.assertRaises(ValueError):
            t.apply('2', 'working')

    def test_artifact_contract(self):
        t = m.Task()
        t.apply('1', 'working')
        with self.assertRaises(ValueError):
            t.apply('2', 'completed')
        self.assertEqual(t.status, 'working')

class BonusTests(unittest.TestCase):

    def test_parts(self):
        self.assertEqual(m.text_parts([{'type': 'text', 'text': 'a'}, {'type': 'file', 'uri': 'u'}, {'type': 'text', 'text': 'b'}]), 'a\nb')

    def test_empty(self):
        self.assertEqual(m.text_parts([]), '')
