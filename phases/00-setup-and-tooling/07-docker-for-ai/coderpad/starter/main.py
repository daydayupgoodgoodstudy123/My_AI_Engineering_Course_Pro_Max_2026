"""Original interview practice for 00-setup-and-tooling/07-docker-for-ai.

Local source: phases/00-setup-and-tooling/07-docker-for-ai/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 1: manifest; see PROMPT.md')

def command_review(argv, allowlist):
    """Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing."""
    raise NotImplementedError('TODO 2: command_review; see PROMPT.md')
