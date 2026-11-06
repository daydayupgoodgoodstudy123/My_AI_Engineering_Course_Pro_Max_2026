"""Markdown answer replay with a candidate citation-appendix formatter."""
from .evidence import CITATION_MARKER, footnote

def citation_appendix(body,references):
    """Return the Markdown appendix for completed, original text fragments.

    Markers are [^positive_integer], can cross fragment boundaries, and name
    local labels in references. Include each actually used label once in first
    appearance order. Reject unknown complete labels. Return an empty string
    if no valid markers exist, otherwise two LF separators, complete escaped
    footnote lines, and exactly one terminal LF. Do not modify the fragments
    or reference catalog. Replay and resource ownership are already supplied.
    """
    labels=list(dict.fromkeys(int(match.group(1)) for match in CITATION_MARKER.finditer("".join(body))))
    if any(label not in references for label in labels):
        raise ValueError("answer cites an unavailable retrieved label")
    if labels:
        return "\n\n"+"\n".join(footnote(label,references[label]) for label in labels)+"\n"
    return ""

async def encode_markdown(fragments,references):
    """Given original-fragment replay, complete-body capture and appendix dispatch.

    Publish every original source fragment before pulling another, including
    empty fragments. Only the synchronous appendix formatter is candidate work.
    The final body is buffered for citation discovery, without a memory bound.
    """
    body=[]
    async for fragment in fragments:
        body.append(fragment)
        yield fragment
    appendix=citation_appendix(body,references)
    if appendix:
        yield appendix

async def stream_markdown(fragments,references):
    """Given source/encoder ownership wrapper for early consumer close."""
    encoder=encode_markdown(fragments,references)
    try:
        async for fragment in encoder:yield fragment
    finally:
        await encoder.aclose()
        close=getattr(fragments,"aclose",None)
        if close is not None:await close()
