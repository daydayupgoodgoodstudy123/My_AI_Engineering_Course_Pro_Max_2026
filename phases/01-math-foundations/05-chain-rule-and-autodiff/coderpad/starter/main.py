"""Original interview practice for 01-math-foundations/05-chain-rule-and-autodiff.

Local source: phases/01-math-foundations/05-chain-rule-and-autodiff/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def quadratic_gradient(weights, target):
    """For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError."""
    raise NotImplementedError('TODO 1: quadratic_gradient; see PROMPT.md')

def gradient_step(weights, gradients, rate):
    """Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid."""
    raise NotImplementedError('TODO 2: gradient_step; see PROMPT.md')
