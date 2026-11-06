"""Original interview practice for 05-nlp-foundations-to-advanced/06-named-entity-recognition.

Local source: phases/05-nlp-foundations-to-advanced/06-named-entity-recognition/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

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

def tokenize(text):
    return re.findall('[a-z0-9]+', text.casefold())
