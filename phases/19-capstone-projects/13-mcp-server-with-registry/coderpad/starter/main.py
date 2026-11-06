"""Original interview practice for 19-capstone-projects/13-mcp-server-with-registry.

Local source: phases/19-capstone-projects/13-mcp-server-with-registry/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib
import copy

def rpc_request(request_id, method, params):
    """id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution."""
    raise NotImplementedError('TODO 1: rpc_request; see PROMPT.md')

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 2: manifest; see PROMPT.md')
