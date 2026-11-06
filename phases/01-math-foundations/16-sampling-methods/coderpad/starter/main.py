"""Original interview practice for 01-math-foundations/16-sampling-methods.

Local source: phases/01-math-foundations/16-sampling-methods/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def inverse_cdf(probabilities, uniforms):
    """Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called."""
    raise NotImplementedError('TODO 1: inverse_cdf; see PROMPT.md')

def markov_step(distribution, transition):
    """Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition."""
    raise NotImplementedError('TODO 2: markov_step; see PROMPT.md')
