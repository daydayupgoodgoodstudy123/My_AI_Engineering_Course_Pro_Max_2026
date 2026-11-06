"""Candidate orchestration; lexical pair scoring is a separate TODO."""
from .models import Candidate,allowed_candidates,rank_batch,nonnegative
from .hyde import HyDEQueryResult

def project_candidates(candidates):
    """Preserve original retrieval ids, scores and one-based retrieval ranks."""
    return [Candidate(child_id,score,rank+1) for rank,(child_id,score) in enumerate(candidates)]

class SearchDesk:
    def query(self,query,candidates,catalog,metadata,pool_k,final_k,scorer):
        """Prefilter a complete retrieved list, rerank its pool, then final-cut.

        Input candidates are the complete ordered fixture retrieval list,
        not a pre-truncated external search result. scorer is mandatory and
        receives (query, original_child_id, original_text, initial_score).
        Preserve stable score ties and the original retrieval rank metadata.
        Zero pool/final limits are valid; no default scorer is supplied.
        """
        pool_k,final_k=nonnegative(pool_k),nonnegative(final_k)
        projected=project_candidates(candidates if metadata else candidates[:pool_k])
        allowed=allowed_candidates(projected,catalog,metadata)
        pool=allowed[:pool_k]
        ranked=rank_batch(query,pool,catalog,scorer)
        return ranked[:final_k]

    def query_hyde(self,question,retriever,catalog,metadata,pool_k,final_k,scorer):
        """Rerank source-style HyDE results and retain their hypothesis text.

        retriever returns (complete_candidate_rows, hypothesis_text).
        Pair scoring uses the user's original question. Candidate scores,
        retrieval ranks and metadata follow the same policy as query().
        """
        candidates,hypothesis=retriever(question)
        hits=self.query(question,candidates,catalog,metadata,pool_k,final_k,scorer)
        return HyDEQueryResult(hypothesis,tuple(hits))
