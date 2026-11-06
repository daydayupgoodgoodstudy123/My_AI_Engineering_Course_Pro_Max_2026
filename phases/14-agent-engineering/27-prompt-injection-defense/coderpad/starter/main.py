"""Original interview practice for 14-agent-engineering/27-prompt-injection-defense.

Local source: phases/14-agent-engineering/27-prompt-injection-defense/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 1: permission_decision; see PROMPT.md')

def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 2: unsupported_claims; see PROMPT.md')
