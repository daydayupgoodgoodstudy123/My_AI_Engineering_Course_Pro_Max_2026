"""Original interview practice for 12-multimodal-ai/19-audio-language-whisper-to-af3.

Local source: phases/12-multimodal-ai/19-audio-language-whisper-to-af3/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def audio_frames(samples, width, hop):
    if any((type(x) is not int or x <= 0 for x in (width, hop))):
        raise ValueError('window')
    return [samples[i:i + width] for i in range(0, len(samples) - width + 1, hop)]

def ctc_decode(tokens, blank=0):
    result = []
    previous = object()
    for token in tokens:
        if token != previous and token != blank:
            result.append(token)
        previous = token
    return result
