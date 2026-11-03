"""Original Phase 13 / Lesson 14 CoderPad practice.

Lesson source: 14-mcp-apps/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import html
from copy import deepcopy

def bridge(origin, message, allowed_origin, permissions):

    def error(code):
        return {'ok': False, 'error': code}
    if origin != allowed_origin:
        return error('origin')
    if not isinstance(message, dict) or set(message) != {'id', 'method', 'params'} or (not isinstance(message['id'], str)) or (not message['id']) or (not isinstance(message['params'], dict)):
        return error('message')
    method = message['method']
    required = {'notes/read': 'read', 'notes/export': 'export'}
    if not isinstance(method, str) or method not in required:
        return error('method')
    if required[method] not in permissions:
        return error('permission')
    return {'ok': True, 'id': message['id'], 'method': method, 'params': deepcopy(message['params'])}

def timeline(titles):
    return '<ul>' + ''.join(('<li>' + html.escape(t) + '</li>' for t in titles)) + '</ul>'

def resource(uri, enabled):
    if enabled is not True or not isinstance(uri, str) or (not uri.startswith('ui://')) or (len(uri) == 5):
        raise ValueError('resource')
    return {'uri': uri, 'mimeType': 'text/html'}
