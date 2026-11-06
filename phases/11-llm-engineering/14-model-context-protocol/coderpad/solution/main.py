"""Original interview practice for 11-llm-engineering/14-model-context-protocol.

Local source: phases/11-llm-engineering/14-model-context-protocol/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def rpc_request(request_id, method, params):
    if not (type(request_id) is int or (isinstance(request_id, str) and request_id)) or not isinstance(method, str) or (not method) or (not isinstance(params, dict)):
        raise ValueError('request')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': copy.deepcopy(params)}

def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}
