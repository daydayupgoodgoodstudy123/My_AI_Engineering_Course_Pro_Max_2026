"""Original Phase 13 / Lesson 11 CoderPad practice.

Lesson source: 11-mcp-sampling/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import base64
import hashlib
import hmac
import json

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def seal(state, secret):
    raw = canonical(state)
    return base64.urlsafe_b64encode(raw).decode() + '.' + hmac.new(secret, raw, hashlib.sha256).hexdigest()

def verify(token, secret, principal, method, arguments, now):
    try:
        encoded, signature = token.split('.')
        raw = base64.b64decode(encoded, altchars=b'-_', validate=True)
        if not hmac.compare_digest(signature, hmac.new(secret, raw, hashlib.sha256).hexdigest()):
            raise ValueError('signature')
        state = json.loads(raw)
        if not isinstance(state, dict) or canonical([state.get('principal'), state.get('method'), state.get('arguments')]) != canonical([principal, method, arguments]):
            raise ValueError('binding')
        if type(state.get('expires')) is not int or now >= state['expires']:
            raise ValueError('expiry')
        return state
    except (TypeError, KeyError, UnicodeError, AttributeError) as exc:
        raise ValueError('token') from exc

def next_round(current, maximum):
    if type(current) is not int or type(maximum) is not int or maximum <= 0 or (not 0 <= current < maximum):
        raise ValueError('round')
    return current + 1
