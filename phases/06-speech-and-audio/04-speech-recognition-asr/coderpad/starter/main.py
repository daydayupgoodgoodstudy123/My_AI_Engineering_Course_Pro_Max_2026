"""Original interview practice for 06-speech-and-audio/04-speech-recognition-asr.

Local source: phases/06-speech-and-audio/04-speech-recognition-asr/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def ctc_decode(tokens, blank=0):
    """Collapse adjacent repeated tokens first, then remove blank tokens. A blank separates repetitions, so [1,0,1] decodes to [1,1]. Tokens and blank are provided scalar ids; empty input returns []."""
    raise NotImplementedError('TODO 1: ctc_decode; see PROMPT.md')

def edit_distance(reference, hypothesis):
    """Return Levenshtein distance between two token lists, using unit insertion/deletion/substitution costs. Inputs are lists of scalar tokens. Empty sequences are valid; no transposition operation."""
    raise NotImplementedError('TODO 2: edit_distance; see PROMPT.md')
