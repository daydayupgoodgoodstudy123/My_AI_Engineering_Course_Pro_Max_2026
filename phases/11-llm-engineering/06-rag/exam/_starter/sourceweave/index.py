"""Corpus lifecycle and Step5 retrieved context; no extractive generation here."""
from dataclasses import replace
from .models import Hit, ContextBundle, count_value, document_values, validate_snapshot, validate_hit
from .source_spans import index_chunks
from .backend import fit_snapshot, search

def project_hit(snapshot, index, score):
    """Project an original flat hit into its immutable source record."""
    chunk = snapshot.chunks[index]
    source = next(row for row in snapshot.documents if row.key == chunk.source_id)
    return Hit(chunk.ordinal,chunk.source_id,source.name,chunk.ordinal,chunk.start,chunk.end,chunk.text,score)

def render_context(snapshot, question, hits):
    """Given strict downstream provenance consumer and prompt builder."""
    for hit in hits:
        validate_hit(hit,snapshot)
    blocks = [f"[Source {label}] {hit.source_name} (chunk {hit.chunk_id})\n{hit.text}" for label,hit in enumerate(hits,1)]
    context = "\n\n---\n\n".join(blocks)
    prompt = f"Answer only from the following context.\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
    return ContextBundle(snapshot.generation,question,tuple(hits),prompt)

class RAGService:
    def __init__(self, words_per_chunk=512, default_k=5):
        self.words_per_chunk = words_per_chunk
        self.default_k = count_value(default_k)
        self.snapshot = None
    def replace_corpus(self, documents):
        """Replace all records and the fitted vector space as one generation."""
        documents = document_values(documents)
        chunks = index_chunks(documents,self.words_per_chunk)
        generation = self.snapshot.generation+1 if self.snapshot is not None else 1
        fitted = fit_snapshot(generation,documents,chunks)
        vectors = (self.snapshot.vectors if self.snapshot is not None else ()) + fitted.vectors
        fitted = replace(fitted,vectors=vectors)
        validate_snapshot(fitted)
        self.snapshot = fitted
        return fitted
    def prepare_context(self, question, top_k=None):
        """Return Step5 bundle from this generation; no answer extraction."""
        if self.snapshot is None:
            raise ValueError("corpus has not been indexed")
        k = count_value(top_k,self.default_k)
        snapshot = self.snapshot
        snapshot = fit_snapshot(snapshot.generation,snapshot.documents,snapshot.chunks)
        results = search(question,snapshot,k)
        hits = [project_hit(snapshot,index,score) for index,score in results]
        return render_context(snapshot,question,hits)
