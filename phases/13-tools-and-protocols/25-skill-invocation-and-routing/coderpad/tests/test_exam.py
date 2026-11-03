"""Behavior tests for 25-skill-invocation-and-routing; default target is starter."""
import unittest
from _support import m

SKILLS = [{'name': 'review', 'human': True, 'model': True, 'keywords': {'review', 'notes'}}, {'name': 'export', 'human': True, 'model': False, 'keywords': {'export', 'notes'}}]

class CoreTests(unittest.TestCase):

    def test_explicit(self):
        self.assertEqual(m.route(SKILLS, 'nothing', 'human', 'export'), {'name': 'export', 'reason': 'explicit'})

    def test_explicit_ineligible_no_fallback(self):
        self.assertEqual(m.route(SKILLS, 'review', 'model', 'export'), {'name': None, 'reason': 'ineligible'})

    def test_implicit(self):
        self.assertEqual(m.route(SKILLS, 'Please REVIEW notes!', 'human'), {'name': 'review', 'reason': 'matched'})

    def test_tie(self):
        self.assertEqual(m.route(list(reversed(SKILLS)), 'notes', 'human'), {'name': None, 'reason': 'ambiguous'})

    def test_near_miss(self):
        self.assertEqual(m.route(SKILLS, 'reviewer notebook', 'human'), {'name': None, 'reason': 'no_match'})

    def test_actor_policy(self):
        self.assertEqual(m.route(SKILLS, 'notes', 'model')['name'], 'review')

    def test_invalid_actor(self):
        with self.assertRaises(ValueError):
            m.route(SKILLS, 'review', 'plugin')

class BonusTests(unittest.TestCase):

    def test_matrix(self):
        self.assertEqual(m.matrix(SKILLS), {'human': ['export', 'review'], 'model': ['review']})

    def test_empty(self):
        self.assertEqual(m.matrix([]), {'human': [], 'model': []})
