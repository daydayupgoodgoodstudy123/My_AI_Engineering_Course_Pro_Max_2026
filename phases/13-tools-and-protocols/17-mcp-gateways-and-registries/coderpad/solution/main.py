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
        route = self.routes[public]
        if not roles & route['roles']:
            raise PermissionError(public)
        if self.fetch(route['peer'], route['local']) != route['pin']:
            raise ValueError('drift')
        return self.forward(route['peer'], route['local'], args)

    def visible(self, roles):
        return sorted((n for n, r in self.routes.items() if roles & r['roles']))
