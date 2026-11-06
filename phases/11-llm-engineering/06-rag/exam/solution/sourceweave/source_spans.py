"""Given literal source spans and splitters; offsets are UTF-8 byte offsets.

Index chunks use a word window without overlap. Candidate recursive chunking
uses the supplied section/paragraph/sentence tree, not these index windows.
The local parser recognizes '# ' headings, blank-line paragraphs and sentence
boundaries after .!? followed by whitespace. It is not a general NLP parser.
"""
from dataclasses import dataclass
import re
from .models import Chunk, document_values

@dataclass(frozen=True)
class Boundary:
    kind: str
    start: int
    end: int
    section_path: tuple
    children: tuple = ()

def byte_map(text):
    positions = [0]
    for character in text:
        positions.append(positions[-1] + len(character.encode("utf-8")))
    return positions

def index_chunks(documents, words_per_chunk=512):
    if type(words_per_chunk) is not int or words_per_chunk < 1:
        raise ValueError("chunk word budget must be positive")
    result = []
    for doc in document_values(documents):
        tokens = list(re.finditer(r"\S+",doc.text))
        offsets = byte_map(doc.text)
        for ordinal,start in enumerate(range(0,len(tokens),words_per_chunk)):
            batch = tokens[start:start+words_per_chunk]
            left,right = batch[0].start(),batch[-1].end()
            result.append(Chunk(len(result),doc.key,ordinal,offsets[left],offsets[right],doc.text[left:right]))
    return tuple(result)

def span_text(document, span):
    return document.text.encode("utf-8")[span.start:span.end].decode("utf-8")

def span_words(document, span):
    return len(span_text(document,span).split())

def token_spans(document, span):
    text = span_text(document,span)
    offsets = byte_map(text)
    return tuple((span.start+offsets[token.start()],span.start+offsets[token.end()]) for token in re.finditer(r"\S+",text))

def boundary_tree(document):
    text = document.text
    offsets = byte_map(text)
    headings = list(re.finditer(r"(?m)^# ([^\n]+)",text))
    starts = [match.start() for match in headings]
    if not starts or starts[0] != 0:
        starts.insert(0,0)
    heading_by_start = {match.start():match.group(1).strip() for match in headings}
    def trimmed(left,right):
        while left < right and text[left].isspace():left += 1
        while right > left and text[right-1].isspace():right -= 1
        return left,right
    def split_ranges(left,right,pattern):
        cursor = left
        for match in re.finditer(pattern,text[left:right]):
            end = left+match.start()
            a,b = trimmed(cursor,end)
            if a < b:yield a,b
            cursor = left+match.end()
        a,b = trimmed(cursor,right)
        if a < b:yield a,b
    sections = []
    for i,left in enumerate(starts):
        right = starts[i+1] if i+1 < len(starts) else len(text)
        left,right = trimmed(left,right)
        if left == right:continue
        path = (heading_by_start[left],) if left in heading_by_start else ()
        paragraphs = []
        for a,b in split_ranges(left,right,r"\n[ \t]*\n"):
            sentences = tuple(Boundary("sentence",offsets[c],offsets[d],path) for c,d in split_ranges(a,b,r"(?<=[.!?])\s+"))
            paragraphs.append(Boundary("paragraph",offsets[a],offsets[b],path,sentences))
        sections.append(Boundary("section",offsets[left],offsets[right],path,tuple(paragraphs)))
    return tuple(sections)

@dataclass(frozen=True)
class Sentence:
    text: str
    start: int
    end: int

def evidence_sentences(hit):
    """Given Python-source literal-period splitter, with correct byte mapping.

    Candidate applies strip+len>=10 eligibility; interior text is unchanged.
    Decimal/domain splitting is the source toy behavior, not a new TODO.
    """
    text = hit.text
    offsets = byte_map(text)
    cursor = 0
    for part in text.split("."):
        left,right = cursor,cursor+len(part)
        cursor = right+1
        while left < right and text[left].isspace():left += 1
        while right > left and text[right-1].isspace():right -= 1
        if left < right:yield Sentence(text[left:right],hit.start+offsets[left],hit.start+offsets[right])
