"""Original interview practice for 00-setup-and-tooling/01-dev-environment.

Local source: phases/00-setup-and-tooling/01-dev-environment/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def environment_report(probes, required):
    """probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run."""
    raise NotImplementedError('TODO 1: environment_report; see PROMPT.md')

def compatible_version(version, minimum, maximum_major):
    """version and minimum are strings of exactly three nonnegative decimal components separated by dots. Reject malformed strings with ValueError. Return version tuple>=minimum tuple and version major<=maximum_major; maximum_major is an exact nonnegative integer or raises ValueError."""
    raise NotImplementedError('TODO 2: compatible_version; see PROMPT.md')
