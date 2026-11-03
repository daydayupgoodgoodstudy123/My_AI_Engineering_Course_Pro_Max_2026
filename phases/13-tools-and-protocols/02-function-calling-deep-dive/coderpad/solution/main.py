"""Original Phase 13 / Lesson 02 CoderPad practice.

Lesson source: 02-function-calling-deep-dive/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json
from copy import deepcopy

def normalize(provider, payload):
    if provider not in ('openai', 'anthropic', 'gemini'):
        raise ValueError('provider')
    try:
        key = {'openai': 'tool_calls', 'anthropic': 'content', 'gemini': 'parts'}[provider]
        blocks = payload.get(key, [])
        if not isinstance(blocks, list):
            raise ValueError('collection')
        result = []
        for b in blocks:
            if provider == 'openai':
                call = {'id': b['id'], 'name': b['function']['name'], 'arguments': json.loads(b['function']['arguments'])}
            elif provider == 'anthropic':
                if b.get('type') != 'tool_use':
                    continue
                call = {'id': b['id'], 'name': b['name'], 'arguments': b['input']}
            else:
                if 'functionCall' not in b:
                    continue
                c = b['functionCall']
                call = {'id': c['id'], 'name': c['name'], 'arguments': c['args']}
            if any((not isinstance(call[k], str) or not call[k] for k in ('id', 'name'))) or not isinstance(call['arguments'], dict):
                raise ValueError('call')
            result.append(deepcopy(call))
        return result
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('malformed call') from exc

def choice(provider, mode, name=None):
    if provider not in ('openai', 'anthropic', 'gemini') or mode not in ('auto', 'none', 'required', 'force'):
        raise ValueError('choice')
    if mode == 'force' and (not isinstance(name, str) or not name):
        raise ValueError('name')
    if provider == 'openai':
        return {'type': 'function', 'function': {'name': name}} if mode == 'force' else mode
    if provider == 'anthropic':
        return {'type': 'tool', 'name': name} if mode == 'force' else {'type': {'required': 'any'}.get(mode, mode)}
    return {'mode': 'ANY', 'allowed_function_names': [name]} if mode == 'force' else {'mode': {'auto': 'AUTO', 'none': 'NONE', 'required': 'ANY'}[mode]}

def unique_calls(calls):
    seen = {}
    for call in calls:
        if call['id'] in seen and seen[call['id']] != call:
            raise ValueError('conflicting id')
        seen.setdefault(call['id'], call)
    return list(seen.values())
