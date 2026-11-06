"""Original interview practice for 06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki.

Local source: phases/06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def quantize_codebook(vectors, codebook):
    """Codebook must be a nonempty set of same-dimensional numeric rows. All vectors must have that dimension. Return nearest codeword index per vector by squared Euclidean distance, ties to lower index. Invalid dimensions or empty codebook raises ValueError."""
    raise NotImplementedError('TODO 1: quantize_codebook; see PROMPT.md')

def latency_report(latencies, deadline):
    """Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError."""
    raise NotImplementedError('TODO 2: latency_report; see PROMPT.md')
