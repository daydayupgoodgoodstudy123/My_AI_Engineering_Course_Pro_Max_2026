"""Behavior tests for 29-mcp-reliability-cancellation-and-flow-control; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_drop_oldest_progress(self):
        b = m.Buffer(2)
        b.push('final', 'f1')
        b.push('progress', 1)
        self.assertTrue(b.push('final', 'f2'))
        self.assertEqual(b.drain(), [{'kind': 'final', 'value': 'f1'}, {'kind': 'final', 'value': 'f2'}])

    def test_preserve_finals(self):
        b = m.Buffer(1)
        b.push('final', 'f')
        self.assertFalse(b.push('progress', 1))
        with self.assertRaises(BufferError):
            b.push('final', 'g')
        self.assertEqual(b.drain(), [{'kind': 'final', 'value': 'f'}])

    def test_drain_clears(self):
        b = m.Buffer(2)
        b.push('progress', 1)
        self.assertEqual(len(b.drain()), 1)
        self.assertEqual(b.drain(), [])

    def test_capacity(self):
        for c in (0, -1, True):
            with self.subTest(c=c), self.assertRaises(ValueError):
                m.Buffer(c)

    def test_retry(self):
        self.assertEqual([m.retry(False, None), m.retry(True, 'id'), m.retry(True, ''), m.retry(True, None)], ['safe', 'deduplicated', 'unsafe', 'unsafe'])

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            m.Buffer(1).push('unknown', 1)

class BonusTests(unittest.TestCase):

    def test_cancel_wins(self):
        r = m.Race()
        self.assertTrue(r.cancel())
        self.assertFalse(r.complete('late'))
        self.assertEqual(r.state, 'canceled')
        self.assertIsNone(r.value)

    def test_complete_wins(self):
        r = m.Race()
        self.assertTrue(r.complete(0))
        self.assertFalse(r.cancel())
        self.assertEqual(r.value, 0)
