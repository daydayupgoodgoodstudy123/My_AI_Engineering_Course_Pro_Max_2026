"""Given token/stopword semantics, citation record and source-aware renderer."""
from dataclasses import dataclass
import json,re
STOPWORDS = frozenset("the a an is are was were what how why when where do does for of in to and or on at by it its this that".split())
FALLBACK = "I don't have enough information."

def word_tokens(text):
    return text.lower().split()

@dataclass(frozen=True)
class Citation:
    label: int
    chunk_id: int
    source_id: str
    source_name: str
    start: int
    end: int

def citation_for(label,hit,sentence):
    return Citation(label,hit.chunk_id,hit.source_id,hit.source_name,sentence.start,sentence.end)

CITATION_MARKER = re.compile(r"\[\^([1-9][0-9]*)\]")

def footnote(label,citation):
    payload = {"source":citation.source_name,"source_id":citation.source_id,"chunk":citation.chunk_id,"start":citation.start,"end":citation.end}
    return f"[^{label}]: " + json.dumps(payload,ensure_ascii=False)
