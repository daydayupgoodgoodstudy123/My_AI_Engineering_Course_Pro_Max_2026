"""Behavior tests for 27-skill-evals-packaging-and-portability; default target is starter."""
import unittest
from _support import m

GOOD = {'structure': True, 'behavior': True, 'safety': True, 'portability': True, 'metrics': {'precision': 0.8, 'recall': 0.9}}

class CoreTests(unittest.TestCase):

    def test_metrics(self):
        self.assertEqual(m.metrics([True, False, True, False], [True, True, False, False]), {'tp': 1, 'fp': 1, 'fn': 1, 'precision': 0.5, 'recall': 0.5})

    def test_zero(self):
        self.assertEqual(m.metrics([], []), {'tp': 0, 'fp': 0, 'fn': 0, 'precision': 0.0, 'recall': 0.0})

    def test_invalid(self):
        for a, b in (([True], []), ([1], [True])):
            with self.subTest(a=a), self.assertRaises(ValueError):
                m.metrics(a, b)

    def test_gate_boundary(self):
        self.assertEqual(m.gate(GOOD), {'ready': True, 'reasons': []})

    def test_safety_veto(self):
        self.assertEqual(m.gate(dict(GOOD, safety=False)), {'ready': False, 'reasons': ['safety']})

    def test_bad_metrics(self):
        self.assertEqual(m.gate(dict(GOOD, metrics={'precision': True, 'recall': 0.9}))['reasons'], ['metrics'])

    def test_all_reasons(self):
        self.assertEqual(m.gate(dict(GOOD, structure=False, metrics={'precision': 0.7, 'recall': 0.6}))['reasons'], ['precision', 'recall', 'structure'])

class BonusTests(unittest.TestCase):

    def test_negative_improvement(self):
        self.assertAlmostEqual(m.improvement(0.9, 0.8), -0.1)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            m.improvement(True, 0.8)
