"""Original interview practice for 14-agent-engineering/14-autogen-actor-model.

Local source: phases/14-agent-engineering/14-autogen-actor-model/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def schedule_jobs(jobs, capacity):
    if type(capacity) is not int or capacity < 0 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('queue')
    return [j['id'] for j in sorted((j for j in jobs if j['status'] == 'queued'), key=lambda j: (-j['priority'], j['created'], j['id']))[:capacity]]

def rpc_request(request_id, method, params):
    if not (type(request_id) is int or (isinstance(request_id, str) and request_id)) or not isinstance(method, str) or (not method) or (not isinstance(params, dict)):
        raise ValueError('request')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': copy.deepcopy(params)}
