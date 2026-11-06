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
    blocks={}
    for hit in hits:
        child=catalog.require(hit.child_id)
        key=(child.source_key,child.parent)
        parent=catalog.parent_by_key[key]
        if key not in blocks:
            source=catalog.source_by_key[child.source_key]
            blocks[key]={"source_id":source.key,"source_label":source.label,"parent_id":parent.ordinal,"start":parent.start,"end":parent.end,"text":parent.text,"matches":[]}
        blocks[key]["matches"].append({"child_id":child.key,"start":child.start,"end":child.end,"text":child.text,"score":hit.score,"initial_rank":hit.initial_rank})
    return list(blocks.values())
