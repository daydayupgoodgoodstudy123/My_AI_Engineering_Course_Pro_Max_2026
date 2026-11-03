"""Behavior tests for 05-tool-schema-design; default target is starter."""
import unittest
from _support import m

def tool(name='get_note'):
    return {'name': name, 'description': 'Use when reading. Do not use for edits.', 'input_schema': {'type': 'object', 'properties': {'id': {'type': 'integer'}}, 'required': ['id'], 'additionalProperties': False}}

class CoreTests(unittest.TestCase):

    def test_valid(self):
        self.assertEqual(m.lint(tool()), [])

    def test_missing(self):
        self.assertEqual(m.lint({}), ['description', 'name', 'schema'])

    def test_names(self):
        for name in ('Bad', 'a-b', '1a', 'x' * 41, None):
            with self.subTest(name=name):
                self.assertIn('name', m.lint(tool(name)))

    def test_schema(self):
        for patch in ({'required': ['missing']}, {'required': ['id', 'id']}, {'additionalProperties': True}, {'properties': []}, {'required': [{}]}):
            t = tool()
            t['input_schema'].update(patch)
            with self.subTest(patch=patch):
                self.assertIn('schema', m.lint(t))

    def test_description(self):
        t = tool()
        t['description'] = 'Use when needed'
        self.assertEqual(m.lint(t), ['description'])

    def test_registry(self):
        self.assertEqual(m.lint_registry([tool('z'), {}, tool('z'), tool('a'), tool('a')]), {'findings': [{'index': 1, 'codes': ['description', 'name', 'schema']}], 'duplicates': ['a', 'z']})

class BonusTests(unittest.TestCase):

    def test_clean(self):
        self.assertEqual(m.clean_names([tool('b'), tool('a'), tool('b'), {}]), ['a'])

    def test_empty(self):
        self.assertEqual(m.clean_names([]), [])
