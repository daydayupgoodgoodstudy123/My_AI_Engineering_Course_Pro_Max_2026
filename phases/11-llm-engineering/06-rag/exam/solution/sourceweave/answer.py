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
    keywords = set(word_tokens(question)) - STOPWORDS
    best_text,best_score,best_citation = FALLBACK,0,None
    for label,hit in enumerate(bundle.hits,1):
        for sentence in evidence_sentences(hit):
            if len(sentence.text) < 10:
                continue
            score = len(keywords & set(word_tokens(sentence.text)))
            if score > best_score:
                best_text,best_score = sentence.text,score
                best_citation = citation_for(label,hit,sentence)
    return {"text":best_text,"support":best_score,"citations":(best_citation,) if best_citation is not None else ()}
