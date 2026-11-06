"""Original interview practice for 19-capstone-projects/16-github-issue-to-pr-agent.

Local source: phases/19-capstone-projects/16-github-issue-to-pr-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def git_plan(changes):
    """Each change has path and status among added,modified,deleted. Return dict status->sorted paths for all three categories. Duplicate paths or unknown status raises ValueError. This function plans only; no git command executes."""
    raise NotImplementedError('TODO 1: git_plan; see PROMPT.md')

def evidence_gate(evidence, required):
    """For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed."""
    raise NotImplementedError('TODO 2: evidence_gate; see PROMPT.md')
