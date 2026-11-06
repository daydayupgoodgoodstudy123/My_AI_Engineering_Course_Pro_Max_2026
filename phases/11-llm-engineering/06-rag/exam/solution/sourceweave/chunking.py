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
    if type(max_words) is not int or max_words < 1:
        raise ValueError("chunk word budget must be positive")
    output=[]
    def emit(span,start=None,end=None):
        left=span.start if start is None else start
        right=span.end if end is None else end
        text=document.text.encode("utf-8")[left:right].decode("utf-8")
        output.append({"source_id":document.key,"start":left,"end":right,"text":text,"section_path":span.section_path})
    def visit(span):
        if span_words(document,span) <= max_words:
            emit(span)
        elif span.children:
            for child in span.children:visit(child)
        else:
            tokens=token_spans(document,span)
            for start in range(0,len(tokens),max_words):
                batch=tokens[start:start+max_words]
                emit(span,batch[0][0],batch[-1][1])
    for section in boundary_tree(document):visit(section)
    return output
