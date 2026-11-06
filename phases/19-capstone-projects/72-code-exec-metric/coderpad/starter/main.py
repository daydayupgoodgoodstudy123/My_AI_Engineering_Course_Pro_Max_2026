"""Original interview practice for 19-capstone-projects/72-code-exec-metric.

Local source: phases/19-capstone-projects/72-code-exec-metric/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def permission_decision(capability, granted, side_effect, approved):
    """If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes."""
    raise NotImplementedError('TODO 1: permission_decision; see PROMPT.md')

def command_review(argv, allowlist):
    """Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing."""
    raise NotImplementedError('TODO 2: command_review; see PROMPT.md')
