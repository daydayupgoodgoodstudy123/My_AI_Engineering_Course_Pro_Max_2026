"""Original Phase 13 / Lesson 08 CoderPad practice.

Lesson source: 08-building-an-mcp-client/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
from copy import deepcopy

class Client:

    def __init__(self, peers):
        self.peers = peers
        self.catalog = {}

    def discover(self):
        catalog = {}
        for peer_name, peer in self.peers.items():
            if not peer_name or '::' in peer_name:
                raise ValueError('peer name')
            for d in peer.list_tools():
                name = d.get('name')
                if not isinstance(name, str) or not name or '::' in name:
                    raise ValueError('tool name')
                public = peer_name + '::' + name
                if public in catalog:
                    raise ValueError('duplicate')
                catalog[public] = (peer_name, name, deepcopy(d))
        self.catalog = catalog
        return sorted(catalog)

    def call(self, public_name, args):
        peer, name, _ = self.catalog[public_name]
        return self.peers[peer].call(name, args)

    def descriptor(self, public_name):
        d = deepcopy(self.catalog[public_name][2])
        d['name'] = public_name
        return d
