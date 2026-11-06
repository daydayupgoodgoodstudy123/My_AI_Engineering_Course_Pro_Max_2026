"""Original interview practice for 12-multimodal-ai/22-document-diagram-understanding.

Local source: phases/12-multimodal-ai/22-document-diagram-understanding/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


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

def patchify(image, patch_size):
    if type(patch_size) is not int or patch_size <= 0 or (not image) or (not image[0]) or any((len(r) != len(image[0]) for r in image)) or len(image) % patch_size or len(image[0]) % patch_size:
        raise ValueError('patch shape')
    p = patch_size
    return [[image[r + i][c + j] for i in range(p) for j in range(p)] for r in range(0, len(image), p) for c in range(0, len(image[0]), p)]
