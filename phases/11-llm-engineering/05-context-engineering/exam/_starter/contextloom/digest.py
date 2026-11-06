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
    raise NotImplementedError
