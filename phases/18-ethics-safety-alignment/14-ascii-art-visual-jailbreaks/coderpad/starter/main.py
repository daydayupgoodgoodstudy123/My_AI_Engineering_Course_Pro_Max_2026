"""Original interview practice for 18-ethics-safety-alignment/14-ascii-art-visual-jailbreaks.

Local source: phases/18-ethics-safety-alignment/14-ascii-art-visual-jailbreaks/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import re

def tokenize(text):
    """Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching."""
    raise NotImplementedError('TODO 1: tokenize; see PROMPT.md')

def moderation(signals, block_at):
    """Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called."""
    raise NotImplementedError('TODO 2: moderation; see PROMPT.md')
