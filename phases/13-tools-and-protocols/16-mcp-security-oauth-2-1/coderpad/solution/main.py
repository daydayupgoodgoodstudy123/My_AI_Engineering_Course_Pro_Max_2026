"""Original Phase 13 / Lesson 16 CoderPad practice.

Lesson source: 16-mcp-security-oauth-2-1/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import hashlib, base64

def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode().rstrip('=')

def authorize(claims, issuer, resource, required, now):

    def fail(code):
        return {'ok': False, 'error': code}
    if claims.get('iss') != issuer:
        return fail('issuer')
    aud = claims.get('aud')
    if not (isinstance(aud, str) and aud == resource or (isinstance(aud, list) and resource in aud)):
        return fail('audience')
    if type(claims.get('exp')) is not int or now >= claims['exp']:
        return fail('expired')
    if not isinstance(claims.get('scope'), str) or not required <= set(claims['scope'].split()):
        return fail('scope')
    return {'ok': True}

def step_up(current, required):
    return sorted(required - current)
