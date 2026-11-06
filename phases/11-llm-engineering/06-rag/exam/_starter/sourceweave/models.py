"""Given immutable corpus records and strict snapshot/provenance contracts."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Document:
    key: str
    name: str
    text: str

@dataclass(frozen=True)
class Chunk:
    flat_id: int
    source_id: str
    ordinal: int
    start: int
    end: int
    text: str

@dataclass(frozen=True)
class Snapshot:
    generation: int
    documents: tuple
    chunks: tuple
    vocab: tuple
    idf: tuple
    vectors: tuple

@dataclass(frozen=True)
class Hit:
    chunk_id: int
    source_id: str
    source_name: str
    ordinal: int
    start: int
    end: int
    text: str
    score: float

@dataclass(frozen=True)
class ContextBundle:
    generation: int
    question: str
    hits: tuple
    prompt: str

def count_value(value, default=5):
    value = default if value is None else value
    if type(value) is not int or value < 0:
        raise ValueError("top_k must be a nonnegative integer")
    return value

def document_values(documents):
    rows = tuple(documents)
    if any(not isinstance(row, Document) or not isinstance(row.key, str) or not row.key or not isinstance(row.name, str) or not isinstance(row.text, str) for row in rows):
        raise ValueError("invalid source document")
    if len({row.key for row in rows}) != len(rows):
        raise ValueError("duplicate source identity")
    return rows

def validate_snapshot(snapshot):
    if type(snapshot.generation) is not int or snapshot.generation < 1:
        raise ValueError("invalid corpus generation")
    rows = document_values(snapshot.documents)
    documents = {row.key: row for row in rows}
    if len(snapshot.vectors) != len(snapshot.chunks):
        raise ValueError("corpus vectors and chunks must share one snapshot")
    if len(snapshot.idf) != len(snapshot.vocab) or len(set(snapshot.vocab)) != len(snapshot.vocab):
        raise ValueError("vocabulary dimensions disagree")
    if any(not isinstance(term, str) for term in snapshot.vocab) or any(type(x) not in (int,float) or not math.isfinite(x) for x in snapshot.idf):
        raise ValueError("invalid vector-space metadata")
    ordinals = {}
    for index, (chunk, vector) in enumerate(zip(snapshot.chunks, snapshot.vectors)):
        if chunk.flat_id != index or chunk.source_id not in documents or chunk.ordinal != ordinals.get(chunk.source_id, 0):
            raise ValueError("invalid flat/source-local chunk identity")
        ordinals[chunk.source_id] = chunk.ordinal + 1
        raw = documents[chunk.source_id].text.encode("utf-8")
        if type(chunk.start) is not int or type(chunk.end) is not int or not 0 <= chunk.start < chunk.end <= len(raw) or raw[chunk.start:chunk.end].decode("utf-8") != chunk.text:
            raise ValueError("chunk byte span disagrees with original source")
        if len(vector) != len(snapshot.vocab) or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):
            raise ValueError("vector dimensions disagree with generation")
    return snapshot

def validate_hit(hit, snapshot):
    if type(hit.chunk_id) is not int or not 0 <= hit.chunk_id < len(snapshot.chunks):
        raise ValueError("retrieved identity is outside this snapshot")
    chunk = snapshot.chunks[hit.chunk_id]
    source = next(row for row in snapshot.documents if row.key == chunk.source_id)
    if (hit.source_id, hit.source_name, hit.ordinal, hit.start, hit.end, hit.text) != (chunk.source_id, source.name, chunk.ordinal, chunk.start, chunk.end, chunk.text):
        raise ValueError("retrieved identity disagrees with source provenance")
