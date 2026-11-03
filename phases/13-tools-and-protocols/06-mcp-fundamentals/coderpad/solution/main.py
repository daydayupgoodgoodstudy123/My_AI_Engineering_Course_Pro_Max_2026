"""Original Phase 13 / Lesson 06 CoderPad practice.

Lesson source: 06-mcp-fundamentals/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from copy import deepcopy
VERSION = '2026-07-28'

def dispatch(message):
    valid = isinstance(message, dict) and message.get('jsonrpc') == '2.0' and (type(message.get('id')) is int or (isinstance(message.get('id'), str) and bool(message['id']))) and isinstance(message.get('method'), str) and bool(message['method']) and isinstance(message.get('params'), dict)
    meta = message['params'].get('_meta') if valid else None
    valid = valid and isinstance(meta, dict) and isinstance(meta.get('protocolVersion'), str) and isinstance(meta.get('clientCapabilities'), dict)
    rid = message['id'] if valid else None

    def error(code):
        return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': code}}
    if not valid:
        return error(-32600)
    if meta['protocolVersion'] != VERSION:
        return error(-32022)
    method = message['method']
    if method == 'server/discover':
        result = {'resultType': 'complete', 'name': 'interview-server'}
    elif method == 'tools/list':
        result = {'resultType': 'complete', 'tools': []}
    else:
        return error(-32601)
    return {'jsonrpc': '2.0', 'id': rid, 'result': result}

def request(request_id, method, params=None):
    p = deepcopy(params) if params is not None else {}
    p['_meta'] = {'protocolVersion': VERSION, 'clientCapabilities': {}}
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': p}
