"""Complete exact binary64/vector and tagged scalar/RNG tuple codecs."""
import json,math,struct
def encode(value):
    if isinstance(value,tuple):return {'tuple':[encode(v)for v in value]}
    if type(value)is float:
        if not math.isfinite(value):raise ValueError('finite binary64 required')
        return {'float':value.hex()}
    if value is None or type(value)in(str,int,bool):return value
    raise TypeError('declared tagged scalar tree required')
def decode(value):
    if isinstance(value,dict):
        if set(value)=={'tuple'}:return tuple(decode(v)for v in value['tuple'])
        if set(value)=={'float'}:return float.fromhex(value['float'])
        raise ValueError('exact scalar tag required')
    return value
def dumps(value):return json.dumps(encode(value),ensure_ascii=False)
def loads(text):return decode(json.loads(text))
def pack_vectors(vectors):
    out=bytearray(b'SW19\x01'+struct.pack('>I',len(vectors)))
    for vector in vectors:out.extend(struct.pack('>I',len(vector)));out.extend(struct.pack('>'+str(len(vector))+'d',*vector))
    return bytes(out)
def unpack_vectors(data):
    if data[:5]!=b'SW19\x01':raise ValueError('declared checkpoint version required')
    count=struct.unpack_from('>I',data,5)[0];offset=9;vectors=[]
    for _ in range(count):
        n=struct.unpack_from('>I',data,offset)[0];offset+=4;vectors.append(struct.unpack_from('>'+str(n)+'d',data,offset));offset+=8*n
    if offset!=len(data):raise ValueError('complete declared vector payload required')
    return tuple(vectors)
