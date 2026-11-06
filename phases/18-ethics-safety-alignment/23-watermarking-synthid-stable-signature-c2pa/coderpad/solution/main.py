"""Original interview practice for 18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa.

Local source: phases/18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bit_accuracy(expected, observed):
    if not expected or len(expected) != len(observed) or any((type(x) is not int or x not in (0, 1) for x in expected + observed)):
        raise ValueError('bits')
    return sum((a == b for a, b in zip(expected, observed))) / len(expected)

def unsupported_claims(claims, evidence_ids):
    if len({c['id'] for c in claims}) != len(claims):
        raise ValueError('duplicate claim')
    known = set(evidence_ids)
    return sorted((c['id'] for c in claims if not c['references'] or not set(c['references']) <= known))
