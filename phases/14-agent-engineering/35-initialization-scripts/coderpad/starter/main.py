"""Original interview practice for 14-agent-engineering/35-initialization-scripts.

Local source: phases/14-agent-engineering/35-initialization-scripts/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    """probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run."""
    raise NotImplementedError('TODO 1: environment_report; see PROMPT.md')

def command_review(argv, allowlist):
    """Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing."""
    raise NotImplementedError('TODO 2: command_review; see PROMPT.md')
