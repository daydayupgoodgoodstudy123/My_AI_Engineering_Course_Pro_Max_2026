"""Original Phase 13 / Lesson 01 CoderPad practice.

Lesson source: 01-the-tool-interface/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def execute(registry, name, arguments):
    if name not in registry:
        return {'ok': False, 'error': 'unknown_tool'}
    tool = registry[name]
    if not isinstance(arguments, dict) or set(arguments) != set(tool['parameters']) or any((type(v) is not int for v in arguments.values())):
        return {'ok': False, 'error': 'invalid_arguments'}
    try:
        return {'ok': True, 'value': tool['executor'](arguments)}
    except Exception:
        return {'ok': False, 'error': 'execution_error'}

def run_loop(registry, decisions, max_calls=3):
    if type(max_calls) is not int or max_calls <= 0:
        raise ValueError('max_calls')
    results = []
    for decision in decisions:
        if len(results) >= max_calls:
            return {'results': results, 'stop': 'limit', 'answer': None}
        if 'final' in decision:
            return {'results': results, 'stop': 'final', 'answer': decision['final']}
        results.append(execute(registry, decision['tool'], decision['arguments']))
    return {'results': results, 'stop': 'exhausted', 'answer': None}

def describe(registry):
    return sorted(registry)
