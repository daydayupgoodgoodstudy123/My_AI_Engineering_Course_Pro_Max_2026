"""Original interview practice for 16-multi-agent-and-swarms/12-a2a-protocol.

Local source: phases/16-multi-agent-and-swarms/12-a2a-protocol/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def transition(state, target):
    edges = {'queued': {'running', 'canceled'}, 'running': {'waiting', 'completed', 'failed', 'canceled'}, 'waiting': {'running', 'canceled'}}
    if target not in edges.get(state, set()):
        raise ValueError('transition')
    return target

def rpc_request(request_id, method, params):
    if not (type(request_id) is int or (isinstance(request_id, str) and request_id)) or not isinstance(method, str) or (not method) or (not isinstance(params, dict)):
        raise ValueError('request')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': copy.deepcopy(params)}
