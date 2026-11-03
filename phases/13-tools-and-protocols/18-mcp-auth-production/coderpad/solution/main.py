"""Original Phase 13 / Lesson 18 CoderPad practice.

Lesson source: 18-mcp-auth-production/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def token_for(cache, issuer, resource, now):
    record = cache.get((issuer, resource))
    return record.copy() if record is not None and type(record.get('exp')) is int and (now < record['exp']) else None

class KeyCache:

    def __init__(self, ttl):
        self.ttl = ttl
        self.keys = {}
        self.expires = 0

    def get(self, kid, now, fetch):
        if now >= self.expires or kid not in self.keys:
            keys = fetch()
            self.keys = keys.copy()
            self.expires = now + self.ttl
        return self.keys[kid]

def invalidate(cache, issuer):
    keys = [k for k in cache if k[0] == issuer]
    for k in keys:
        del cache[k]
    return len(keys)
