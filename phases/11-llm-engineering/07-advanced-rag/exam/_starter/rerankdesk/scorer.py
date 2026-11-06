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
        raise NotImplementedError("Part 3")
    def __call__(self,query,child_id,text,initial_score):
        return self.breakdown(query,text,initial_score).total
