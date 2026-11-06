"""Original interview practice for 11-llm-engineering/14-model-context-protocol.

Local source: phases/11-llm-engineering/14-model-context-protocol/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def rpc_request(request_id, method, params):
    """id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution."""
    raise NotImplementedError('TODO 1: rpc_request; see PROMPT.md')

def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 2: validate_config; see PROMPT.md')
