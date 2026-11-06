"""Original interview practice for 19-capstone-projects/85-content-classifier-integration.

Local source: phases/19-capstone-projects/85-content-classifier-integration/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def moderation(signals, block_at):
    """Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called."""
    raise NotImplementedError('TODO 1: moderation; see PROMPT.md')

def prioritize_risks(risks):
    """Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria."""
    raise NotImplementedError('TODO 2: prioritize_risks; see PROMPT.md')
