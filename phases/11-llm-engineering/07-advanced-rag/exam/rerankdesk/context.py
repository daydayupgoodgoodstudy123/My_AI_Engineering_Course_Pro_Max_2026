"""Parent contexts with nested original child matches, separate from scoring."""

def expand_parent_context(catalog,hits):
    """Expand child hits into parent blocks in first/best-child hit order.

    Identity is (source_key,parent_ordinal), never ordinal alone or text.
    Emit one complete raw parent per identity, attach every selected child
    with original byte span, score and original retrieval rank, in hit order.
    Keep equal text from different sources distinct. Do not re-sort matches,
    clip a final child to its nominal size or concatenate across documents.
    Correct per-source parent/child construction and lookup are GIVEN.
    """
    raise NotImplementedError("Part 5")
