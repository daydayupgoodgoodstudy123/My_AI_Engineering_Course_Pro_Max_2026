"""Original interview practice for 18-ethics-safety-alignment/12-red-teaming-pair-automated-attacks.

Local source: phases/18-ethics-safety-alignment/12-red-teaming-pair-automated-attacks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def classification(expected, predicted):
    """Require equal-length exact-bool lists. Return tp,fp,fn,tn,precision,recall,f1. A ratio with zero denominator is 0.0. Empty lists are valid; invalid labels raise ValueError."""
    raise NotImplementedError('TODO 1: classification; see PROMPT.md')

def prioritize_risks(risks):
    """Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria."""
    raise NotImplementedError('TODO 2: prioritize_risks; see PROMPT.md')
