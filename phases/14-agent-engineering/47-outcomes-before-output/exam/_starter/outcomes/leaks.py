"""Finite phrase matching: lexical leakage indicators, not semantic requirements review."""
from __future__ import annotations
import re
from dataclasses import dataclass
PLURALS={"databases":"database","summaries":"summary","incidents":"incident"}

def tokens(text:str)->list[tuple[str,int,int]]:
    """Correct supplied tokenizer. Unicode alphanumeric runs, underscore excluded;
    lowercase and the finite PLURALS map. Hyphens and whitespace are separators.
    Each token retains original Python-character offsets [start,end).
    """
    return [(PLURALS.get(m.group().lower(),m.group().lower()),m.start(),m.end())
            for m in re.finditer(r"[^\W_]+",text)]
@dataclass(frozen=True)
class Phrase:
    id:str
    category:str
    text:str
@dataclass(frozen=True)
class Leak:
    phrase:str
    category:str
    start:int
    end:int

def find_leaks(text:str,phrases:list[Phrase])->list[Leak]:
    """Scan from left to right. At each token choose the longest matching phrase,
    equal-length ties by phrase id, emit its category and original character span,
    then continue after that match. Otherwise advance one token. Match whole tokens;
    all normalization uses supplied tokens. Phrases are nonempty and ids unique.
    """
    raise NotImplementedError
