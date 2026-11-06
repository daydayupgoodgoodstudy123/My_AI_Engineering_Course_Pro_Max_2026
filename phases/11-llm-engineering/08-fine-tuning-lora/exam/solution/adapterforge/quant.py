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
    if any(type(c) is not int or not -8<=c<=7 for c in codes):raise ValueError("signed int4 code required")
    codes=list(codes)
    if len(codes)%2:codes.append(0)
    return bytes(((codes[i]&15)<<4)|(codes[i+1]&15) for i in range(0,len(codes),2))
def unpack_codes(payload,count):
    """Recover exactly count signed codes, ignoring the storage-only low tail nibble."""
    if type(count) is not int or count<0 or len(payload)!=(count+1)//2:raise ValueError("packed code count")
    codes=[]
    for value in payload:
        for n in (value>>4,value&15):codes.append(n-16 if n>=8 else n)
    return tuple(codes[:count])
def quantize(values,block_size=64):
    """Use absmax/7 with 1e-8 floor, ties-to-even rounding and [-8,7] clamp per padded block."""
    values=matrix(values)
    if type(block_size) is not int or block_size<=0:raise ValueError("positive block size")
    shape=(len(values),len(values[0]));flat=[x for row in values for x in row]
    pad=(-len(flat))%block_size;flat.extend([0.0]*pad);scales=[];codes=[]
    for start in range(0,len(flat),block_size):
        block=flat[start:start+block_size];scale=max(max(abs(x) for x in block)/7,1e-8)
        scales.append(scale);codes.extend(max(-8,min(7,round(x/scale))) for x in block)
    return Quantized(shape,block_size,pad,tuple(scales),pack_codes(codes))
def dequantize(artifact):
    """Restore the original matrix extent using each block's own scale."""
    ni,no=artifact.shape;count=ni*no+artifact.pad
    if artifact.block_size<=0 or artifact.pad!=(-ni*no)%artifact.block_size or len(artifact.scales)*artifact.block_size!=count:raise ValueError("quantized extent")
    codes=unpack_codes(artifact.payload,count)
    flat=[code*artifact.scales[i//artifact.block_size] for i,code in enumerate(codes)]
    flat=flat[:ni*no]
    return tuple(tuple(flat[i*no:(i+1)*no]) for i in range(ni))
