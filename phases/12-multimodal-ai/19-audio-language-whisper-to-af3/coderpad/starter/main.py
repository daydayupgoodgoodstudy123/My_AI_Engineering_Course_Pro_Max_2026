"""Original interview practice for 12-multimodal-ai/19-audio-language-whisper-to-af3.

Local source: phases/12-multimodal-ai/19-audio-language-whisper-to-af3/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def audio_frames(samples, width, hop):
    """width and hop are exact positive ints. Return complete windows only, starting at 0,hop,2*hop...; drop incomplete tail. Short or empty signals yield []. Invalid size raises ValueError."""
    raise NotImplementedError('TODO 1: audio_frames; see PROMPT.md')

def ctc_decode(tokens, blank=0):
    """Collapse adjacent repeated tokens first, then remove blank tokens. A blank separates repetitions, so [1,0,1] decodes to [1,1]. Tokens and blank are provided scalar ids; empty input returns []."""
    raise NotImplementedError('TODO 2: ctc_decode; see PROMPT.md')
