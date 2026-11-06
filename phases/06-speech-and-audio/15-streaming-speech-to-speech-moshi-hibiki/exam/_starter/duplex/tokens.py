"""Token ids shared by the streams of a duplex session."""

CODEBOOKS = 8  # Mimi codes per frame: codebook 0 is semantic, 1-7 are acoustic
CODEBOOK_SIZE = 1024  # every code is in 0..1023
AUDIO_START = CODEBOOK_SIZE  # stands for the model's audio before its first frame; never a real code

PAD = 0  # text stream: no new text in this frame
EPAD = 1  # text stream: a word starts in the next frame
TEXT_START = 2  # stands for the model's text before its first step
# word-piece ids start at 3

UNSET = -1  # delayed layout: no token at this position
