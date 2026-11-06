"""Original interview practice for 12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot.

Local source: phases/12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def flow_step(state, velocity, delta):
    if len(state) != len(velocity) or not 0 <= delta <= 1:
        raise ValueError('contract')
    return [x + delta * v for x, v in zip(state, velocity)]

def permission_decision(capability, granted, side_effect, approved):
    if type(side_effect) is not bool or type(approved) is not bool:
        raise ValueError('flags')
    if capability not in granted:
        return 'deny'
    return 'ask' if side_effect and (not approved) else 'allow'
