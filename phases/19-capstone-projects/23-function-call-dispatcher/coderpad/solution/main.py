"""Original interview practice for 19-capstone-projects/23-function-call-dispatcher.

Local source: phases/19-capstone-projects/23-function-call-dispatcher/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def route_task(routes, query_tokens, role):
    if len({r['name'] for r in routes}) != len(routes):
        raise ValueError('duplicate route')
    scores = [(len(set(r['keywords']) & set(query_tokens)), r['name']) for r in routes if role in r['roles']]
    best = max((s for s, n in scores), default=0)
    names = [n for s, n in scores if s == best]
    return names[0] if best > 0 and len(names) == 1 else None

def validate_arguments(schema, arguments):
    types = {'string': str, 'integer': int, 'boolean': bool}
    return isinstance(arguments, dict) and set(arguments) == set(schema) and all((kind in types and type(arguments[k]) is types[kind] for k, kind in schema.items()))
