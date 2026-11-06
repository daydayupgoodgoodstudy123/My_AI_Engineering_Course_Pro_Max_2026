"""Original interview practice for 14-agent-engineering/39-reviewer-agent.

Local source: phases/14-agent-engineering/39-reviewer-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def unsupported_claims(claims, evidence_ids):
    """Claims have unique id(str) and references(list of evidence ids). Return sorted claim ids lacking references or containing any unknown reference. Duplicate claim ids raises ValueError. Having a reference verifies linkage only, not factual truth."""
    raise NotImplementedError('TODO 1: unsupported_claims; see PROMPT.md')

def git_plan(changes):
    """Each change has path and status among added,modified,deleted. Return dict status->sorted paths for all three categories. Duplicate paths or unknown status raises ValueError. This function plans only; no git command executes."""
    raise NotImplementedError('TODO 2: git_plan; see PROMPT.md')
