"""Given local binary format primitives, strict header checks and sign packer.

These versioned formats belong only to this exercise, not to a vector DB.
"""
import json
import struct
from .metrics import binarize
from .records import dimension_value

BANK_HEADER = struct.Struct("<4sBIII")  # magic, version, dimensions, rows, metadata bytes
STREAM_HEADER = struct.Struct("<4sI")   # magic, dimensions
RECORD_PREFIX = struct.Struct("<I")    # metadata byte count; packed code has ceil(D/8) bytes

def bank_header(data):
    if len(data) < BANK_HEADER.size:
        raise ValueError("truncated bank header")
    magic, version, dimension, count, metadata_size = BANK_HEADER.unpack_from(data)
    if magic != b"BV64" or version != 1:
        raise ValueError("unsupported bank format")
    dimension_value(dimension)
    return dimension, count, metadata_size

def metadata_bytes(records):
    """Given ordered Unicode metadata codec. Values are string dictionaries."""
    return json.dumps([{"key": row.key, "metadata": row.metadata} for row in records], ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def parse_metadata(blob):
    return json.loads(blob.decode("utf-8"))

def wire_metadata(record):
    return json.dumps({"key": record.key, "metadata": record.metadata}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def pack_sign_bits(vector):
    """Given MSB-first sign packing; unused low bits of final byte are zero."""
    bits = binarize(vector)
    output = bytearray((len(bits) + 7) // 8)
    for index, bit in enumerate(bits):
        output[index // 8] |= bit << (7 - index % 8)
    return bytes(output)

def packed_pair(a, b, dimension):
    """Given shape validation; padding is allowed to contain arbitrary bits."""
    dimension_value(dimension)
    size = (dimension + 7) // 8
    if not isinstance(a, bytes) or not isinstance(b, bytes) or len(a) != size or len(b) != size:
        raise ValueError("packed dimension mismatch")
    return a, b
