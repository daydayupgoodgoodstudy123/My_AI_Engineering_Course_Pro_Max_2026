"""Original interview practice for 16-multi-agent-and-swarms/03-communication-protocols.

Local source: phases/16-multi-agent-and-swarms/03-communication-protocols/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
import copy

def rpc_request(request_id, method, params):
    """id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution."""
    raise NotImplementedError('TODO 1: rpc_request; see PROMPT.md')

def replay_requests(requests):
    """Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal."""
    raise NotImplementedError('TODO 2: replay_requests; see PROMPT.md')
