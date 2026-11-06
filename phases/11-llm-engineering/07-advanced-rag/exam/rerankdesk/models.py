"""Given typed source/parent/child catalog and strict lookup contracts."""
from dataclasses import dataclass
import json
import math

@dataclass(frozen=True)
class Source:
    key: str
    label: str
    text: str
    category: str
    created_us: int

@dataclass(frozen=True)
class Parent:
    source_key: str
    ordinal: int
    start: int
    end: int
    text: str

@dataclass(frozen=True)
class Child:
    key: str
    source_key: str
    parent: int
    ordinal: int
    start: int
    end: int
    text: str

@dataclass(frozen=True)
class Candidate:
    child_id: str
    initial_score: float
    initial_rank: int

@dataclass(frozen=True)
class ScoredHit:
    child_id: str
    initial_score: float
    score: float
    initial_rank: int

def child_key(source,parent,child):
    return json.dumps([source,parent,child],ensure_ascii=False,separators=(",",":"))

class Catalog:
    def __init__(self,sources=(),parents=(),children=()):
        self.sources,self.parents,self.children=tuple(sources),tuple(parents),tuple(children)
        self.source_by_key={row.key:row for row in self.sources}
        self.parent_by_key={(row.source_key,row.ordinal):row for row in self.parents}
        self.child_by_key={row.key:row for row in self.children}
        if len(self.sources)!=len(self.source_by_key) or len(self.parents)!=len(self.parent_by_key) or len(self.children)!=len(self.child_by_key):raise ValueError("duplicate catalog identity")
        for source in self.sources:
            if type(source.created_us) is not int:raise ValueError("creation time must be integer microseconds")
        for row in self.parents+self.children:
            source=self.source_by_key[row.source_key]
            raw=source.text.encode("utf-8")
            if not 0<=row.start<row.end<=len(raw) or raw[row.start:row.end].decode("utf-8")!=row.text:raise ValueError("catalog span disagrees with source")
        for row in self.children:
            parent=self.parent_by_key[(row.source_key,row.parent)]
            if row.key!=child_key(row.source_key,row.parent,row.ordinal) or not parent.start<=row.start<row.end<=parent.end:raise ValueError("child does not belong to declared parent")
    def require(self,key):
        """Correct downstream original-id lookup, without fallback rank coercion."""
        return self.child_by_key[key]
    def __eq__(self,other):
        return isinstance(other,Catalog) and (self.sources,self.parents,self.children)==(other.sources,other.parents,other.children)

def nonnegative(value):
    if type(value) is not int or value<0:raise ValueError("count must be a nonnegative integer")
    return value

def allowed_candidates(rows,catalog,metadata):
    """Given prefilter over the complete caller-supplied retrieval list."""
    if not metadata:return list(rows)
    def matches(row):
        source=catalog.source_by_key[catalog.require(row.child_id).source_key]
        return all(getattr(source,key)==value for key,value in metadata.items())
    return [row for row in rows if matches(row)]

def rank_batch(query,rows,catalog,scorer):
    """Given generic stable ranker; scorer is a required injected dependency."""
    output=[]
    for row in rows:
        child=catalog.require(row.child_id)
        score=scorer(query,row.child_id,child.text,row.initial_score)
        if type(score) not in (int,float) or not math.isfinite(score):raise ValueError("invalid supplied relevance score")
        output.append(ScoredHit(row.child_id,row.initial_score,float(score),row.initial_rank))
    return sorted(output,key=lambda row:-row.score)
