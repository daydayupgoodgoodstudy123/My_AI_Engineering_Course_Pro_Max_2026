"""Original interview practice for 16-multi-agent-and-swarms/12-a2a-protocol.

Local source: phases/16-multi-agent-and-swarms/12-a2a-protocol/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def transition(state, target):
    """Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves."""
    raise NotImplementedError('TODO 1: transition; see PROMPT.md')

def rpc_request(request_id, method, params):
    """id exact int or nonempty string; method nonempty string; params dict. Return {'jsonrpc':'2.0','id','method','params':deepcopy}. Reject bool id, invalid method/params with ValueError. No connection or request execution."""
    raise NotImplementedError('TODO 2: rpc_request; see PROMPT.md')
