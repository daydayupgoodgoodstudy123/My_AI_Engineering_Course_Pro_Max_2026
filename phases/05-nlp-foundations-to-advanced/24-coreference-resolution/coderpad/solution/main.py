"""Original interview practice for 05-nlp-foundations-to-advanced/24-coreference-resolution.

Local source: phases/05-nlp-foundations-to-advanced/24-coreference-resolution/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import copy

def bio_spans(labels):
    result = []
    active = None
    start = 0
    for i, label in enumerate(labels + ['O']):
        if label == 'O':
            kind, typ = ('O', None)
        elif isinstance(label, str) and len(label) > 2 and (label[:2] in ('B-', 'I-')):
            kind, typ = (label[0], label[2:])
        else:
            raise ValueError('BIO')
        continuation = kind == 'I' and typ == active
        if active is not None and (not continuation):
            result.append({'type': active, 'start': start, 'end': i})
            active = None
        if kind != 'O' and (not continuation):
            active = typ
            start = i
    return result

def update_slots(state, changes):
    allowed = {'cuisine', 'area', 'people'}
    if not set(state) <= allowed or not set(changes) <= allowed:
        raise ValueError('slot')
    result = copy.deepcopy(state)
    for key, value in changes.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = copy.deepcopy(value)
    return result
