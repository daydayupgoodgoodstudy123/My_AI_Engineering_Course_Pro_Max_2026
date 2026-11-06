"""Recursive boundary-first chunks from correct supplied source splitters."""
from .source_spans import boundary_tree,span_text,span_words,token_spans

def recursive_chunks(document,max_words):
    """Visit section->paragraph->sentence; preserve a unit that already fits.

    Never merge adjacent sections/paragraphs. For an oversized leaf sentence,
    group consecutive given token spans in windows of at most max_words.
    Return ordered {source_id,start,end,text,section_path} records. Every token
    is covered once; whitespace gaps between chunks may be excluded. Offsets
    are original UTF8 bytes, text is the exact source slice. Heading text is
    covered normally, and section title metadata follows every descendant;
    do not repeat heading text in each interval. max_words is a positive int.
    The provided parser is finite/local, not a complete Markdown/NLP parser.
    """
    raise NotImplementedError
