"""Independent source lexical reranker, not a cross-encoder model."""
from .features import STOPWORDS,ScoreBreakdown

class SourceLexicalScorer:
    def breakdown(self,query,text,initial_score):
        """Source four-feature contract, with intentional toy token semantics.

        Whole-token distinct term overlap. Unique adjacent bigrams from the
        ORDERED stopword-filtered query, each substring present at most once.
        For every unique term, first substring find in lowercased text earns
        0.5 iff 0<=position<len(lower_text)//3 (Python characters).
        Total=terms +2*bigrams +position_boost +5*initial_score.
        No punctuation cleanup, score normalization or model inference.
        """
        tokens=[word for word in query.lower().split() if word not in STOPWORDS]
        terms=set(tokens);lower=text.lower()
        term_overlap=len(terms & set(lower.split()))
        bigrams={tokens[i]+" "+tokens[i+1] for i in range(len(tokens)-1)}
        bigram_matches=sum(phrase in lower for phrase in bigrams)
        position_boost=sum(0.5 for term in terms if 0<=lower.find(term)<len(lower)//3)
        total=term_overlap+2*bigram_matches+position_boost+5*initial_score
        return ScoreBreakdown(term_overlap,bigram_matches,position_boost,total)
    def __call__(self,query,child_id,text,initial_score):
        return self.breakdown(query,text,initial_score).total
