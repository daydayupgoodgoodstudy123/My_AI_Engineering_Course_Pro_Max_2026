"""Behavior tests for 09-mcp-transports; default target is starter."""
import unittest
from _support import m

BODY = {'method': 'tools/call', 'params': {'name': 'read', '_meta': {'protocolVersion': 'v1'}}}
HEADERS = [('MCP-Version', 'v1'), ('mcp-method', 'tools/call'), ('Mcp-Name', 'read')]

class CoreTests(unittest.TestCase):

    def test_valid(self):
        self.assertEqual(m.validate(HEADERS, BODY, []), 'ok')

    def test_origin(self):
        self.assertEqual(m.validate(HEADERS + [('origin', 'https://bad')], BODY, ['https://good']), 'forbidden_origin')

    def test_duplicate_case_insensitive(self):
        self.assertEqual(m.validate(HEADERS + [('MCP-METHOD', 'tools/call')], BODY, []), 'duplicate_header')

    def test_mismatch(self):
        for headers in (HEADERS[:-1], HEADERS[:-1] + [('mcp-name', 'delete')], HEADERS[1:]):
            with self.subTest(headers=headers):
                self.assertEqual(m.validate(headers, BODY, []), 'routing_mismatch')

    def test_noncall_forbids_name(self):
        b = {'method': 'tools/list', 'params': {'_meta': {'protocolVersion': 'v1'}}}
        self.assertEqual(m.validate([('mcp-version', 'v1'), ('mcp-method', 'tools/list')], b, []), 'ok')
        self.assertEqual(m.validate([('mcp-version', 'v1'), ('mcp-method', 'tools/list'), ('mcp-name', 'read')], b, []), 'routing_mismatch')

    def test_duplicate_origins(self):
        self.assertEqual(m.validate(HEADERS + [('Origin', 'x'), ('origin', 'x')], BODY, ['x']), 'duplicate_header')

class BonusTests(unittest.TestCase):

    def test_sse(self):
        self.assertEqual(m.parse_sse(': ping\n\ndata: {"x":\ndata: 1}\n\ndata: [2]\n\n'), [{'x': 1}, [2]])

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            m.parse_sse('data: {\n\n')
