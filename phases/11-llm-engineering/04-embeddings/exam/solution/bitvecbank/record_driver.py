"""Given incremental record driver; callbacks own the local binary encoding."""
async def drive_vector_records(source, dimension, header_encoder, record_encoder):
    """Publish the header, then one encoded current record, and close the source.

    Callbacks are synchronous. No future record is pulled before the current
    callback result is published; even an empty source has its header.
    """
    try:
        yield header_encoder(dimension)
        async for row in source:
            yield record_encoder(row, dimension)
    finally:
        close = getattr(source, "aclose", None)
        if close is not None:
            await close()
