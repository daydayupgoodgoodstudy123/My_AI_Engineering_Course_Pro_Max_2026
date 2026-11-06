"""Original interview practice for 01-math-foundations/02-vectors-matrices-operations.

Local source: phases/01-math-foundations/02-vectors-matrices-operations/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def matmul(a, b):
    if not a or not b or (not a[0]) or (not b[0]) or any((len(r) != len(a[0]) for r in a)) or any((len(r) != len(b[0]) for r in b)) or (len(a[0]) != len(b)):
        raise ValueError('shape')
    return [[sum((a[i][k] * b[k][j] for k in range(len(b)))) for j in range(len(b[0]))] for i in range(len(a))]

def transpose(rows):
    if not rows:
        return []
    if any((len(r) != len(rows[0]) for r in rows)):
        raise ValueError('ragged')
    return [list(c) for c in zip(*rows)]
