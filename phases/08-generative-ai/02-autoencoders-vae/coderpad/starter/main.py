"""Original interview practice for 08-generative-ai/02-autoencoders-vae.

Local source: phases/08-generative-ai/02-autoencoders-vae/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def mse(predicted, expected):
    """Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError."""
    raise NotImplementedError('TODO 1: mse; see PROMPT.md')

def inverse_cdf(probabilities, uniforms):
    """Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called."""
    raise NotImplementedError('TODO 2: inverse_cdf; see PROMPT.md')
