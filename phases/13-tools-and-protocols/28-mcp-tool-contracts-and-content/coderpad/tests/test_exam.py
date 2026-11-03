"""Behavior tests for 28-mcp-tool-contracts-and-content; default target is starter."""
import unittest
from _support import m

class CoreTests(unittest.TestCase):

    def test_array_scalar_null(self):
        for value, kind in (([], 'array'), (0, 'integer'), (None, 'null'), (False, 'boolean'), ('x', 'string')):
            with self.subTest(kind=kind):
                self.assertTrue(m.validate({'content': [], 'structured': value}, kind))

    def test_bool_not_integer(self):
        with self.assertRaises(ValueError):
            m.validate({'content': [], 'structured': True}, 'integer')

    def test_image(self):
        self.assertTrue(m.validate({'content': [{'type': 'image', 'mimeType': 'image/png', 'data': 'aGk='}], 'structured': {}}, 'object'))

    def test_bad_blocks(self):
        for block in ({'type': 'text', 'text': 1}, {'type': 'image', 'mimeType': 'image/png', 'data': '@@'}, {'type': 'audio'}):
            with self.subTest(block=block), self.assertRaises(ValueError):
                m.validate({'content': [block], 'structured': {}}, 'object')

    def test_tool_error(self):
        self.assertTrue(m.validate({'content': [{'type': 'text', 'text': 'not found'}], 'isError': True}, 'object'))

    def test_missing_structured(self):
        with self.assertRaises(ValueError):
            m.validate({'content': []}, 'object')

class BonusTests(unittest.TestCase):

    def test_opaque_cursor(self):
        seen = []
        table = {None: {'items': [1], 'next': ''}, '': {'items': [2], 'next': None}}
        self.assertEqual(m.pages(lambda c: seen.append(c) or table[c]), [1, 2])
        self.assertEqual(seen, [None, ''])

    def test_cycle(self):
        with self.assertRaises(ValueError):
            m.pages(lambda c: {'items': [], 'next': 'x'})
