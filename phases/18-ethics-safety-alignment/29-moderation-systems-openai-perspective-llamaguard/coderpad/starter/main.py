"""Original interview practice for 18-ethics-safety-alignment/29-moderation-systems-openai-perspective-llamaguard.

Local source: phases/18-ethics-safety-alignment/29-moderation-systems-openai-perspective-llamaguard/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def moderation(signals, block_at):
    """Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called."""
    raise NotImplementedError('TODO 1: moderation; see PROMPT.md')

def calibration_error(confidences, correct, bins):
    """Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError."""
    raise NotImplementedError('TODO 2: calibration_error; see PROMPT.md')
