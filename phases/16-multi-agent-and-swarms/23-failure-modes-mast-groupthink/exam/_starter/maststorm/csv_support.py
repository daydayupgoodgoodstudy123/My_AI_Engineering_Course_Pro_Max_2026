"""Complete scalar/tree exact codec and quoted CSV resource, not a domain record serializer. Given."""
import csv,json
from decimal import Decimal
from pathlib import Path
HEADER=('uid','root','primary','symptoms','category','tags','action','budget','validation_action','validation_at','validation_cleared','validation_note')
def encode(value):
    def pack(x):
        if isinstance(x,Decimal):return {'D':str(x)}
        if isinstance(x,tuple):return {'T':[pack(v)for v in x]}
        if isinstance(x,list):return [pack(v)for v in x]
        if isinstance(x,dict):return {'M':[[k,pack(v)]for k,v in x.items()]}
        if x is None or type(x)in(str,int,float,bool):return x
        raise ValueError('declared JSON/Decimal/tuple value required')
    return json.dumps(pack(value),ensure_ascii=False,allow_nan=False,separators=(',',':'))
def decode(text):
    def unpack(x):
        if isinstance(x,list):return [unpack(v)for v in x]
        if isinstance(x,dict):
            if 'D'in x:return Decimal(x['D'])
            if 'T'in x:return tuple(unpack(v)for v in x['T'])
            return {k:unpack(v)for k,v in x['M']}
        return x
    return unpack(json.loads(text))
class CSVRows:
    def __init__(self,path):
        self.path=Path(path)
        if not self.path.exists():
            with self.path.open('w',newline='',encoding='utf-8')as f:csv.writer(f).writerow(HEADER)
    def append(self,values):
        if len(values)!=len(HEADER):raise ValueError('complete row required')
        with self.path.open('a',newline='',encoding='utf-8')as f:csv.writer(f).writerow(tuple(encode(v)for v in values))
    def all(self):
        with self.path.open(newline='',encoding='utf-8')as f:
            rows=csv.reader(f)
            if tuple(next(rows))!=HEADER:raise ValueError('archive schema')
            return tuple(tuple(decode(v)for v in row)for row in rows)
    def close(self):pass
