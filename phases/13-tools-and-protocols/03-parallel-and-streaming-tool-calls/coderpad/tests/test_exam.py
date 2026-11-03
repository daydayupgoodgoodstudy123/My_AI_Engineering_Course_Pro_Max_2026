"""Behavior tests for 03-parallel-and-streaming-tool-calls; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_interleaved(self):
        events = [{'index': 1, 'id': 'b', 'name': 'weather', 'arguments': '{"city":'}, {'index': 0, 'id': 'a', 'name': 'add', 'arguments': '{"x":'}, {'index': 1, 'arguments': '"NY"}'}, {'index': 0, 'arguments': '2}'}]
        self.assertEqual(m.assemble(events), [{'id': 'a', 'name': 'add', 'arguments': {'x': 2}}, {'id': 'b', 'name': 'weather', 'arguments': {'city': 'NY'}}])

    def test_repeat_identity(self):
        self.assertEqual(m.assemble([{'index': 2, 'id': 'a', 'name': 'f', 'arguments': '{'}, {'index': 2, 'id': 'a', 'name': 'f', 'arguments': '}'}])[0]['arguments'], {})

    def test_conflicting_identity(self):
        for key in ('id', 'name'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.assemble([{'index': 0, 'id': 'a', 'name': 'f', 'arguments': '{}'}, {'index': 0, key: 'other'}])

    def test_incomplete_and_nonobject(self):
        for raw in ('{', '[]', 'null'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                m.assemble([{'index': 0, 'id': 'a', 'name': 'f', 'arguments': raw}])

    def test_missing_identity(self):
        with self.assertRaises(ValueError):
            m.assemble([{'index': 0, 'arguments': '{}'}])

    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):
            m.assemble([{'index': i, 'id': 'a', 'name': 'f', 'arguments': '{}'} for i in (0, 1)])

    def test_bad_index(self):
        for index in (-1, True, 1.0):
            with self.subTest(index=index), self.assertRaises(ValueError):
                m.assemble([{'index': index}])

    def test_bad_fragment(self):
        with self.assertRaises(ValueError):
            m.assemble([{'index': 0, 'arguments': {}}])

    def test_empty(self):
        self.assertEqual(m.assemble([]), [])

class BonusTests(unittest.TestCase):

    def test_order_and_concurrency(self):
        import threading
        barrier = threading.Barrier(3, timeout=3)

        def execute(value):
            barrier.wait()
            return value * 2
        self.assertEqual(m.parallel([3, 1, 2], execute, 3), [6, 2, 4])

    def test_exception_and_empty(self):

        def fail(_):
            raise RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            m.parallel([1], fail)
        self.assertEqual(m.parallel([], fail), [])

    def test_workers(self):
        for workers in (0, True):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                m.parallel([], lambda x: x, workers)
