"""Per-query rerank evidence projection; CSV and async publication are given."""
from .codec import csv_chunk

def report_rows(query_id,hits,catalog):
    """Project this completed query's hits into complete CSV row mappings.

    Preserve supplied hit order and every occurrence. query_id is the current
    query identity. Use the original child id and retrieval initial_rank; score
    is this hit's rerank score, represented with round-trippable binary64 text.
    Look up each child's own source-local parent id and raw source label in the
    given catalog. Return an empty list for no hits, without changing inputs.
    CSV encoding, header, publication, source pulling and close are supplied.
    """
    rows=[]
    for hit in hits:
        child=catalog.require(hit.child_id)
        source=catalog.source_by_key[child.source_key]
        rows.append({"query_id":query_id,"doc_id":hit.child_id,"initial_rank":hit.initial_rank,"rerank_score":repr(hit.score),"parent_id":child.parent,"source_label":source.label})
    return rows

async def encode_batches(batches,catalog):
    """Given batch-local callback dispatch, CSV header and complete publication.

    Only synchronous report_rows is candidate work. Empty completed queries
    still call the given CSV codec. A current batch's rows are buffered together
    without a fixed memory bound; future batches are not consumed early.
    """
    header=True
    async for query_id,hits in batches:
        rows=report_rows(query_id,hits,catalog)
        yield csv_chunk(rows,header=header)
        header=False

async def stream_batches(batches,catalog):
    """Given owner wrapper; close does not consume future query batches."""
    encoder=encode_batches(batches,catalog)
    try:
        async for fragment in encoder:yield fragment
    finally:
        await encoder.aclose()
        close=getattr(batches,"aclose",None)
        if close is not None:await close()
