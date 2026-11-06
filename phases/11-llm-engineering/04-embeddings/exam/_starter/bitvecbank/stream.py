"""Encode complete local BVS1 headers and packed-vector records."""
from .formats import STREAM_HEADER, RECORD_PREFIX, wire_metadata, pack_sign_bits
from .records import dimension_value, records_value
from .record_driver import drive_vector_records

def encode_vector_header(dimension):
    """Return the BVS1/<I vector-dimension header for the declared stream.

    The dimension is the number of vector coordinates, not its packed size.
    Use the supplied shape validator and binary struct definitions.
    """
    raise NotImplementedError

def encode_vector_record(row, dimension):
    """Return one complete record under the declared vector dimension.

    Layout: <I metadata UTF8 byte count + supplied metadata bytes + complete
    supplied sign-bit code. Preserve this row's metadata and coordinate order.
    The metadata codec, sign packer and strict record validator are supplied.
    """
    raise NotImplementedError

async def encode_vectors(source, dimension):
    """Given driver adapter; synchronous callbacks encode the domain bytes."""
    encoded = drive_vector_records(source, dimension, encode_vector_header, encode_vector_record)
    try:
        async for chunk in encoded:
            yield chunk
    finally:
        await encoded.aclose()

async def stream_vectors(source, dimension):
    """Given public ownership wrapper; the record driver owns source closure."""
    encoded = encode_vectors(source, dimension)
    try:
        async for chunk in encoded:
            yield chunk
    finally:
        await encoded.aclose()
