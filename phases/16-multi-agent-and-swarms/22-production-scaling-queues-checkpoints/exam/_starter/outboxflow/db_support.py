"""Complete exact codec, transaction resource and immutable-replay discriminator. Given."""
from contextlib import contextmanager
from decimal import Decimal
import json
import sqlite3

def encode(value):
    def pack(x):
        if isinstance(x,Decimal):
            return {'$decimal':str(x)}
        if isinstance(x,tuple):
            return {'$tuple':[pack(v) for v in x]}
        if isinstance(x,list):
            return [pack(v) for v in x]
        if isinstance(x,dict):
            return {'$dict':[[k,pack(v)] for k,v in x.items()]}
        if x is None or type(x) in (str,int,float,bool):
            return x
        raise ValueError('declared serializable value required')
    return json.dumps(pack(value),ensure_ascii=False,allow_nan=False,separators=(',',':'))

def decode(text):
    def unpack(x):
        if isinstance(x,list):return [unpack(v) for v in x]
        if isinstance(x,dict):
            if '$decimal' in x:return Decimal(x['$decimal'])
            if '$tuple' in x:return tuple(unpack(v) for v in x['$tuple'])
            return {k:unpack(v) for k,v in x['$dict']}
        return x
    return unpack(json.loads(text))

class Rows:
    def __init__(self,path):
        self.conn=sqlite3.connect(path)
        self.conn.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT,key TEXT,value TEXT,PRIMARY KEY(kind,key))')
        self.conn.commit()
    @contextmanager
    def atomic(self):
        with self.conn:
            yield
    def put(self,kind,key,value):
        k=encode(key);v=encode(value)
        old=self.conn.execute('SELECT value FROM records WHERE kind=? AND key=?',(kind,k)).fetchone()
        if old and old[0]!=v:raise ValueError('conflicting immutable record replay')
        self.conn.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)',(kind,k,v))
    def all(self,kind):
        return tuple(decode(row[0]) for row in self.conn.execute('SELECT value FROM records WHERE kind=? ORDER BY rowid',(kind,)))
    def close(self):
        self.conn.close()
