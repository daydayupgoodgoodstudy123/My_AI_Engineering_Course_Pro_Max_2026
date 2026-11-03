"""Original Phase 13 / Lesson 17 CoderPad practice.

Lesson source: 17-mcp-gateways-and-registries/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
class Gateway:

    def __init__(self, routes, fetch, forward):
        self.routes = routes
        self.fetch = fetch
        self.forward = forward

    def call(self, public, roles, args):
        raise NotImplementedError("TODO 1: Gateway.call; see PROMPT.md")

    def visible(self, roles):
        raise NotImplementedError("TODO 2: Gateway.visible; see PROMPT.md")
