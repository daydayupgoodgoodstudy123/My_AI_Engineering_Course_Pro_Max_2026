"""Complete WPJ1 append framing/scalar codec. Integer times are signed64, never float."""
from pathlib import Path
import struct
MAGIC=b'WPJ1'
def encode_value(value):
    if value is None:return b'n'
    if type(value)is int:return b'i'+struct.pack('>q',value)
    if type(value)is str:
        raw=value.encode('utf-8');return b's'+struct.pack('>I',len(raw))+raw
    if type(value)is tuple:return b't'+struct.pack('>I',len(value))+b''.join(encode_value(v)for v in value)
    raise TypeError('journal scalar type')
def decode_value(raw,pos=0):
    tag=raw[pos:pos+1];pos+=1
    if tag==b'n':return None,pos
    if tag==b'i':return struct.unpack_from('>q',raw,pos)[0],pos+8
    if tag==b's':
        size=struct.unpack_from('>I',raw,pos)[0];pos+=4
        return raw[pos:pos+size].decode('utf-8'),pos+size
    if tag==b't':
        count=struct.unpack_from('>I',raw,pos)[0];pos+=4;values=[]
        for _ in range(count):value,pos=decode_value(raw,pos);values.append(value)
        return tuple(values),pos
    raise ValueError('journal tag')
def append_records(path,records):
    path=Path(path)
    if path.exists():
        with path.open('rb')as stream:
            if stream.read(4)!=MAGIC:raise ValueError('journal magic')
    new=not path.exists()
    with path.open('ab')as stream:
        if new:stream.write(MAGIC)
        for record in records:
            raw=encode_value(record);stream.write(struct.pack('>I',len(raw)));stream.write(raw)
def read_records(path):
    raw=Path(path).read_bytes()
    if raw[:4]!=MAGIC:raise ValueError('journal magic')
    pos=4;result=[]
    while pos<len(raw):
        if len(raw)-pos<4:raise ValueError('partial journal frame')
        size=struct.unpack_from('>I',raw,pos)[0];pos+=4;end=pos+size
        if end>len(raw):raise ValueError('partial journal frame')
        value,used=decode_value(raw[pos:end])
        if used!=size:raise ValueError('journal trailing data')
        result.append(value);pos=end
    return tuple(result)
