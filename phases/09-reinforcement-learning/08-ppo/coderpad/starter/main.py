"""Original interview practice for 09-reinforcement-learning/08-ppo.

Local source: phases/09-reinforcement-learning/08-ppo/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def ppo_objective(ratios, advantages, epsilon):
    """Return mean(min(ratio*A,clip(ratio,1-epsilon,1+epsilon)*A)). Require equal nonempty lists, ratios>=0, and 0<=epsilon<1; otherwise ValueError. Keep the sign of advantages."""
    raise NotImplementedError('TODO 1: ppo_objective; see PROMPT.md')

def advantages(rewards, values, gamma):
    """values contains one more element than rewards. Return one-step TD advantage r[t]+gamma*v[t+1]-v[t]. Require gamma in [0,1] and exact length relation; otherwise ValueError. Empty rewards plus one value returns []."""
    raise NotImplementedError('TODO 2: advantages; see PROMPT.md')
