"""Bottom-up section/paragraph digest with ordered full-path provenance."""
from .documents import node_value, fit_digest
from .primitives import count_tokens

def digest_document(node, summarize):
    """Visit children before parent; summarize only over-budget local text.

    Leaf text is a paragraph; fitting leaves remain byte-for-byte verbatim.
    Parent input is newline-joined CHILD DIGESTS, not original leaf text.
    Return each node's path/title/text/tokens/sources/children. sources is an
    ordered tuple of leaf full paths, not section titles or a global seen set.
    Repeated titles are legal; each node obeys its own local token budget.
    Input is a finite tree; no actual model or summary-quality claim.
    """
    def visit(current, path):
        node_value(current)
        path = path + (current.key,)
        children = [visit(child, path) for child in current.children]
        text = "\n".join(child["text"] for child in children) if children else current.text
        text = fit_digest(text, current.budget, path, summarize)
        sources = tuple(source for child in children for source in child["sources"]) if children else (path,)
        return {"path": path, "title": current.title, "text": text, "tokens": count_tokens(text), "sources": sources, "children": children}
    return visit(node, ())
