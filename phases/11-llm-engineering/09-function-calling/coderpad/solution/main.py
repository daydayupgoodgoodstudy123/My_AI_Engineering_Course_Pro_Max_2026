"""Original interview practice for 11-llm-engineering/09-function-calling.

Local source: phases/11-llm-engineering/09-function-calling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def validate_arguments(schema, arguments):
    types = {'string': str, 'integer': int, 'boolean': bool}
    return isinstance(arguments, dict) and set(arguments) == set(schema) and all((kind in types and type(arguments[k]) is types[kind] for k, kind in schema.items()))

def rpc_request(request_id, method, params):
    if not (type(request_id) is int or (isinstance(request_id, str) and request_id)) or not isinstance(method, str) or (not method) or (not isinstance(params, dict)):
        raise ValueError('request')
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': copy.deepcopy(params)}
