"""Original interview practice for 16-multi-agent-and-swarms/03-communication-protocols.

Local source: phases/16-multi-agent-and-swarms/03-communication-protocols/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json
import copy

def rpc_request(request_id, method, params):
    if not (type(request_id) is int or (isinstance(request_id, str) and request_id)) or not isinstance(method, str) or (not method) or (not isinstance(params, dict)):
        raise ValueError('request')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': copy.deepcopy(params)}

def replay_requests(requests):
    seen = {}
    executed = []
    replayed = []
    for r in requests:
        payload = json.dumps(r['payload'], sort_keys=True, separators=(',', ':'))
        if r['id'] in seen:
            if seen[r['id']] != payload:
                raise ValueError('conflict')
            replayed.append(r['id'])
        else:
            seen[r['id']] = payload
            executed.append(r['id'])
    return {'executed': executed, 'replayed': replayed}
