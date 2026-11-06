"""Original interview practice for 19-capstone-projects/06-devops-troubleshooting-agent.

Local source: phases/19-capstone-projects/06-devops-troubleshooting-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    """probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run."""
    raise NotImplementedError('TODO 1: environment_report; see PROMPT.md')

def topological_order(dependencies):
    """dependencies maps node string to prerequisite-name list. Include names appearing only as prerequisites. Return lexicographically smallest available node at each step. Cycles raise ValueError. Duplicate dependencies count once; empty graph returns []."""
    raise NotImplementedError('TODO 2: topological_order; see PROMPT.md')
