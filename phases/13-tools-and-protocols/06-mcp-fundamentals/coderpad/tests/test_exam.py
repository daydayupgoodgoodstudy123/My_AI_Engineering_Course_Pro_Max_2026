"""Behavior tests for 06-mcp-fundamentals; default target is starter."""
import unittest
from _support import m

def req(method='server/discover', rid=1):
    return {'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': {'_meta': {'protocolVersion': m.VERSION, 'clientCapabilities': {}}}}

class CoreTests(unittest.TestCase):

    def test_discover(self):
        self.assertEqual(m.dispatch(req())['result'], {'resultType': 'complete', 'name': 'interview-server'})

    def test_list_without_handshake(self):
        self.assertEqual(m.dispatch(req('tools/list', 'a')), {'jsonrpc': '2.0', 'id': 'a', 'result': {'resultType': 'complete', 'tools': []}})

    def test_missing_metadata(self):
        r = req()
        r['params'] = {}
        self.assertEqual(m.dispatch(r), {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600}})

    def test_invalid_envelopes(self):
        for value in (None, [], {}, dict(req(), id=True), dict(req(), params=[])):
            with self.subTest(value=value):
                self.assertEqual(m.dispatch(value)['error']['code'], -32600)

    def test_version_before_method(self):
        r = req('missing', 0)
        r['params']['_meta']['protocolVersion'] = 'old'
        self.assertEqual(m.dispatch(r), {'jsonrpc': '2.0', 'id': 0, 'error': {'code': -32022}})

    def test_unknown(self):
        self.assertEqual(m.dispatch(req('initialize'))['error']['code'], -32601)

class BonusTests(unittest.TestCase):

    def test_builder(self):
        self.assertEqual(m.request(0, 'tools/list'), req('tools/list', 0))

    def test_copy(self):
        p = {'nested': []}
        r = m.request(1, 'tools/list', p)
        r['params']['nested'].append(1)
        self.assertEqual(p, {'nested': []})
