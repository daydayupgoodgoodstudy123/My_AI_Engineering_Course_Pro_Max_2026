"""Original interview practice for 18-ethics-safety-alignment/10-ai-control-subversion.

Local source: phases/18-ethics-safety-alignment/10-ai-control-subversion/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 1: permission_decision; see PROMPT.md')

def prioritize_risks(risks):
    """Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria."""
    raise NotImplementedError('TODO 2: prioritize_risks; see PROMPT.md')
