"""Original interview practice for 19-capstone-projects/01-terminal-native-coding-agent.

Local source: phases/19-capstone-projects/01-terminal-native-coding-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def command_review(argv, allowlist):
    """Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing."""
    raise NotImplementedError('TODO 1: command_review; see PROMPT.md')

def contained_path(root, relative):
    """Use POSIX lexical paths only: root must be absolute, relative must not be absolute. Normalize '.' and '..'; reject any attempt to pop above root with ValueError. Return normalized absolute path string. No filesystem or symlink checks are made. root is already normalized without trailing slash except '/'."""
    raise NotImplementedError('TODO 2: contained_path; see PROMPT.md')
