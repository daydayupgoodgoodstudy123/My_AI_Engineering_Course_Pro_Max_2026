"""Original interview practice for 18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa.

Local source: phases/18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bit_accuracy(expected, observed):
    """Require equal-length nonempty lists of exact integer bits 0 or 1 (bool invalid). Return fraction matching. Invalid lists raise ValueError. This bit check does not establish provenance authenticity."""
    raise NotImplementedError('TODO 1: bit_accuracy; see PROMPT.md')

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 2: unsupported_claims; see PROMPT.md')
