"""Original interview practice for 14-agent-engineering/41-workbench-for-real-repos.

Local source: phases/14-agent-engineering/41-workbench-for-real-repos/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import hashlib

def manifest(files):
    """files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk."""
    raise NotImplementedError('TODO 1: manifest; see PROMPT.md')

def git_plan(changes):
    """Each change has path and status among added,modified,deleted. Return dict status->sorted paths for all three categories. Duplicate paths or unknown status raises ValueError. This function plans only; no git command executes."""
    raise NotImplementedError('TODO 2: git_plan; see PROMPT.md')
