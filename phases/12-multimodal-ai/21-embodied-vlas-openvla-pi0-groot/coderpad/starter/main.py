"""Original interview practice for 12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot.

Local source: phases/12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def flow_step(state, velocity, delta):
    """Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid."""
    raise NotImplementedError('TODO 1: flow_step; see PROMPT.md')

def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 2: permission_decision; see PROMPT.md')
