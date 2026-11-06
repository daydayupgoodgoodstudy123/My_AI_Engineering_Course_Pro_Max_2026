"""Original interview practice for 19-capstone-projects/86-constitutional-rules-engine.

Local source: phases/19-capstone-projects/86-constitutional-rules-engine/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    """required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid."""
    raise NotImplementedError('TODO 1: validate_config; see PROMPT.md')

def moderation(signals, block_at):
    """Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called."""
    raise NotImplementedError('TODO 2: moderation; see PROMPT.md')
