"""Given local module frame codec; this is not a framework wire protocol."""
import struct
def frame(path,payload):
    name=path.encode("utf-8")
    return struct.pack(">II",len(name),len(payload))+name+payload
def parse_frames(raw):
    out=[];cursor=0
    while cursor<len(raw):
        if len(raw)-cursor<8:raise ValueError("incomplete frame header")
        n,p=struct.unpack_from(">II",raw,cursor);cursor+=8
        if len(raw)-cursor<n+p:raise ValueError("incomplete module frame")
        name=raw[cursor:cursor+n].decode("utf-8");cursor+=n
        out.append((name,raw[cursor:cursor+p]));cursor+=p
    return out
