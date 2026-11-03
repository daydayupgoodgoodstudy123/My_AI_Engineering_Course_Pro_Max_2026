"""Behavior tests for 01-the-tool-interface; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def setUp(self):
        self.seen = []
        self.registry = {'add': {'parameters': ['a', 'b'], 'executor': lambda a: self.seen.append(a.copy()) or a['a'] + a['b']}}

    def test_valid_call(self):
        self.assertEqual(m.execute(self.registry, 'add', {'a': 2, 'b': 3}), {'ok': True, 'value': 5})
        self.assertEqual(len(self.seen), 1)

    def test_unknown(self):
        self.assertEqual(m.execute(self.registry, 'delete', {}), {'ok': False, 'error': 'unknown_tool'})

    def test_invalid_arguments_never_execute(self):
        for args in ({'a': True, 'b': 1}, {'a': 1.0, 'b': 2}, {'a': '1', 'b': 2}, {'a': 1}, {'a': 1, 'b': 2, 'c': 3}, []):
            with self.subTest(args=args):
                self.assertEqual(m.execute(self.registry, 'add', args), {'ok': False, 'error': 'invalid_arguments'})
        self.assertEqual(self.seen, [])

    def test_executor_error_isolated(self):

        def fail(a):
            raise RuntimeError('offline')
        self.registry['bad'] = {'parameters': [], 'executor': fail}
        self.assertEqual(m.execute(self.registry, 'bad', {}), {'ok': False, 'error': 'execution_error'})
        self.assertTrue(m.execute(self.registry, 'add', {'a': 0, 'b': 0})['ok'])

    def test_final(self):
        self.assertEqual(m.run_loop(self.registry, [{'final': 'done'}]), {'results': [], 'stop': 'final', 'answer': 'done'})

    def test_limit_counts_errors(self):
        r = m.run_loop(self.registry, [{'tool': 'missing', 'arguments': {}}, {'final': 'done'}], 1)
        self.assertEqual(r, {'results': [{'ok': False, 'error': 'unknown_tool'}], 'stop': 'limit', 'answer': None})

    def test_empty(self):
        self.assertEqual(m.run_loop(self.registry, []), {'results': [], 'stop': 'exhausted', 'answer': None})

    def test_exhausted_after_call(self):
        self.assertEqual(m.run_loop(self.registry, [{'tool': 'add', 'arguments': {'a': -1, 'b': 2}}])['results'], [{'ok': True, 'value': 1}])

    def test_invalid_limit(self):
        for n in (0, -1, True, 1.5):
            with self.subTest(n=n), self.assertRaises(ValueError):
                m.run_loop(self.registry, [], n)

class BonusTests(unittest.TestCase):

    def test_sorted_description(self):
        self.assertEqual(m.describe({'z': {}, 'a': {}}), ['a', 'z'])

    def test_no_execution(self):
        self.assertEqual(m.describe({'x': {'executor': lambda _: self.fail('executed')}}), ['x'])
