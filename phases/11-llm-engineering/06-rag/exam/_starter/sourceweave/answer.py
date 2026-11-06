"""Source Step6 extractive answer and Exercise3 provenance, independent of fit."""
from .evidence import STOPWORDS, FALLBACK, word_tokens, citation_for
from .source_spans import evidence_sentences

def grounded_answer(question,bundle):
    """Choose the first positive maximum distinct-keyword evidence sentence.

    Use question directly, lower/split source tokens minus given stopwords.
    Only actual retrieved hits, in order, are eligible. A sentence is stripped
    by the given iterator and must contain at least10 Python characters.
    Compare distinct word-set overlap; ties keep first encountered support.
    Return {text,support,citations}; fallback has0support and no citations.
    Winning citation is the original source/span with retrieved-local label
    (one-based); never substitute a global chunk index for that display label.
    No stemming, punctuation cleanup, semantic inference or model is involved.
    """
    raise NotImplementedError
