"""Blockwise uniform signed-int4 teaching codec, not a true NF4 codebook."""
from dataclasses import dataclass
from .mathops import matrix
@dataclass(frozen=True)
class Quantized:
    shape: tuple
    block_size: int
    pad: int
    scales: tuple
    payload: bytes
def pack_codes(codes):
    """Pack signed codes [-8,7], first code in the high nibble; pad an odd tail with zero."""
    raise NotImplementedError
def unpack_codes(payload,count):
    """Recover exactly count signed codes, ignoring the storage-only low tail nibble."""
    raise NotImplementedError
def quantize(values,block_size=64):
    """Use absmax/7 with 1e-8 floor, ties-to-even rounding and [-8,7] clamp per padded block."""
    raise NotImplementedError
def dequantize(artifact):
    """Restore the original matrix extent using each block's own scale."""
    raise NotImplementedError
