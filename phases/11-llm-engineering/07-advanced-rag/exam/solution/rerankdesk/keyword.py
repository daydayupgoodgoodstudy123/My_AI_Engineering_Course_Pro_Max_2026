"""Fitted corpus statistics and complete local BM25 keyword candidates.

Counts, document frequencies, query weights and stable retrieval describe one fitted corpus. Re-index replaces all statistics. Source all-empty corpus has avg0,
but no matching terms enter its denominator; an absent corpus has avg1.
"""
from collections import Counter
import math

class KeywordIndex:
    def __init__(self):
        self.generation=0
        self.index((),())
    def index(self,ids,texts):
        ids,texts=tuple(ids),tuple(texts)
        if len(ids)!=len(texts) or len(set(ids))!=len(ids):raise ValueError("keyword records need unique paired ids")
        self.ids=ids
        self.counts=tuple(Counter(text.lower().split()) for text in texts)
        self.doc_lengths=tuple(sum(count.values()) for count in self.counts)
        self.n_docs=len(ids)
        self.doc_freqs={}
        for counts in self.counts:
            for term in counts:self.doc_freqs[term]=self.doc_freqs.get(term,0)+1
        self.avg_dl=sum(self.doc_lengths)/self.n_docs if self.n_docs else 1
        self.generation+=1
    def average_length(self):
        """Return the document-length statistic belonging to this index generation."""
        return self.avg_dl
    def query_weights(self,query):
        # Given algebraic query preparation; repeated query terms are retained.
        return tuple((term,math.log((self.n_docs-self.doc_freqs[term]+0.5)/(self.doc_freqs[term]+0.5)+1)) for term in query.lower().split() if term in self.doc_freqs)
    def score(self,weights,index):
        """Given actual source BM25 per-document computation."""
        avg=self.average_length()
        count=self.counts[index];length=self.doc_lengths[index];score=0.0
        for term,idf in weights:
            tf=count.get(term,0)
            if tf:
                score+=idf*(tf*2.2)/(tf+1.2*(0.25+0.75*length/avg))
        return score

def keyword_candidate_source(query,index):
    """Given complete real BM25 candidate generation and stable score ordering."""
    weights=index.query_weights(query)
    rows=[(key,index.score(weights,position)) for position,key in enumerate(index.ids)]
    return sorted(rows,key=lambda row:-row[1])
