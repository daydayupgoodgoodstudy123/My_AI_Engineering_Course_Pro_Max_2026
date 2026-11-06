"""Given complete source TF-IDF backend; it is not a candidate algorithm TODO."""
from collections import Counter
import math
from .models import Snapshot

def embed(text, vocab, idf):
    words = text.lower().split()
    counts = Counter(words)
    return tuple(counts.get(term, 0) / len(words) * weight for term, weight in zip(vocab,idf)) if words else (0.0,) * len(vocab)

def fit_snapshot(generation, documents, chunks):
    texts = [chunk.text for chunk in chunks]
    vocab = tuple(sorted({word for text in texts for word in text.lower().split()}))
    # These are the source formula and complete fit work, on both versions.
    idf = tuple(math.log((len(texts)+1)/(sum(term in text.lower().split() for text in texts)+1))+1 for term in vocab)
    vectors = tuple(embed(text,vocab,idf) for text in texts)
    return Snapshot(generation,tuple(documents),tuple(chunks),vocab,idf,vectors)

def search(question, snapshot, k):
    query = embed(question,snapshot.vocab,snapshot.idf)
    qnorm = math.sqrt(sum(x*x for x in query))
    scored = []
    for index, vector in enumerate(snapshot.vectors):
        norm = math.sqrt(sum(x*x for x in vector))
        score = sum(x*y for x,y in zip(query,vector))/(qnorm*norm) if qnorm and norm else 0.0
        scored.append((index,score))
    return sorted(scored,key=lambda value:-value[1])[:k]
