"""Given exact binary64 vector codec and common corpus-generation checks."""
import struct

def pack_vector(vector):
    return struct.pack("<"+"d"*len(vector),*vector)

def unpack_vector(blob, dimensions):
    if len(blob) != dimensions*8:
        raise ValueError("vector payload dimension mismatch")
    return struct.unpack("<"+"d"*dimensions,blob)

def generation_rows(rows,generation):
    if any(row[-1] != generation for row in rows):
        raise ValueError("database rows belong to different corpus generations")
