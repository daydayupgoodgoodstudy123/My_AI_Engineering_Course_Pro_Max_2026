"""Original interview practice for 14-agent-engineering/06-tool-use-and-function-calling.

Local source: phases/14-agent-engineering/06-tool-use-and-function-calling/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import json

def validate_arguments(schema, arguments):
    types = {'string': str, 'integer': int, 'boolean': bool}
    return isinstance(arguments, dict) and set(arguments) == set(schema) and all((kind in types and type(arguments[k]) is types[kind] for k, kind in schema.items()))

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
