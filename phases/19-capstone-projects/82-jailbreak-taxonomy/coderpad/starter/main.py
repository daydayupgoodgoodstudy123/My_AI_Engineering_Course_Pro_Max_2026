"""Original interview practice for 19-capstone-projects/82-jailbreak-taxonomy.

Local source: phases/19-capstone-projects/82-jailbreak-taxonomy/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def prioritize_risks(risks):
    """Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria."""
    raise NotImplementedError('TODO 1: prioritize_risks; see PROMPT.md')

def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 2: validate_config; see PROMPT.md')
