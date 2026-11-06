"""Original interview practice for 11-llm-engineering/09-function-calling.

Local source: phases/11-llm-engineering/09-function-calling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def validate_arguments(schema, arguments):
    """schema maps required field name -> one of string,integer,boolean. arguments must be a dict with exactly these keys, with str/exact int/exact bool respectively. Return True when valid, False otherwise. Unknown schema type is invalid. No coercion."""
    raise NotImplementedError('TODO 1: validate_arguments; see PROMPT.md')

def rpc_request(request_id, method, params):
    """id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution."""
    raise NotImplementedError('TODO 2: rpc_request; see PROMPT.md')
