"""Original Phase 13 / Lesson 18 CoderPad practice.

Lesson source: 18-mcp-auth-production/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def token_for(cache, issuer, resource, now):
    raise NotImplementedError("TODO 1: token_for; see PROMPT.md")

class KeyCache:

    def __init__(self, ttl):
        self.ttl = ttl
        self.keys = {}
        self.expires = 0

    def get(self, kid, now, fetch):
        raise NotImplementedError("TODO 2: KeyCache.get; see PROMPT.md")

def invalidate(cache, issuer):
    raise NotImplementedError("TODO 3: invalidate; see PROMPT.md")
