"""Original interview practice for 00-setup-and-tooling/08-editor-setup.

Local source: phases/00-setup-and-tooling/08-editor-setup/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def environment_report(probes, required):
    """probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run."""
    raise NotImplementedError('TODO 1: environment_report; see PROMPT.md')

def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 2: validate_config; see PROMPT.md')
